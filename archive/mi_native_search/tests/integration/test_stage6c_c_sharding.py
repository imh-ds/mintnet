from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6c import run_stage_c
from mintnet.experiments.stage6c_c import expected_combinations, expected_row_count, load_config

_SMOKE_CONFIG = Path("configs/stage6c_null_calibration_smoke.yaml")


def test_stage6c_c_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage_c(config, tmp_path / "evidence", max_workers=1, write_report=False)

    combos = set(zip(raw["label"], raw["n"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)


def test_stage6c_c_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage_c(config, tmp_path / "unsharded", max_workers=1, write_report=False)
    shard = run_stage_c(
        config, tmp_path / "shard", max_workers=1, labels=("s1_alt",), sample_sizes=(300,), write_report=False
    )

    expected = unsharded.loc[(unsharded["label"] == "s1_alt") & (unsharded["n"] == 300)].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected, actual)


def test_stage6c_c_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage_c(config, unsharded_dir, max_workers=1)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for label in ("s0_alt", "s1_alt", "s2_alt", "s3_alt"):
        for n in config.sample_sizes:
            run_stage_c(
                config, shards_dir / f"shard_{shard_index}", max_workers=1,
                labels=(label,), sample_sizes=(n,), write_report=False,
            )
            shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage6c_c", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["label", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(unsharded_sorted, aggregated_sorted)
    assert (aggregated_dir / "stage_c_report.md").is_file()
