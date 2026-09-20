"""General multi-variable conditional-independence pruning.

Generalizes mintnet.dpi.conditional's one-variable partial correlation
test to an arbitrary conditioning set, via linear-regression residuals
(exact and closed-form for jointly Gaussian data). See
docs/stage1k_charter.md.
"""

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class PartialCorrelationEvidence:
    """Partial correlation test evidence for one pair, given a conditioning set."""

    partial_correlation: float
    z_statistic: float
    p_value: float


def _validate_data(data: np.ndarray) -> np.ndarray:
    values = np.asarray(data, dtype=float)
    if values.ndim != 2:
        raise ValueError("data must be a two-dimensional array")
    if not np.isfinite(values).all():
        raise ValueError("data must contain only finite values")
    return values


def _residualize(target: np.ndarray, conditioning: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(conditioning)), conditioning])
    coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
    return target - design @ coefficients


def compute_partial_correlation_evidence(
    data: np.ndarray, i: int, j: int, conditioning: Sequence[int]
) -> PartialCorrelationEvidence:
    """Test whether columns i and j are independent given the conditioning columns.

    Exact for jointly Gaussian data: partial correlation via OLS residuals,
    Fisher z-transform with standard error 1/sqrt(N - 3 - |conditioning|).
    """
    values = _validate_data(data)
    n, p = values.shape
    conditioning = list(conditioning)
    if i == j or i in conditioning or j in conditioning:
        raise ValueError("i, j, and conditioning must all be distinct columns")
    if not (0 <= i < p and 0 <= j < p) or any(not (0 <= c < p) for c in conditioning):
        raise ValueError("i, j, and conditioning must be valid column indices")
    degrees_of_freedom = n - 3 - len(conditioning)
    if degrees_of_freedom <= 0:
        raise ValueError("not enough rows for this conditioning set size")
    if values[:, i].std(ddof=1) == 0.0:
        raise ValueError(f"column {i} has zero variance; partial correlation is undefined")
    if values[:, j].std(ddof=1) == 0.0:
        raise ValueError(f"column {j} has zero variance; partial correlation is undefined")

    if conditioning:
        cond_data = values[:, conditioning]
        resid_i = _residualize(values[:, i], cond_data)
        resid_j = _residualize(values[:, j], cond_data)
    else:
        resid_i = values[:, i] - values[:, i].mean()
        resid_j = values[:, j] - values[:, j].mean()

    # Use a relative tolerance, not exact equality: OLS residuals from an
    # (near-)collinear conditioning set are numerically ~1e-15, not exactly
    # 0.0, but are pure floating-point noise rather than a meaningful signal.
    relative_tolerance = 1e-8
    if resid_i.std(ddof=1) <= relative_tolerance * (values[:, i].std(ddof=1)):
        raise ValueError(
            f"column {i}'s residual variance is ~zero after conditioning (perfect collinearity); "
            "partial correlation is undefined"
        )
    if resid_j.std(ddof=1) <= relative_tolerance * (values[:, j].std(ddof=1)):
        raise ValueError(
            f"column {j}'s residual variance is ~zero after conditioning (perfect collinearity); "
            "partial correlation is undefined"
        )
    r = float(np.corrcoef(resid_i, resid_j)[0, 1])
    if not np.isfinite(r):
        raise ValueError("partial correlation is undefined for this input (non-finite result)")
    r = float(np.clip(r, -1.0 + 1e-12, 1.0 - 1e-12))
    z = float(np.arctanh(r) * np.sqrt(degrees_of_freedom))
    p_value = float(2.0 * norm.sf(abs(z)))
    return PartialCorrelationEvidence(r, z, p_value)


def prune_pair(data: np.ndarray, i: int, j: int, conditioning: Sequence[int], alpha: float) -> bool:
    """Retain the edge (i, j) if its conditional-independence test rejects at alpha."""
    if not np.isscalar(alpha) or not (0.0 < float(alpha) < 1.0):
        raise ValueError("alpha must satisfy 0 < alpha < 1")
    evidence = compute_partial_correlation_evidence(data, i, j, conditioning)
    return evidence.p_value <= float(alpha)
