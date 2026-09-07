from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4g_fit import FITTING_ALPHAS, FITTING_SAMPLE_SIZES, compute_fitting_points


def _write_monotonic_tradeoff_csv(tmp_path: Path) -> Path:
    """Synthetic Stage 4e evidence where, at every N, candidacy strictly
    decreases and conditional_accuracy strictly increases as alpha shrinks
    -- the realistic tradeoff shape that makes an unconstrained argmax
    degenerate to the smallest alpha, and that the .80 candidacy floor
    must resolve."""
    rows = []
    for n in FITTING_SAMPLE_SIZES:
        for rank, alpha in enumerate(sorted(FITTING_ALPHAS, reverse=True)):
            # rank 0 = largest alpha = highest candidacy, lowest accuracy.
            candidacy_fraction = 1.0 - rank * 0.11  # spans ~1.0 down to ~0.0
            accuracy_fraction = 0.5 + rank * 0.06  # spans ~0.5 up to ~1.0
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


def test_compute_fitting_points_respects_candidacy_floor_not_pure_argmax(tmp_path: Path) -> None:
    path = _write_monotonic_tradeoff_csv(tmp_path)

    points = compute_fitting_points(path)

    assert len(points) == len(FITTING_SAMPLE_SIZES)
    # None of the selected alphas should be the single strictest grid value
    # (0.0001) at every N -- that would indicate the unconstrained-argmax
    # degeneracy this floor exists to prevent.
    selected_alphas = {alpha for _n, alpha in points}
    assert selected_alphas != {0.0001}


def test_compute_fitting_points_raises_when_nothing_clears_the_floor(tmp_path: Path) -> None:
    import pytest

    rows = []
    for n in FITTING_SAMPLE_SIZES:
        for alpha in FITTING_ALPHAS:
            for replicate in range(4):
                row = {
                    "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
                    "true_edge_prune_fpr": 0.0, "status": "ok", "error": "",
                }
                for label in ("03", "04", "13", "14"):
                    row[f"candidate_{label}"] = False  # candidacy always 0.0
                    row[f"correctly_pruned_{label}"] = np.nan
                rows.append(row)
    path = tmp_path / "stage4e_raw_metrics.csv"
    pd.DataFrame(rows).to_csv(path, index=False)

    with pytest.raises(ValueError):
        compute_fitting_points(path)
