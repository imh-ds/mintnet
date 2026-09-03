"""Conditional mutual information estimator (CMIknn, Frenzel & Pompe
2007), a direct generalization of `mintnet.mi.ksg.estimate_ksg_mi`'s
own validated bivariate formula and counting convention -- same
per-dimension standardization, Chebyshev/max-norm distance, and
self-inclusive open-ball neighbor counting via the epsilon-minus
radius trick. Paired with a local-permutation significance test
(Runge, 2018) for conditional independence testing, since CMIknn has
no closed-form null distribution. See docs/stage6b_charter.md and
docs/stage6d_charter.md.

D-055 (Stage 6c): a first-pass, good-faith construction of the local
permutation shuffle was found, with proper statistical power, to be
genuinely miscalibrated at |S| in {1, 2} regardless of k_perm -- not a
tunable-parameter problem. D-055's own required next step was to
compare that construction directly against Runge's own reference
implementation (`tigramite.independence_tests.cmiknn.CMIknn`'s
`get_shuffle_significance`/`get_restricted_permutation`). Three
structural discrepancies were found and are fixed below:

1. **Self-inclusion**: the reference queries each point's nearest
   neighbors in Z-space *including the point itself* as a candidate
   (a point is its own nearest neighbor at distance 0). The prior
   version explicitly excluded self. Self-inclusion means a point
   occasionally maps to itself under the shuffle (no-op for that
   point on that replicate) -- an intentional, not incidental,
   property of the reference construction.
2. **No global fallback on local exhaustion -- the actual likely cause
   of D-055's finding**: when every one of a point's `k_perm`
   neighbors is already claimed by an earlier point in the same
   permutation replicate, the reference reuses the last-tried
   neighbor anyway (accepting an occasional duplicate/collision
   rather than a strict permutation). The prior version instead fell
   back to a *uniformly random pick from the entire remaining
   dataset* -- which can be arbitrarily far from the point's own
   Z-neighborhood, corrupting exactly the local Y-Z structure this
   shuffle exists to preserve. This should matter most exactly where
   local exhaustion is common, plausibly explaining why |S| in {1, 2}
   miscalibrated while |S| = 0 (no local matching at all) and |S| = 3
   (a denser DGP, less exhaustion) did not.
3. **Distance metric**: the reference queries Z-neighbors with
   Chebyshev/max-norm distance (`p=inf`), matching this module's own
   `estimate_cmiknn` convention throughout. The prior version queried
   with `scipy`'s default (Euclidean, `p=2`) -- a silent inconsistency
   with the rest of this module, independent of the other two issues.

The reference implementation also computes the Z-neighbor tree/query
ONCE per significance test (Z does not change across permutation
replicates) rather than once per replicate; adopted below both for
fidelity to the reference and because it removes a real, previously
unnecessary cost (a full KD-tree rebuild per permutation).
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


def _z_neighbors(z_standardized: np.ndarray, k_perm: int) -> np.ndarray:
    """Each point's `k_perm` nearest Z-neighbors, self-inclusive,
    Chebyshev/max-norm distance -- matches Runge/tigramite's own
    `CMIknn.get_shuffle_significance` exactly (see this module's own
    docstring, point 1 and 3). Computed once per significance test,
    not once per permutation replicate, since Z is fixed throughout."""
    n = z_standardized.shape[0]
    k = min(k_perm, n)
    tree = cKDTree(z_standardized)
    _, neighbor_idx = tree.query(z_standardized, k=k, p=np.inf)
    if k == 1:
        neighbor_idx = neighbor_idx[:, None]
    return neighbor_idx.astype(int)


def _restricted_permutation(neighbors: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Runge/tigramite's own `get_restricted_permutation`: shuffle each
    point's own (self-inclusive) neighbor list, then visit points in a
    random order and assign each one the first not-yet-used neighbor
    from its own shuffled list. If every one of a point's `k_perm`
    neighbors is already claimed, reuse the last one anyway (an
    accepted, rare collision) rather than reaching outside the local
    neighborhood -- the fix for D-055 (a prior version instead fell
    back to a uniformly random point from the entire dataset, which
    could be arbitrarily far in Z-space)."""
    n, k = neighbors.shape
    shuffled = neighbors.copy()
    for row in shuffled:
        rng.shuffle(row)

    order = rng.permutation(n)
    used = np.zeros(n, dtype=bool)
    perm = np.empty(n, dtype=int)
    for i in order:
        m = 0
        use = int(shuffled[i, m])
        while used[use] and m < k - 1:
            m += 1
            use = int(shuffled[i, m])
        perm[i] = use
        used[use] = True
    return perm


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
        y_array = _as_finite_vector(y, "y")
        neighbors = _z_neighbors(z_s, k_perm)
        for b in range(permutations):
            perm = _restricted_permutation(neighbors, rng)
            null[b] = estimate_cmiknn(x, y_array[perm], z, k=k)

    p_value = (float(np.sum(null >= observed)) + 1.0) / (permutations + 1.0)
    return LocalPermutationResult(statistic=observed, p_value=p_value, null_distribution=tuple(null.tolist()))
