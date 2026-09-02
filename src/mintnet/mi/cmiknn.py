"""Conditional mutual information estimator (CMIknn, Frenzel & Pompe
2007), a direct generalization of `mintnet.mi.ksg.estimate_ksg_mi`'s
own validated bivariate formula and counting convention -- same
per-dimension standardization, Chebyshev/max-norm distance, and
self-inclusive open-ball neighbor counting via the epsilon-minus
radius trick. Paired with a local-permutation significance test
(Runge, 2018) for conditional independence testing, since CMIknn has
no closed-form null distribution. See docs/stage6b_charter.md.

Implementation-time disclosure: the local-permutation shuffle below is
a good-faith, documented construction of Runge's general idea (bias a
permutation of Y toward each point's own nearest Z-neighbors, so the
Y-Z and X-Z marginal structure survives the shuffle while the direct
X-Y link is broken) -- it is not verified against the original paper's
own reference implementation, and this charter's own Type-I-error gate
exists specifically to catch it if this construction is not valid.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree
from scipy.special import digamma

ArrayLike = Sequence[float] | np.ndarray


def _as_finite_vector(values: ArrayLike, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _as_conditioning_matrix(z: ArrayLike | None, n: int) -> np.ndarray:
    if z is None:
        return np.empty((n, 0))
    array = np.asarray(z, dtype=float)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2 or array.shape[0] != n:
        raise ValueError("z must be a 1D or 2D array with n rows, or None")
    if not np.isfinite(array).all():
        raise ValueError("z must contain only finite values")
    return array


def _standardize_columns(array: np.ndarray) -> np.ndarray:
    if array.shape[1] == 0:
        return array
    std = array.std(axis=0, ddof=1)
    if np.any(std == 0.0):
        raise ValueError("a conditioning column has zero variance; standardization is undefined")
    return (array - array.mean(axis=0)) / std


def estimate_cmiknn(x: ArrayLike, y: ArrayLike, z: ArrayLike | None = None, *, k: int = 20) -> float:
    """Estimate I(X;Y|Z) in nats via CMIknn. `z=None` reduces exactly
    to `mintnet.mi.ksg.estimate_ksg_mi`'s own bivariate formula (see
    tests/unit/test_cmiknn.py's own exact-agreement check) -- the
    z-only marginal count is treated as the constant `n` when `Z` has
    zero dimensions, which algebraically collapses the general formula
    to the bivariate one rather than requiring a separate code path."""
    x_array = _as_finite_vector(x, "x")
    y_array = _as_finite_vector(y, "y")
    if x_array.size != y_array.size:
        raise ValueError("x and y must have the same length")
    n = x_array.size
    if not 1 <= k < n:
        raise ValueError("k must satisfy 1 <= k < n")
    if np.std(x_array, ddof=1) == 0.0:
        raise ValueError("x must have nonzero variance")
    if np.std(y_array, ddof=1) == 0.0:
        raise ValueError("y must have nonzero variance")

    z_array = _as_conditioning_matrix(z, n)
    m = z_array.shape[1]

    x_s = (x_array - x_array.mean()) / x_array.std(ddof=1)
    y_s = (y_array - y_array.mean()) / y_array.std(ddof=1)
    z_s = _standardize_columns(z_array)

    joint = np.column_stack([x_s, y_s, z_s])
    joint_tree = cKDTree(joint)
    distances, _ = joint_tree.query(joint, k=k + 1, p=np.inf)
    radii = np.nextafter(distances[:, k], 0.0)

    xz = np.column_stack([x_s, z_s])
    yz = np.column_stack([y_s, z_s])
    xz_tree = cKDTree(xz)
    yz_tree = cKDTree(yz)
    n_xz = np.fromiter((len(idx) for idx in xz_tree.query_ball_point(xz, radii, p=np.inf)), dtype=int, count=n)
    n_yz = np.fromiter((len(idx) for idx in yz_tree.query_ball_point(yz, radii, p=np.inf)), dtype=int, count=n)

    if m > 0:
        z_tree = cKDTree(z_s)
        n_z = np.fromiter((len(idx) for idx in z_tree.query_ball_point(z_s, radii, p=np.inf)), dtype=int, count=n)
    else:
        n_z = np.full(n, n, dtype=int)

    estimate = digamma(k) - np.mean(digamma(n_xz) + digamma(n_yz) - digamma(n_z))
    return float(estimate)


def _local_permutation(y: np.ndarray, z_standardized: np.ndarray, k_perm: int, rng: np.random.Generator) -> np.ndarray:
    """Shuffle y toward each point's own k_perm nearest Z-neighbors: a
    greedy random matching (not a naive per-point independent draw),
    so the result is a valid permutation of y, not a resampling with
    replacement."""
    n = len(y)
    tree = cKDTree(z_standardized)
    _, neighbor_idx = tree.query(z_standardized, k=min(k_perm + 1, n))
    neighbor_idx = neighbor_idx[:, 1:]  # drop self (always the nearest neighbor of itself)

    order = rng.permutation(n)
    used = np.zeros(n, dtype=bool)
    perm = np.full(n, -1, dtype=int)
    for i in order:
        candidates = [int(j) for j in neighbor_idx[i] if not used[j]]
        if candidates:
            j = candidates[int(rng.integers(len(candidates)))]
        else:
            leftover = np.flatnonzero(~used)
            j = int(leftover[int(rng.integers(len(leftover)))])
        perm[i] = j
        used[j] = True
    return np.asarray(y, dtype=float)[perm]


@dataclass(frozen=True)
class LocalPermutationResult:
    statistic: float
    p_value: float
    null_distribution: tuple[float, ...]


def local_permutation_test(
    x: ArrayLike,
    y: ArrayLike,
    z: ArrayLike | None = None,
    *,
    k: int = 20,
    k_perm: int = 5,
    permutations: int = 199,
    rng: np.random.Generator,
) -> LocalPermutationResult:
    """Test X independent-of Y given Z via CMIknn and a local
    permutation null. `z=None`: ordinary (global) permutation, valid
    for the unconditional case. p-value uses the standard `+1`
    correction (never exactly zero)."""
    observed = estimate_cmiknn(x, y, z, k=k)
    n = len(np.asarray(x))
    null = np.empty(permutations)

    if z is None:
        y_array = _as_finite_vector(y, "y")
        for b in range(permutations):
            null[b] = estimate_cmiknn(x, rng.permutation(y_array), None, k=k)
    else:
        z_array = _as_conditioning_matrix(z, n)
        z_s = _standardize_columns(z_array)
        for b in range(permutations):
            y_shuffled = _local_permutation(y, z_s, k_perm, rng)
            null[b] = estimate_cmiknn(x, y_shuffled, z, k=k)

    p_value = (float(np.sum(null >= observed)) + 1.0) / (permutations + 1.0)
    return LocalPermutationResult(statistic=observed, p_value=p_value, null_distribution=tuple(null.tolist()))
