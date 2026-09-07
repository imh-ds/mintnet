"""Pairwise mutual-information matrix estimation."""

from itertools import combinations

import numpy as np

from .ksg import estimate_ksg_mi


def estimate_pairwise_mi(data: np.ndarray, k: int) -> np.ndarray:
    """Estimate KSG MI for every unordered pair of three data columns."""
    values = np.asarray(data, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("data must be a two-dimensional array with three columns")
    if not np.isfinite(values).all():
        raise ValueError("data must contain only finite values")
    result = np.zeros((3, 3), dtype=float)
    for left, right in combinations(range(3), 2):
        estimate = estimate_ksg_mi(values[:, left], values[:, right], k=k)
        result[left, right] = estimate
        result[right, left] = estimate
    return result
