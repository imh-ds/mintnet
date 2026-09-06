import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from stage7d_compare import compare  # noqa: E402

from mintnet.experiments.stage7d_cmiknn_baseline import load_config as load_baseline_config
from mintnet.experiments.stage7d_cmiknn_baseline import run_stage7d_cmiknn_baseline
from mintnet.experiments.stage7d_structured_density import load_config as load_structured_config
from mintnet.experiments.stage7d_structured_density import run_stage7d_structured_density

_STRUCTURED_SMOKE_CONFIG = Path("configs/stage7d_structured_density_smoke.yaml")
_BASELINE_SMOKE_CONFIG = Path("configs/stage7d_cmiknn_baseline_smoke.yaml")


def test_stage7d_compare_produces_a_report_from_two_smoke_scale_runs(tmp_path: Path) -> None:
    structured_config = load_structured_config(_STRUCTURED_SMOKE_CONFIG)
    baseline_config = load_baseline_config(_BASELINE_SMOKE_CONFIG)

    structured_dir = tmp_path / "structured"
    baseline_dir = tmp_path / "baseline"
    run_stage7d_structured_density(structured_config, structured_dir, write_report=False)
    run_stage7d_cmiknn_baseline(baseline_config, baseline_dir, write_report=False)

    output_dir = tmp_path / "comparison"
    compare(structured_dir, baseline_dir, _STRUCTURED_SMOKE_CONFIG, output_dir)

    assert (output_dir / "structured_density_detection_limits.csv").is_file()
    assert (output_dir / "cmiknn_baseline_detection_limits.csv").is_file()
    assert (output_dir / "ushape_power_comparison.csv").is_file()
    report = (output_dir / "stage7d_comparison_report.md").read_text(encoding="utf-8")
    assert "Head-to-Head Comparison" in report
    assert "Mandatory diagnostic" in report

    import json

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert "calibrated_degrees" in summary
    assert "ushape_power_comparison" in summary
