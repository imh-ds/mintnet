from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6b import CONDITIONS, load_stage6b_config, run_stage6b


def test_stage6b_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage6b_config(Path("configs/stage6b_cmi_validation_smoke.yaml"))

    first = run_stage6b(config, tmp_path / "first", max_workers=1)
    second = run_stage6b(config, tmp_path / "second", max_workers=1)

    expected_rows = len(CONDITIONS) * len(config.sample_sizes) * config.replicates
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(first, second)
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage6b_report.md"):
            assert (output / filename).is_file()


def test_stage6b_null_and_alt_estimates_point_the_right_direction(tmp_path: Path) -> None:
    """Weak evidence, not a statistical gate (too few replicates at
    smoke scale) -- just confirms null conditions estimate near zero
    and alt conditions estimate materially positive, on average."""
    config = load_stage6b_config(Path("configs/stage6b_cmi_validation_smoke.yaml"))

    raw = run_stage6b(config, tmp_path / "evidence", max_workers=1)
    ok = raw.loc[raw["status"] == "ok"]

    for label in ("s0_null", "s1_null", "s2_null", "s3_null"):
        mean_estimate = ok.loc[ok["label"] == label, "estimate"].mean()
        assert abs(mean_estimate) < 0.2

    for label in ("s0_alt", "s1_alt", "s2_alt", "s3_alt"):
        mean_estimate = ok.loc[ok["label"] == label, "estimate"].mean()
        assert mean_estimate > 0.0
