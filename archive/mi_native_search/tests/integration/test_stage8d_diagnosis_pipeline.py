from pathlib import Path

import pandas as pd
import pytest

from mintnet.experiments.stage8c_composed_calibration import load_config, run_stage8c
from mintnet.experiments.stage8d_reversal_diagnosis import run_stage8d_diagnosis

_SMOKE_CONFIG = Path("configs/stage8c_composed_calibration_smoke.yaml")


def test_run_stage8d_diagnosis_wires_end_to_end_against_a_fresh_stage8c_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    stage8c_dir = tmp_path / "stage8c"
    run_stage8c(config, stage8c_dir, write_report=False)

    h1, h2 = run_stage8d_diagnosis(stage8c_dir / "raw_metrics.csv", tmp_path / "diagnosis")

    assert h1.status in ("CONFIRMED", "NOT_CONFIRMED", "INCONCLUSIVE")
    assert h2.status in ("CONFIRMED", "NOT_CONFIRMED", "INCONCLUSIVE")
    assert (tmp_path / "diagnosis" / "h1_cap_reached_table.csv").is_file()
    assert (tmp_path / "diagnosis" / "h2_conditioning_size_bins.csv").is_file()
    assert (tmp_path / "diagnosis" / "h1_verdict.json").is_file()
    assert (tmp_path / "diagnosis" / "h2_verdict.json").is_file()


def test_run_stage8d_diagnosis_raises_on_evidence_without_the_enrichment(tmp_path: Path) -> None:
    """Guards against silently running a diagnosis that means nothing
    -- pre-enrichment Stage 8c evidence (like D-068's own already-
    recorded raw_metrics.csv) has no cap_reached data at all."""
    import json

    old_edge = {"i": 0, "j": 1, "is_true_edge": False, "decisive_p_value": 0.5, "margin": 0.3, "retained": False, "correct": True}
    raw = pd.DataFrame(
        [{"dgp": "chain_fork_hub", "n": 750, "replicate": 0, "edges_json": json.dumps([old_edge]), "status": "ok"}]
    )
    raw_path = tmp_path / "old_raw_metrics.csv"
    raw.to_csv(raw_path, index=False)

    with pytest.raises(ValueError, match="predates Stage 8c's own"):
        run_stage8d_diagnosis(raw_path, tmp_path / "diagnosis")
