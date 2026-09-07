from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage1j_fit import FittedForm, fit_candidate_forms, select_form
from mintnet.experiments.stage4g_fit import FITTING_ALPHAS
from mintnet.experiments.stage4j_fit import (
    COARSE_SAMPLE_SIZES,
    DENSE_SAMPLE_SIZES,
    FITTING_SAMPLE_SIZES,
    compute_fitting_points,
    fitting_point_self_check,
)


def _write_tradeoff_csv(path: Path, sample_sizes: tuple[int, ...], offset_by_n: dict[int, int]) -> None:
    """Synthetic Stage 4e-shaped evidence, per test_stage4i_fit.py's own
    precedent: at every N, candidacy strictly decreases and
    conditional_accuracy strictly increases as alpha shrinks, with the
    crossing point shifting by N so the fitting points are not all
    identical (an all-identical fitting curve makes R^2 divide by zero)."""
    ordered_alphas = sorted(FITTING_ALPHAS, reverse=True)
    rows = []
    for n in sample_sizes:
        offset = offset_by_n[n]
        for rank, alpha in enumerate(ordered_alphas):
            effective_rank = max(0, rank - offset)
            candidacy = max(0.0, 1.0 - effective_rank * 0.11)
            accuracy = min(1.0, 0.5 + effective_rank * 0.06)
            for replicate in range(10):
                candidate = (replicate / 10.0) < candidacy
                row = {
                    "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
                    "true_edge_prune_fpr": 0.0, "status": "ok", "error": "",
                }
                for label in ("03", "04", "13", "14"):
                    row[f"candidate_{label}"] = candidate
                    row[f"correctly_pruned_{label}"] = ((replicate * 3) % 10) / 10.0 < accuracy if candidate else np.nan
                rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    stage4e_offsets = {300: 0, 500: 1, 600: 1, 650: 2, 700: 2, 750: 3}
    dense_offsets = {710: 2, 720: 2, 730: 3, 740: 3}

    stage4e_path = tmp_path / "stage4e_raw_metrics.csv"
    dense_path = tmp_path / "dense_fitting_raw.csv"
    _write_tradeoff_csv(stage4e_path, COARSE_SAMPLE_SIZES, stage4e_offsets)
    _write_tradeoff_csv(dense_path, DENSE_SAMPLE_SIZES, dense_offsets)
    return stage4e_path, dense_path


def test_fitting_sample_sizes_are_ten_points_sorted() -> None:
    assert len(FITTING_SAMPLE_SIZES) == 10
    assert FITTING_SAMPLE_SIZES == tuple(sorted(FITTING_SAMPLE_SIZES))
    assert set(FITTING_SAMPLE_SIZES) == set(COARSE_SAMPLE_SIZES) | set(DENSE_SAMPLE_SIZES)


def test_compute_fitting_points_covers_all_ten_n(tmp_path: Path) -> None:
    stage4e_path, dense_path = _fixtures(tmp_path)

    points = compute_fitting_points(stage4e_path, dense_path)

    assert len(points) == 10
    assert {n for n, _alpha in points} == set(float(n) for n in FITTING_SAMPLE_SIZES)


def test_compute_fitting_points_reuses_coarse_and_simulates_dense(tmp_path: Path) -> None:
    stage4e_path, dense_path = _fixtures(tmp_path)

    points = compute_fitting_points(stage4e_path, dense_path)
    by_n = {n: alpha for n, alpha in points}

    for n in COARSE_SAMPLE_SIZES:
        assert float(n) in by_n
    for n in DENSE_SAMPLE_SIZES:
        assert float(n) in by_n


def test_fitting_point_self_check_flags_invalid_prediction() -> None:
    form = FittedForm("linear_n", (1.0, -0.01), r_squared=0.99, n_parameters=2)
    fitting_points = ((50.0, 0.5), (200.0, -1.0))  # 200 -> 1.0 + (-0.01*200) = -1.0

    results = fitting_point_self_check(form, fitting_points)

    by_n = {r["n"]: r for r in results}
    assert by_n[50.0]["valid"] is True
    assert by_n[200.0]["valid"] is False


def test_fitting_point_self_check_passes_when_all_valid(tmp_path: Path) -> None:
    stage4e_path, dense_path = _fixtures(tmp_path)
    points = compute_fitting_points(stage4e_path, dense_path)
    selected = select_form(fit_candidate_forms(points))

    results = fitting_point_self_check(selected, points)

    assert all(r["valid"] for r in results)
