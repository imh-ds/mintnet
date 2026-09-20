"""Conditional-independence pruning via Gaussian partial correlation.

For jointly Gaussian variables, conditional mutual information is a strictly
monotonic function of partial correlation:
``I(Xi; Xj | Xk) = -0.5 * ln(1 - r_ij.k ** 2)``. Testing the partial
correlation against zero is therefore the exact, closed-form conditional-MI
test on this data-generating process; see ``docs/stage1b_charter.md``.
"""

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class ConditionalIndependenceEvidence:
    """Pairwise partial-correlation test evidence for a three-column sample."""

    partial_correlation: np.ndarray
    z_statistic: np.ndarray
    p_value: np.ndarray


def _validate_data(data: np.ndarray) -> np.ndarray:
    values = np.asarray(data, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("data must be a two-dimensional array with three columns")
    if not np.isfinite(values).all():
        raise ValueError("data must contain only finite values")
    if values.shape[0] < 5:
        raise ValueError("data must have at least 5 rows for the Fisher z partial-correlation test")
    return values


def compute_conditional_independence_evidence(data: np.ndarray) -> ConditionalIndependenceEvidence:
    """Test each pair for independence conditional on the remaining third column.

    Returns symmetric 3x3 matrices (zero diagonal for the correlation and
    z-statistic, one diagonal for the p-value) holding, for every pair
    ``(i, j)``, the partial correlation ``r_ij.k``, its Fisher z-statistic,
    and the two-sided p-value against the null of conditional independence.
    """
    values = _validate_data(data)
    n = values.shape[0]
    correlation = np.corrcoef(values, rowvar=False)

    partial = np.zeros((3, 3))
    z_stat = np.zeros((3, 3))
    p_value = np.ones((3, 3))
    for i, j in combinations(range(3), 2):
        (k,) = {0, 1, 2} - {i, j}
        r_ij, r_ik, r_jk = correlation[i, j], correlation[i, k], correlation[j, k]
        denominator = np.sqrt((1.0 - r_ik**2) * (1.0 - r_jk**2))
        if not denominator > 0.0:
            raise ValueError("partial correlation is undefined for collinear inputs")
        r_partial = (r_ij - r_ik * r_jk) / denominator
        r_partial = float(np.clip(r_partial, -1.0 + 1e-12, 1.0 - 1e-12))
        z = float(np.arctanh(r_partial) * np.sqrt(n - 4))
        p = float(2.0 * norm.sf(abs(z)))
        partial[i, j] = partial[j, i] = r_partial
        z_stat[i, j] = z_stat[j, i] = z
        p_value[i, j] = p_value[j, i] = p
    return ConditionalIndependenceEvidence(partial, z_stat, p_value)


def prune_conditional_independence(data: np.ndarray, alpha: float) -> np.ndarray:
    """Retain an edge only when its partial-correlation test rejects independence at alpha.

    Mirrors ``prune_tolerant_dpi``'s adjacency-matrix contract but decides
    each edge from its own conditional-independence test rather than by
    comparing magnitudes against the other two edges of a triangle.
    """
    if not np.isscalar(alpha):
        raise ValueError("alpha must be a scalar")
    alpha_value = float(alpha)
    if not np.isfinite(alpha_value) or not 0.0 < alpha_value < 1.0:
        raise ValueError("alpha must satisfy 0 < alpha < 1")

    evidence = compute_conditional_independence_evidence(data)
    adjacency = evidence.p_value <= alpha_value
    np.fill_diagonal(adjacency, False)
    return adjacency
