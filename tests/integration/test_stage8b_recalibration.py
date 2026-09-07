from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage8b_recalibration import load_config, run_stage8b

_CONFIG = Path("configs/stage8b_recalibration.yaml")


def _synthetic_raw_metrics(tmp_path: Path) -> Path:
    """Mirrors Stage 8a's own raw_metrics.csv shape closely enough for
    run_stage8b's own pipeline, with chain/fork built to reproduce
    D-066's own flat-accuracy-below-0.9 pattern and triangle built
    already well-calibrated -- so the gate has something real to
    distinguish."""
    rng = np.random.default_rng(0)
    rows = []
    for motif in ("chain", "fork"):
        for replicate in range(5000):
            margin = rng.uniform(0.0, 1.0)
            # Flat ~0.9 accuracy below 0.9 margin, matching D-066 at N=3000.
            correct = 1.0 if margin >= 0.9 else float(rng.uniform() < 0.9)
            rows.append(
                {"condition": f"{motif}_0.5", "n": 3000, "replicate": replicate, "margin": margin,
                 "correct": correct, "status": "ok", "error": ""}
            )
    for replicate in range(5000):
        margin = rng.uniform(0.9, 1.0)  # triangle: already well-calibrated, high-margin-dominated
        correct = float(rng.uniform() < margin)
        rows.append(
            {"condition": "triangle_strong", "n": 3000, "replicate": replicate, "margin": margin,
             "correct": correct, "status": "ok", "error": ""}
        )
    raw = pd.DataFrame(rows)
    path = tmp_path / "raw_metrics.csv"
    raw.to_csv(path, index=False)
    return path


def test_run_stage8b_proceeds_when_recalibration_fixes_the_flat_region(tmp_path: Path) -> None:
    raw_path = _synthetic_raw_metrics(tmp_path)
    config = load_config(_CONFIG)

    raw, decision = run_stage8b(raw_path, config, tmp_path / "output")

    assert decision.status == "PROCEED"
    assert decision.max_gated_ece <= config.ece_tolerance
    assert (tmp_path / "output" / "calibration_curves.json").is_file()
    assert (tmp_path / "output" / "validation_bin_table.csv").is_file()
    assert (tmp_path / "output" / "decision.json").is_file()


def test_run_stage8b_recalibrated_curve_tracks_the_flat_region_correctly() -> None:
    """Direct check that the fitted curve for chain at n=3000 reads
    close to the true underlying accuracy at both a low and a high
    margin -- not just that the aggregate ECE gate passed."""
    import tempfile

    rng = np.random.default_rng(1)
    rows = []
    for replicate in range(5000):
        margin = rng.uniform(0.0, 1.0)
        correct = 1.0 if margin >= 0.9 else float(rng.uniform() < 0.9)
        rows.append({"condition": "chain_0.5", "n": 3000, "replicate": replicate, "margin": margin, "correct": correct, "status": "ok"})
    raw = pd.DataFrame(rows)

    from mintnet.confidence.recalibration import calibrated_margin, fit_calibration_curves

    curves = fit_calibration_curves(raw, development_replicates=(0, 2499))
    low_margin_estimate = calibrated_margin(0.1, 3000, "chain", curves)
    high_margin_estimate = calibrated_margin(0.95, 3000, "chain", curves)

    assert 0.8 < low_margin_estimate < 1.0  # should read ~0.9, not ~0.1
    assert 0.9 < high_margin_estimate <= 1.0
