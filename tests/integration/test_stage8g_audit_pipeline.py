import json
from pathlib import Path

import pandas as pd
import pytest

from mintnet.experiments.stage8c_composed_calibration import load_config, run_stage8c
from mintnet.experiments.stage8g_structural_audit import run_stage8g_audit

_SMOKE_CONFIG = Path("configs/stage8c_composed_calibration_smoke.yaml")


def test_run_stage8g_audit_wires_end_to_end_against_a_fresh_stage8c_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    stage8c_dir = tmp_path / "stage8c"
    run_stage8c(config, stage8c_dir, write_report=False)

    h3, step5 = run_stage8g_audit(stage8c_dir / "raw_metrics.csv", tmp_path / "audit")

    assert h3.status in ("CONFIRMED", "NOT_CONFIRMED", "INCONCLUSIVE")
    assert step5.status in ("CLEAN", "FLAGGED")
    assert (tmp_path / "audit" / "h3_wrong_retention_table.csv").is_file()
    assert (tmp_path / "audit" / "chance_correlation_candidates.csv").is_file()
    assert (tmp_path / "audit" / "h3_verdict.json").is_file()
    assert (tmp_path / "audit" / "step5_validity.json").is_file()


def test_run_stage8g_audit_raises_on_evidence_without_the_enrichment(tmp_path: Path) -> None:
    """Guards against silently auditing evidence that carries no
    decisive_conditioning_subset data at all (e.g. D-068's or D-069's
    own already-recorded raw_metrics.csv, predating Stage 8g)."""
    old_edge = {"i": 0, "j": 2, "is_true_edge": False, "decisive_p_value": 0.5, "margin": 0.3, "retained": True, "correct": False, "conditioning_size_used": 2, "cap_reached": False}
    raw = pd.DataFrame(
        [{"dgp": "chain_fork_hub", "n": 750, "alpha": 0.05, "replicate": 0, "seed": 1,
          "edges_json": json.dumps([old_edge]), "n_edges": 1, "elapsed_seconds": 0.001, "status": "ok", "error": ""}]
    )
    output_dir = tmp_path / "stage8c_old"
    output_dir.mkdir()
    raw_path = output_dir / "raw_metrics.csv"
    raw.to_csv(raw_path, index=False)
    (output_dir / "resolved_config.yaml").write_text("strength: 0.5\n", encoding="utf-8")

    with pytest.raises(ValueError, match="predates Stage 8c's own"):
        run_stage8g_audit(raw_path, tmp_path / "audit")
