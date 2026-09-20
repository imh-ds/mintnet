from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7h_composed import (
    _conditions,
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage7h,
)

_SMOKE_CONFIG = Path("configs/stage7h_composed_smoke.yaml")


def test_stage7h_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7h(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["condition"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_stage7h_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage7h(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage7h(
        config, tmp_path / "shard",
        conditions=("overlap_0",), sample_sizes=(750,), batches=(0,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["condition"] == "overlap_0") & (unsharded["n"] == 750)
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage7h_aggregate_shards_reproduces_unsharded_evidence(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage7h(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for condition in _conditions(config):
        for n in config.sample_sizes:
            run_stage7h(
                config, shards_dir / f"shard_{shard_index}",
                conditions=(condition,), sample_sizes=(n,), batches=(0,), write_report=False,
            )
            shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage7h_composed", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["condition", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "stratified_accuracy_table.csv").is_file()
    assert (aggregated_dir / "confidence_transfer_table.csv").is_file()
    assert (aggregated_dir / "decision.json").is_file()
