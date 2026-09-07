from pathlib import Path

import pandas as pd

from mintnet.experiments.stage8c_composed_calibration import (
    COMPOSED_SHAPES,
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage8c,
)

_SMOKE_CONFIG = Path("configs/stage8c_composed_calibration_smoke.yaml")


def test_stage8c_covers_every_expected_replicate_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage8c(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["dgp"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()
    assert (raw["n_edges"] > 0).all()  # both DGPs always produce at least one screened candidate


def test_stage8c_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage8c(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage8c(
        config, tmp_path / "shard",
        conditions=("overlap",), sample_sizes=(400,), batches=(0,), write_report=False,
    )

    expected = unsharded.loc[(unsharded["dgp"] == "overlap") & (unsharded["n"] == 400)].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage8c_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage8c(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for dgp in COMPOSED_SHAPES:
        for n in config.sample_sizes:
            run_stage8c(
                config, shards_dir / f"shard_{shard_index}",
                conditions=(dgp,), sample_sizes=(n,), batches=(0,), write_report=False,
            )
            shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage8c_composed_calibration", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["dgp", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "decision.json").is_file()
    assert (aggregated_dir / "exploded_edges.csv").is_file()
    assert (aggregated_dir / "exploratory_false_edge_recalibration_ece.json").is_file()
