"""Tolerance-modified data-processing inequality pruning."""

from itertools import combinations

import numpy as np


def _validate_mi_matrix(mi_matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(mi_matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("mi_matrix must be a square matrix")
    if not np.isfinite(matrix).all():
        raise ValueError("mi_matrix must contain only finite values")
    if not np.allclose(matrix, matrix.T, rtol=0.0, atol=0.0):
        raise ValueError("mi_matrix must be symmetric")
    if not np.all(np.diag(matrix) == 0.0):
        raise ValueError("mi_matrix must have a zero diagonal")
    return matrix


def prune_tolerant_dpi(mi_matrix: np.ndarray, tau: float) -> np.ndarray:
    """Prune weakest edges of triangles satisfying a strict tolerant-DPI rule.

    Every edge starts retained. For each three-node combination, a unique
    weakest mutual-information edge is removed when it is strictly less than
    ``(1 - tau)`` times the weaker of the other two edges. Ties for the
    weakest edge are left untouched.
    """
    matrix = _validate_mi_matrix(mi_matrix)
    if not np.isscalar(tau):
        raise ValueError("tau must be a scalar")
    tau_value = float(tau)
    if not np.isfinite(tau_value) or not 0.0 <= tau_value < 1.0:
        raise ValueError("tau must satisfy 0 <= tau < 1")

    adjacency = np.ones(matrix.shape, dtype=bool)
    np.fill_diagonal(adjacency, False)
    for i, j, k in combinations(range(matrix.shape[0]), 3):
        edges = np.array([matrix[i, j], matrix[i, k], matrix[j, k]])
        weakest = int(np.argmin(edges))
        if np.count_nonzero(edges == edges[weakest]) != 1:
            continue
        stronger = np.delete(edges, weakest)
        threshold = (1.0 - tau_value) * np.min(stronger)
        if edges[weakest] < threshold:
            edge_pairs = ((i, j), (i, k), (j, k))
            left, right = edge_pairs[weakest]
            adjacency[left, right] = False
            adjacency[right, left] = False
    return adjacency
