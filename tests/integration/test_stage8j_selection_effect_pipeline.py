from pathlib import Path

import pandas as pd

from mintnet.experiments.stage8j_selection_effect_diagnosis import (
    CONDITIONS,
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage8j,
)

_SMOKE_CONFIG = Path("configs/stage8j_selection_effect_diagnosis_smoke.yaml")


def test_stage8j_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage8j(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["condition"], raw["k"], raw["n"], raw["strength"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_stage8j_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage8j(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage8j(
        config, tmp_path / "shard",
        conditions=("selected_decoy",), pool_sizes=(5,), sample_sizes=(300,), strengths=(0.3,), batches=(0,),
        write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["condition"] == "selected_decoy")
        & (unsharded["k"] == 5)
        & (unsharded["n"] == 300)
        & (unsharded["strength"] == 0.3)
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage8j_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage8j(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for condition in CONDITIONS:
        for k in config.pool_sizes:
            for n in config.sample_sizes:
                for strength in config.strengths:
                    run_stage8j(
                        config, shards_dir / f"shard_{shard_index}",
                        conditions=(condition,), pool_sizes=(k,), sample_sizes=(n,), strengths=(strength,),
                        batches=(0,), write_report=False,
                    )
                    shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate(
        "mintnet.experiments.stage8j_selection_effect_diagnosis", _SMOKE_CONFIG, shards_dir, aggregated_dir
    )

    dedup_columns = ["condition", "k", "n", "strength", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "h7_verdict.json").is_file()
    assert (aggregated_dir / "h8_verdict.json").is_file()
    assert (aggregated_dir / "rejection_rate_table.csv").is_file()
