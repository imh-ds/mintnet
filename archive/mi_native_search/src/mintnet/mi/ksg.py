"""A narrow bivariate implementation of the KSG-1 MI estimator."""

from collections.abc import Sequence

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


def estimate_ksg_mi(x: ArrayLike, y: ArrayLike, *, k: int = 5) -> float:
    """Estimate continuous bivariate mutual information in nats using KSG-1.

    Each marginal is standardized before Chebyshev-neighborhood queries. This
    changes neither MI nor the intended estimate while preventing input units
    from changing the joint metric.
    """
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

    x_standardized = (x_array - x_array.mean()) / x_array.std(ddof=1)
    y_standardized = (y_array - y_array.mean()) / y_array.std(ddof=1)
    joint = np.column_stack((x_standardized, y_standardized))
    joint_tree = cKDTree(joint)
    distances, _ = joint_tree.query(joint, k=k + 1, p=np.inf)
    radii = np.nextafter(distances[:, k], 0.0)

    x_tree = cKDTree(x_standardized[:, None])
    y_tree = cKDTree(y_standardized[:, None])
    x_neighbors = np.fromiter(
        (len(indices) for indices in x_tree.query_ball_point(x_standardized[:, None], radii, p=np.inf)),
        dtype=int,
        count=n,
    )
    y_neighbors = np.fromiter(
        (len(indices) for indices in y_tree.query_ball_point(y_standardized[:, None], radii, p=np.inf)),
        dtype=int,
        count=n,
    )

    estimate = digamma(k) + digamma(n) - np.mean(digamma(x_neighbors) + digamma(y_neighbors))
    return float(estimate)
