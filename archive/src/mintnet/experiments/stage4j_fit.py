"""Fits the densely-supported alpha(N) formula for Stage 4j, per
docs/stage4j_charter.md.

D-038 (Stage 4i) found that removing N=750 from the fitting set
relocates the formula's zero-crossing rather than closing it -- a
sample-density problem near the crossing, not a fitting-target problem.
This module fits on ten points: six reused verbatim from Stage 4e's own
evidence (300, 500, 600, 650, 700, 750) plus four new, densely-spaced
points inside the gap (710, 720, 730, 740) freshly simulated by
`mintnet.experiments.stage4j.run_dense_fitting_simulation`.
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

# The six coarse/boundary points reused verbatim from Stage 4e's own
# evidence, plus four new points densely spaced inside the N=700-750 gap.
COARSE_SAMPLE_SIZES: tuple[int, ...] = (300, 500, 600, 650, 700, 750)
DENSE_SAMPLE_SIZES: tuple[int, ...] = (710, 720, 730, 740)
FITTING_SAMPLE_SIZES: tuple[int, ...] = tuple(sorted(COARSE_SAMPLE_SIZES + DENSE_SAMPLE_SIZES))


def _select_alpha_star(development: pd.DataFrame, n: int) -> float:
    """Identical selection rule to `stage4g_fit.compute_fitting_points`
    (argmax conditional_accuracy subject to true-edge FPR `<= .10` and
    candidacy rate `>= .80`), factored out to apply to any development
    partition -- reused here for both Stage 4e's existing data and this
    charter's own freshly-simulated dense points."""
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
        raise ValueError(f"no eligible alpha found for N={n} in the supplied fitting data")
    return best_alpha


def compute_fitting_points(stage4e_raw_path: Path, dense_raw_path: Path) -> tuple[tuple[float, float], ...]:
    """Ten-point fitting set: six coarse/boundary points from Stage 4e's
    own already-generated evidence (no new simulation), plus four dense
    points from this charter's own fresh simulation inside [700, 750]."""
    stage4e_raw = pd.read_csv(stage4e_raw_path)
    stage4e_development = stage4e_raw.loc[stage4e_raw["replicate"].between(*_DEVELOPMENT_BOUNDS)]
    dense_raw = pd.read_csv(dense_raw_path)
    dense_development = dense_raw.loc[dense_raw["replicate"].between(*_DEVELOPMENT_BOUNDS)]

    points: list[tuple[float, float]] = []
    for n in COARSE_SAMPLE_SIZES:
        points.append((float(n), _select_alpha_star(stage4e_development, n)))
    for n in DENSE_SAMPLE_SIZES:
        points.append((float(n), _select_alpha_star(dense_development, n)))
    return tuple(sorted(points))


def fitting_point_self_check(
    selected: FittedForm, fitting_points: tuple[tuple[float, float], ...]
) -> tuple[dict[str, object], ...]:
    """Confirm the refit formula returns a valid probability, `0 < alpha
    < 1`, at every one of its own ten fitting N -- carried forward from
    Stage 4i's own safeguard, applied here to the larger fitting set."""
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
