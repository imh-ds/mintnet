"""Per-pair Fisher-z screening on raw (unconditional) Pearson correlation.

Same closed-form test family as mintnet.dpi.conditional's partial
correlation test, without conditioning on a third variable. See
docs/stage2_charter.md.
"""

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class ScreeningEvidence:
    """Pairwise Fisher-z test evidence for a p-column sample."""

    correlation: np.ndarray
    z_statistic: np.ndarray
    p_value: np.ndarray


def _validate_data(data: np.ndarray) -> np.ndarray:
    values = np.asarray(data, dtype=float)
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("data must be a two-dimensional array with at least two columns")
    if not np.isfinite(values).all():
        raise ValueError("data must contain only finite values")
    if values.shape[0] < 4:
        raise ValueError("data must have at least 4 rows for the Fisher z correlation test")
    zero_variance = np.where(values.std(axis=0, ddof=1) == 0.0)[0]
    if zero_variance.size > 0:
        raise ValueError(f"column(s) {list(zero_variance)} have zero variance; correlation is undefined")
    return values


def compute_pairwise_screening_evidence(data: np.ndarray) -> ScreeningEvidence:
    """Test every pair of columns for zero unconditional correlation.

    Returns symmetric p x p matrices (zero diagonal for correlation and
    z-statistic, one diagonal for p-value) holding, for every pair
    (i, j), the Pearson correlation, its Fisher z-statistic, and the
    two-sided p-value against the null of zero correlation.
    """
    values = _validate_data(data)
    n, p = values.shape
    correlation_matrix = np.corrcoef(values, rowvar=False)
    if not np.isfinite(correlation_matrix).all():
        raise ValueError("correlation matrix contains non-finite values; input is degenerate")

    z_stat = np.zeros((p, p))
    p_value = np.ones((p, p))
    for i, j in combinations(range(p), 2):
        r = float(np.clip(correlation_matrix[i, j], -1.0 + 1e-12, 1.0 - 1e-12))
        z = float(np.arctanh(r) * np.sqrt(n - 3))
        pv = float(2.0 * norm.sf(abs(z)))
        z_stat[i, j] = z_stat[j, i] = z
        p_value[i, j] = p_value[j, i] = pv
    np.fill_diagonal(correlation_matrix, 0.0)
    return ScreeningEvidence(correlation_matrix, z_stat, p_value)


def _pair_p_values(evidence: ScreeningEvidence) -> list[tuple[int, int, float]]:
    p = evidence.p_value.shape[0]
    return [(i, j, float(evidence.p_value[i, j])) for i, j in combinations(range(p), 2)]


def screen_uncorrected(evidence: ScreeningEvidence, alpha: float) -> np.ndarray:
    """Flag pair (i, j) as a candidate edge if p_ij <= alpha, independently per pair."""
    if not np.isscalar(alpha) or not (0.0 < float(alpha) < 1.0):
        raise ValueError("alpha must satisfy 0 < alpha < 1")
    flagged = evidence.p_value <= float(alpha)
    np.fill_diagonal(flagged, False)
    return flagged


def benjamini_hochberg_threshold(evidence: ScreeningEvidence, q: float) -> np.ndarray:
    """Flag candidate edges via the Benjamini-Hochberg procedure at FDR level q.

    Applied across the m = C(p, 2) independent pairwise tests, not the
    full p x p matrix (which would double-count each pair).
    """
    if not np.isscalar(q) or not (0.0 < float(q) < 1.0):
        raise ValueError("q must satisfy 0 < q < 1")
    pairs = _pair_p_values(evidence)
    m = len(pairs)
    ordered = sorted(pairs, key=lambda item: item[2])

    threshold_p = 0.0
    for rank, (_, _, pv) in enumerate(ordered, start=1):
        if pv <= (rank / m) * float(q):
            threshold_p = pv

    p = evidence.p_value.shape[0]
    flagged = np.zeros((p, p), dtype=bool)
    for i, j, pv in pairs:
        if pv <= threshold_p:
            flagged[i, j] = flagged[j, i] = True
    return flagged
