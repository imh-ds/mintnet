from pathlib import Path

import pandas as pd

from mintnet.experiments.stage8h_overconditioning_diagnosis import (
    DECOY_COUNTS,
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage8h,
)

_SMOKE_CONFIG = Path("configs/stage8h_overconditioning_diagnosis_smoke.yaml")


def test_stage8h_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage8h(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["decoy_count"], raw["n"], raw["strength"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_stage8h_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage8h(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage8h(
        config, tmp_path / "shard",
        decoy_counts=(1,), sample_sizes=(300,), strengths=(0.3,), batches=(0,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["decoy_count"] == 1) & (unsharded["n"] == 300) & (unsharded["strength"] == 0.3)
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage8h_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage8h(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for decoy_count in DECOY_COUNTS:
        for n in config.sample_sizes:
            for strength in config.strengths:
                run_stage8h(
                    config, shards_dir / f"shard_{shard_index}",
                    decoy_counts=(decoy_count,), sample_sizes=(n,), strengths=(strength,), batches=(0,),
                    write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate(
        "mintnet.experiments.stage8h_overconditioning_diagnosis", _SMOKE_CONFIG, shards_dir, aggregated_dir
    )

    dedup_columns = ["decoy_count", "n", "strength", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "h4_verdict.json").is_file()
    assert (aggregated_dir / "h5_verdict.json").is_file()
    assert (aggregated_dir / "rejection_rate_table.csv").is_file()
