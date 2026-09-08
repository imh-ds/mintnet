import json
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage8e_recalibration_validation import load_config, run_stage8e

_CONFIG = Path("configs/stage8e_recalibration_validation.yaml")


def _synthetic_stage8c_raw(tmp_path: Path) -> Path:
    """Mirrors Stage 8c's own raw_metrics.csv shape (one row per
    replicate, edges embedded as JSON), with the false edge built to
    reproduce D-068's own composed-tier reversal so this charter's own
    gate has something real to fix and confirm."""
    rng = np.random.default_rng(0)
    rows = []
    for dgp in ("chain_fork_hub", "overlap"):
        for replicate in range(2000):
            margin = rng.uniform(0.0, 1.0)
            correct = 1.0 if margin < 0.9 else float(rng.uniform() < 0.3)  # D-068's own reversal shape
            edges = [
                {"i": 0, "j": 1, "is_true_edge": False, "decisive_p_value": 0.5, "margin": margin,
                 "retained": not bool(correct), "correct": bool(correct)}
            ]
            rows.append(
                {"dgp": dgp, "n": 750, "replicate": replicate, "edges_json": json.dumps(edges), "status": "ok"}
            )
    raw = pd.DataFrame(rows)
    path = tmp_path / "raw_metrics.csv"
    raw.to_csv(path, index=False)
    return path


def test_run_stage8e_proceeds_when_recalibration_fixes_the_composed_tier_reversal(tmp_path: Path) -> None:
    raw_path = _synthetic_stage8c_raw(tmp_path)
    config = load_config(_CONFIG)

    decision, curves = run_stage8e(raw_path, config, tmp_path / "output")

    assert decision.status == "PROCEED"
    assert decision.max_ece <= config.ece_tolerance
    assert ("chain_fork_hub", 750) in curves
    assert ("overlap", 750) in curves
    assert (tmp_path / "output" / "composed_false_edge_curves.json").is_file()
    assert (tmp_path / "output" / "validation_bin_table.csv").is_file()
    assert (tmp_path / "output" / "decision.json").is_file()
