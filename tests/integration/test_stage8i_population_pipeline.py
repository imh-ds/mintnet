from pathlib import Path

from mintnet.experiments.stage8c_composed_calibration import load_config, run_stage8c
from mintnet.experiments.stage8i_population_ground_truth import run_stage8i_audit

_SMOKE_CONFIG = Path("configs/stage8c_composed_calibration_smoke.yaml")


def test_run_stage8i_audit_wires_end_to_end_against_a_fresh_stage8c_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    stage8c_dir = tmp_path / "stage8c"
    run_stage8c(config, stage8c_dir, write_report=False)

    h6 = run_stage8i_audit(stage8c_dir / "raw_metrics.csv", tmp_path / "audit")

    assert h6.status in ("CONFIRMED", "NOT_CONFIRMED")
    assert (tmp_path / "audit" / "population_ground_truth.csv").is_file()
    assert (tmp_path / "audit" / "h6_verdict.json").is_file()


def test_run_stage8i_audit_finds_no_population_level_dependency_in_real_flagged_edges(tmp_path: Path) -> None:
    """The charter's own working expectation, checked against a real
    (if small, smoke-sized) Stage 8c run rather than only synthetic
    rows: every flagged edge's own population partial correlation
    should be indistinguishable from zero."""
    config = load_config(_SMOKE_CONFIG)
    stage8c_dir = tmp_path / "stage8c"
    run_stage8c(config, stage8c_dir, write_report=False)

    h6 = run_stage8i_audit(stage8c_dir / "raw_metrics.csv", tmp_path / "audit")
    assert h6.status == "NOT_CONFIRMED"
