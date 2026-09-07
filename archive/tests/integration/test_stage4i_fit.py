from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage4g_fit import FITTING_ALPHAS
from mintnet.experiments.stage4i_fit import FITTING_SAMPLE_SIZES, compute_fitting_points, fitting_point_self_check


def _write_monotonic_tradeoff_csv(tmp_path: Path) -> Path:
    """Synthetic Stage 4e evidence, per test_stage4g_fit.py's own
    precedent: at every N, candidacy strictly decreases and
    conditional_accuracy strictly increases as alpha shrinks. The
    crossing point shifts by N (per test_stage4g_runner.py's own
    precedent) so the fitting points are not all identical -- an
    all-identical fitting curve makes R^2 divide by zero."""
    offset_by_n = {300: 0, 500: 1, 600: 1, 650: 2, 700: 2, 750: 3}
    rows = []
    for n in (300, 500, 600, 650, 700, 750):  # includes 750 -- Stage 4e's own real grid
        offset = offset_by_n[n]
        for rank, alpha in enumerate(sorted(FITTING_ALPHAS, reverse=True)):
            effective_rank = max(0, rank - offset)
            candidacy_fraction = 1.0 - effective_rank * 0.11
            accuracy_fraction = 0.5 + effective_rank * 0.06
            for replicate in range(10):
                row = {
                    "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
                    "true_edge_prune_fpr": 0.0, "status": "ok", "error": "",
                }
                for label in ("03", "04", "13", "14"):
                    is_candidate = (replicate / 10.0) < candidacy_fraction
                    row[f"candidate_{label}"] = is_candidate
                    row[f"correctly_pruned_{label}"] = (
                        ((replicate * 7) % 10) / 10.0 < accuracy_fraction if is_candidate else np.nan
                    )
                rows.append(row)
    path = tmp_path / "stage4e_raw_metrics.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_fitting_set_excludes_n_750() -> None:
    assert 750 not in FITTING_SAMPLE_SIZES
    assert set(FITTING_SAMPLE_SIZES) == {300, 500, 600, 650, 700}


def test_compute_fitting_points_never_uses_n_750(tmp_path: Path) -> None:
    path = _write_monotonic_tradeoff_csv(tmp_path)

    points = compute_fitting_points(path)

    assert len(points) == 5
    assert 750.0 not in {n for n, _alpha in points}


def test_fitting_point_self_check_flags_invalid_prediction() -> None:
    from mintnet.experiments.stage1j_fit import FittedForm

    # A form whose own prediction goes negative at one of its fitting
    # points -- reproduces D-037's failure mode directly against the
    # self-check this charter adds.
    form = FittedForm("linear_n", (1.0, -0.01), r_squared=0.99, n_parameters=2)
    fitting_points = ((50.0, 0.5), (200.0, -1.0))  # 200 -> 1.0 + (-0.01*200) = -1.0

    results = fitting_point_self_check(form, fitting_points)

    by_n = {r["n"]: r for r in results}
    assert by_n[50.0]["valid"] is True
    assert by_n[200.0]["valid"] is False


def test_fitting_point_self_check_passes_when_all_valid(tmp_path: Path) -> None:
    path = _write_monotonic_tradeoff_csv(tmp_path)
    points = compute_fitting_points(path)
    selected = select_form(fit_candidate_forms(points))

    results = fitting_point_self_check(selected, points)

    assert all(r["valid"] for r in results)
