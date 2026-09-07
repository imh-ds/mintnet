"""Fits the repaired alpha(N) formula for Stage 4i, per docs/stage4i_charter.md.

Reuses Stage 4g's own fitting selection rule and thresholds
(`mintnet.experiments.stage4g_fit`) unmodified, except `N=750` is
removed from the fitting set here -- moved to Stage 4i's held-out
validation set instead, the specific repair D-037 called for.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1j_fit import FittedForm
from mintnet.experiments.stage4e_reporting import _pooled_metrics
from mintnet.experiments.stage4g_fit import (
    FITTING_ALPHAS,
    _DEVELOPMENT_BOUNDS,
    _MAXIMUM_TRUE_EDGE_FPR,
    _MINIMUM_CANDIDACY_RATE,
)

# Stage 4g's own six fitting N with 750 removed -- 750 becomes a held-out
# validation point instead, per docs/stage4i_charter.md's repair procedure.
FITTING_SAMPLE_SIZES: tuple[int, ...] = (300, 500, 600, 650, 700)


def compute_fitting_points(stage4e_raw_path: Path) -> tuple[tuple[float, float], ...]:
    """Identical selection rule to `stage4g_fit.compute_fitting_points`
    (argmax conditional_accuracy on development replicates, subject to
    true-edge FPR `<= .10` and candidacy rate `>= .80`), evaluated over
    the five-point fitting set with `N=750` removed."""
    raw = pd.read_csv(stage4e_raw_path)
    development = raw.loc[raw["replicate"].between(*_DEVELOPMENT_BOUNDS)]

    points: list[tuple[float, float]] = []
    for n in FITTING_SAMPLE_SIZES:
        best_alpha: float | None = None
        best_accuracy = -1.0
        for alpha in FITTING_ALPHAS:
            metrics = _pooled_metrics(development, n, alpha)
            if metrics is None:
                continue
            candidacy, accuracy, fpr = metrics
            if accuracy is None or fpr > _MAXIMUM_TRUE_EDGE_FPR or candidacy < _MINIMUM_CANDIDACY_RATE:
                continue
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_alpha = alpha
        if best_alpha is None:
            raise ValueError(f"no eligible alpha found for N={n} in Stage 4e's fitting data")
        points.append((float(n), float(best_alpha)))
    return tuple(points)


def fitting_point_self_check(
    selected: FittedForm, fitting_points: tuple[tuple[float, float], ...]
) -> tuple[dict[str, object], ...]:
    """Confirm the refit formula predicts a valid probability, `0 < alpha
    < 1`, at every one of its own fitting N -- the safeguard this charter
    exists to add. D-037 found Stage 4g's formula failed exactly this
    check at one of its own fitting points (`N=750`), never caught
    because Stage 4g's validation only ever checked points strictly
    between fitting points, not the fitting points themselves."""
    results: list[dict[str, object]] = []
    for n, alpha_star in fitting_points:
        alpha_hat = selected.predict(n)
        results.append(
            {
                "n": n,
                "alpha_star": alpha_star,
                "alpha_hat": alpha_hat,
                "valid": bool(0.0 < alpha_hat < 1.0),
            }
        )
    return tuple(results)
