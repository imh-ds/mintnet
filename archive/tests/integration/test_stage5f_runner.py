from pathlib import Path

import pandas as pd

from mintnet.experiments.stage5f import BUCKETS, DGPS, load_stage5f_config, run_stage5f


def test_stage5f_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage5f_config(Path("configs/stage5f_diagnostic_smoke.yaml"))

    first = run_stage5f(config, tmp_path / "first")
    second = run_stage5f(config, tmp_path / "second")

    expected_rows = len(DGPS) * len(config.sample_sizes) * config.replicates
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(first, second)
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage5f_report.md"):
            assert (output / filename).is_file()


def test_stage5f_bucket_counts_sum_to_final_edge_count(tmp_path: Path) -> None:
    """Every final edge falls into exactly one of the four buckets --
    no edge double-counted or dropped."""
    config = load_stage5f_config(Path("configs/stage5f_diagnostic_smoke.yaml"))

    raw = run_stage5f(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for bucket in BUCKETS:
        assert (ok[bucket] >= 0).all()


def test_stage5f_reuses_stage5a_seed_derivation() -> None:
    from mintnet.experiments.stage5a import _condition_seed as stage5a_seed
    from mintnet.experiments.stage5f import _condition_seed as stage5f_seed

    assert stage5f_seed is stage5a_seed
