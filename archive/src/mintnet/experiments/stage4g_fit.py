"""Fits the alpha(N) formula for the sequential engine's overlap-shape
conditioning step, per docs/stage4g_charter.md.

Fitting points come entirely from Stage 4e's own already-generated raw
evidence (development replicates only) -- no simulation in this module.
Reuses Stage 1j's generic fitting machinery
(`mintnet.experiments.stage1j_fit.fit_candidate_forms`, `select_form`)
unmodified, parameterized on these new points instead of D-008-D-010's.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4e_reporting import _pooled_metrics

FITTING_SAMPLE_SIZES: tuple[int, ...] = (300, 500, 600, 650, 700, 750)
FITTING_ALPHAS: tuple[float, ...] = (0.5, 0.3, 0.2, 0.1, 0.05, 0.01, 0.005, 0.001, 0.0001)
_DEVELOPMENT_BOUNDS: tuple[int, int] = (0, 999)
_MAXIMUM_TRUE_EDGE_FPR = 0.10
_MINIMUM_CANDIDACY_RATE = 0.80


def compute_fitting_points(stage4e_raw_path: Path) -> tuple[tuple[float, float], ...]:
    """For each fitting N, select the alpha (from Stage 4e's own grid) that
    maximizes conditional_accuracy on development replicates, subject to
    true-edge FPR staying within the established .10 ceiling **and
    candidacy rate staying at or above .80**.

    The candidacy floor is a correction found during implementation, not
    present in docs/stage4g_charter.md's own text: conditional_accuracy is
    monotonically non-decreasing as alpha shrinks (a stricter test is
    mechanically less likely to call anything "significant"), while
    candidacy rate is monotonically non-increasing -- an unconstrained
    argmax therefore always degenerates to the single strictest alpha in
    the grid, at every N, which is not a meaningful "best" alpha (it
    would push nearly every cross-branch pair back into the D-032
    non-detection regime this whole diagnostic line exists to avoid).
    Requiring a minimum candidacy rate, matching this project's standard
    .80 threshold convention, keeps the fitting target meaningful: the
    best-performing alpha among those that still let a reasonable
    majority of cross-branch pairs actually be evaluated.

    This is a different selection rule than Stage 4b/4d/4e's own
    "largest eligible above both margins" -- that rule picks the most
    permissive alpha clearing a floor, not the best-performing one, and is
    not the right target for fitting a curve either.
    """
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
