from pathlib import Path

import pandas as pd

from mintnet.experiments.stage0 import load_stage0_config, run_stage0


def test_stage0_runner_is_reproducible_and_captures_evidence(tmp_path: Path) -> None:
    """Changing seed derivation or evidence writes would make a run irreproducible."""
    config_path = Path("configs/stage0_gaussian_smoke.yaml")
    config = load_stage0_config(config_path)

    first = run_stage0(config, tmp_path / "first")
    second = run_stage0(config, tmp_path / "second")

    expected_rows = 2 * 2 * 2 * 3
    assert len(first) == expected_rows
    assert first["status"].eq("ok").all()
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in (
            "raw_metrics.csv",
            "resolved_config.yaml",
            "metadata.json",
            "aggregate_metrics.csv",
            "decision.json",
            "stage0_report.md",
        ):
            assert (output / filename).is_file()
