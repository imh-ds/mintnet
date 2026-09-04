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
