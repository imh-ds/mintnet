"""Gaussian three-node motifs used by the Stage 1 DPI experiment."""

from __future__ import annotations

import numpy as np


_TRIANGLE_PRECISIONS: dict[str, np.ndarray] = {
    "balanced": np.array(
        [[1.0, -0.25, -0.25], [-0.25, 1.0, -0.25], [-0.25, -0.25, 1.0]]
    ),
    "moderate": np.array(
        [[1.0, -0.35, -0.25], [-0.35, 1.0, -0.12], [-0.25, -0.12, 1.0]]
    ),
    "strong": np.array(
        [[1.0, -0.45, -0.25], [-0.45, 1.0, -0.08], [-0.25, -0.08, 1.0]]
    ),
}


def _validate_n(n: int) -> int:
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n < 1:
        raise ValueError("n must be at least 1")
    return int(n)


def _validate_strength(strength: float) -> float:
    value = float(strength)
    if not 0.0 < value < 1.0:
        raise ValueError("strength must satisfy 0 < strength < 1")
    return value


def sample_chain(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    """Draw a unit-variance Gaussian chain ``X1 -> X2 -> X3``."""
    n = _validate_n(n)
    strength = _validate_strength(strength)
    x1 = rng.normal(size=n)
    x2 = strength * x1 + np.sqrt(1.0 - strength**2) * rng.normal(size=n)
    x3 = strength * x2 + np.sqrt(1.0 - strength**2) * rng.normal(size=n)
    return np.column_stack((x1, x2, x3))


def sample_measured_fork(
    n: int, strength: float, rng: np.random.Generator
) -> np.ndarray:
    """Draw a unit-variance Gaussian fork with latent center ``X2``."""
    n = _validate_n(n)
    strength = _validate_strength(strength)
    x2 = rng.normal(size=n)
    x1 = strength * x2 + np.sqrt(1.0 - strength**2) * rng.normal(size=n)
    x3 = strength * x2 + np.sqrt(1.0 - strength**2) * rng.normal(size=n)
    return np.column_stack((x1, x2, x3))


def sample_hub(n: int, strength: float, children: int, rng: np.random.Generator) -> np.ndarray:
    """Draw a unit-variance Gaussian hub with a shared cause and independent children.

    Column 0 is the hub; columns 1..children are its children, each an
    independent noisy copy of the hub at the given strength. The
    direct three-or-more-child generalization of sample_measured_fork's
    two-child case.
    """
    n = _validate_n(n)
    strength = _validate_strength(strength)
    if not isinstance(children, int) or children < 2:
        raise ValueError("children must be an integer at least 2")
    hub = rng.normal(size=n)
    columns = [hub]
    for _ in range(children):
        columns.append(strength * hub + np.sqrt(1.0 - strength**2) * rng.normal(size=n))
    return np.column_stack(columns)


def _build_overlapping_triangles_precision() -> np.ndarray:
    precision = np.eye(5)
    for i, j in ((0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)):
        precision[i, j] = precision[j, i] = -0.25
    return precision


_OVERLAPPING_TRIANGLES_PRECISION: np.ndarray = _build_overlapping_triangles_precision()


def sample_overlapping_triangles(n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw two `balanced`-style triangles sharing one node (column 2).

    Columns 0,1,2 form one triangle; columns 2,3,4 form another. Column 2
    is the shared node. Verified positive definite at import time.
    """
    n = _validate_n(n)
    covariance = np.linalg.inv(_OVERLAPPING_TRIANGLES_PRECISION)
    data = rng.multivariate_normal(np.zeros(5), covariance, size=n)
    return (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)


def triangle_precisions() -> dict[str, np.ndarray]:
    """Return copies of the named positive-definite precision fixtures."""
    return {name: precision.copy() for name, precision in _TRIANGLE_PRECISIONS.items()}


def sample_precision_triangle(
    name: str, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw and sample-standardize a Gaussian triangle fixture."""
    n = _validate_n(n)
    try:
        precision = _TRIANGLE_PRECISIONS[name]
    except KeyError as exc:
        raise ValueError(f"unknown triangle precision fixture: {name}") from exc
    try:
        np.linalg.cholesky(precision)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"triangle precision is not positive definite: {name}") from exc
    covariance = np.linalg.inv(precision)
    data = rng.multivariate_normal(np.zeros(3), covariance, size=n)
    return (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)


def sample_monotonic_curvature_triangle(
    target_rho: float, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw a triangle fixture where the third edge (columns 1, 2) is
    related through a monotonic, saturating nonlinear transform
    (`tanh`) rather than linearly -- Stage 7d's own mild-curvature
    condition. See docs/stage7d_charter.md.

    Built by drawing `sample_weak_edge_triangle(target_rho, n, rng)`
    (columns 0, 1 unchanged) and replacing column 2 with `tanh` of
    itself, re-standardized. `tanh` is a strictly monotonic (hence
    injective) elementwise transform, and mutual information is exactly
    invariant under an injective transform of a single argument:
    `I(X1; tanh(X2) | X0) = I(X1; X2 | X0)`, for any joint distribution.
    (Injectivity is what invariance requires here, not surjectivity --
    `tanh`'s bounded range `(-1, 1)` does not weaken the claim.)

    This fixture therefore has the *exact same* population conditional
    mutual information as `sample_weak_edge_triangle(target_rho, ...)`
    at the same `target_rho` -- a matched-MI, harder-for-a-linear-test
    counterpart, not a stronger or weaker true dependence. Pearson
    correlation (and any partial-correlation/Fisher-z test built on it)
    is *not* invariant under a nonlinear monotonic transform, so such a
    test sees a distorted, generally attenuated relationship here
    instead of the true partial correlation `target_rho` it would
    recover on the untransformed fixture.
    """
    data = sample_weak_edge_triangle(target_rho, n, rng).copy()
    data[:, 2] = np.tanh(data[:, 2])
    return (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)


_USHAPE_DOMINANT_EDGE_01 = 0.45
_USHAPE_DOMINANT_EDGE_02 = 0.25
_USHAPE_CURVATURE_BOUND = 1.0 / np.sqrt(2.0)


def _validate_curvature(curvature: float) -> float:
    value = float(curvature)
    if not abs(value) < _USHAPE_CURVATURE_BOUND:
        raise ValueError(
            f"curvature must satisfy abs(curvature) < {_USHAPE_CURVATURE_BOUND:.6f} (1/sqrt(2)), "
            "so the quadratic term's own variance share cannot exceed the residual's total unit variance"
        )
    return value


def sample_ushape_triangle(curvature: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw a triangle fixture where the third edge (columns 1, 2) is a
    symmetric quadratic dependence -- "U"-shaped for `curvature > 0`,
    inverted-U for `curvature < 0` -- with *exactly zero* linear partial
    correlation given column 0. Stage 7d's own diagnostic condition for
    whether a structured estimator has quietly collapsed to a linear
    model. See docs/stage7d_charter.md.

    Construction: column 0 is a common cause of columns 1 and 2 at
    `strong`'s own dominant-edge magnitudes (`.45`, `.25`). Column 1's
    residual (after removing column 0's linear effect) is standard
    normal noise `e1`. Column 2's residual is
    `curvature * (e1**2 - 1) + sqrt(1 - 2*curvature**2) * e2`, with
    independent standard normal `e2` -- a deterministic *quadratic*
    function of `e1` plus independent noise, not a linear one.

    Because `e1` is standard normal, `E[e1] = E[e1**3] = 0` exactly, so
    `Cov(e1, e1**2 - 1) = E[e1**3] - E[e1] = 0` exactly, for *any*
    `curvature`. Since column 0's linear effect is removed identically
    from both columns 1 and 2, this is also the column-0-partialled
    correlation: a Fisher-z/partial-correlation test sees a perfect
    null here for any `curvature`, while the true conditional mutual
    information `I(X1; X2 | X0)` is strictly positive whenever
    `curvature != 0` (column 2's residual is a non-constant function of
    column 1's residual plus independent noise, hence not conditionally
    independent of it).

    `curvature` must satisfy `abs(curvature) < 1/sqrt(2)` so the
    independent-noise variance share `1 - 2*curvature**2` stays
    positive. `curvature = 0` is a valid null (column 2's residual is
    then pure noise, so columns 1 and 2 are fully conditionally
    independent given column 0).
    """
    n = _validate_n(n)
    curvature = _validate_curvature(curvature)
    x0 = rng.normal(size=n)
    e1 = rng.normal(size=n)
    e2 = rng.normal(size=n)
    x1 = _USHAPE_DOMINANT_EDGE_01 * x0 + np.sqrt(1.0 - _USHAPE_DOMINANT_EDGE_01**2) * e1
    residual_2 = curvature * (e1**2 - 1.0) + np.sqrt(1.0 - 2.0 * curvature**2) * e2
    x2 = _USHAPE_DOMINANT_EDGE_02 * x0 + np.sqrt(1.0 - _USHAPE_DOMINANT_EDGE_02**2) * residual_2
    data = np.column_stack((x0, x1, x2))
    return (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)


def sample_weak_edge_triangle(target_rho: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw a triangle fixture extending `strong`'s own structure: the
    same two dominant edges (partial correlation `.45` between columns
    0-1, `.25` between columns 0-2, matching `strong`'s own off-diagonal
    precision entries), with the third edge's own partial correlation
    (columns 1-2) set to `target_rho` instead of `strong`'s fixed
    `-.08` -- for Stage 7b's own effect-size sweep. See
    docs/stage7b_charter.md.

    Since this precision matrix has a unit diagonal,
    `partial_correlation(i,j) = -precision[i,j]` exactly (the same
    convention every named fixture above already uses) -- `target_rho`
    is therefore the exact resulting partial correlation on columns
    (1, 2), not an approximation. Positive-definiteness is checked, not
    assumed, exactly as `sample_precision_triangle` does for its own
    named fixtures.
    """
    n = _validate_n(n)
    rho = float(target_rho)
    precision = np.array([[1.0, -0.45, -0.25], [-0.45, 1.0, -rho], [-0.25, -rho, 1.0]])
    try:
        np.linalg.cholesky(precision)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"weak_edge_triangle precision is not positive definite at target_rho={rho}") from exc
    covariance = np.linalg.inv(precision)
    data = rng.multivariate_normal(np.zeros(3), covariance, size=n)
    return (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)
