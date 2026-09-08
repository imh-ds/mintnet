from pathlib import Path

import pandas as pd

from mintnet.experiments.stage9a_bootstrap_stability import (
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage9a,
)

_SMOKE_CONFIG = Path("configs/stage9a_bootstrap_stability_smoke.yaml")


def test_stage9a_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage9a(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["dgp"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_stage9a_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage9a(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage9a(config, tmp_path / "shard", dgps=("overlap",), sample_sizes=(1000,), write_report=False)

    expected = unsharded.loc[(unsharded["dgp"] == "overlap") & (unsharded["n"] == 1000)].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage9a_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage9a(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for dgp in ("chain_fork_hub", "overlap"):
        for n in config.sample_sizes:
            run_stage9a(
                config, shards_dir / f"shard_{shard_index}", dgps=(dgp,), sample_sizes=(n,), write_report=False
            )
            shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage9a_bootstrap_stability", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["dgp", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "h9_verdict.json").is_file()
    assert (aggregated_dir / "pi_final_summary.csv").is_file()
    assert (aggregated_dir / "exploded_qualifying.csv").is_file()
