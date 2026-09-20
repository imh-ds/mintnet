from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7c_retune import (
    all_conditions,
    condition_label,
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage7c,
)

_SMOKE_CONFIG = Path("configs/stage7c_retune_smoke.yaml")


def test_stage7c_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7c(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["k_cmi"], raw["target_rho"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_condition_label_round_trips() -> None:
    from mintnet.experiments.stage7c_retune import _parse_condition

    assert condition_label(100, 0.08) == "k100_rho0.08"
    assert _parse_condition("k100_rho0.08") == (100, 0.08)
    assert _parse_condition(condition_label(10, 0.0)) == (10, 0.0)


def test_stage7c_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage7c(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage7c(
        config, tmp_path / "shard",
        conditions=(condition_label(40, 0.08),), sample_sizes=(300,), batches=(0,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["k_cmi"] == 40) & (unsharded["target_rho"] == 0.08)
        & (unsharded["n"] == 300) & (unsharded["replicate"].isin([0, 1]))
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage7c_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage7c(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for condition in all_conditions(config):
        for n in config.sample_sizes:
            for batch in (0, 1):
                run_stage7c(
                    config, shards_dir / f"shard_{shard_index}",
                    conditions=(condition,), sample_sizes=(n,), batches=(batch,), write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage7c_retune", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["k_cmi", "target_rho", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "stage7c_report.md").is_file()
