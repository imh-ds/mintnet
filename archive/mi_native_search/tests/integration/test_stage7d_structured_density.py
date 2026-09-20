from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7d_structured_density import (
    Stage7dStructuredDensityConfig,
    all_shard_labels,
    condition_label,
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage7d_structured_density,
)

_SMOKE_CONFIG = Path("configs/stage7d_structured_density_smoke.yaml")


def test_stage7d_structured_density_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7d_structured_density(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["degree"], raw["condition"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_shard_label_round_trips() -> None:
    from mintnet.experiments.stage7d_structured_density import _parse_shard_label

    assert condition_label(2, "linear_0.08") == "deg2__linear_0.08"
    assert _parse_shard_label("deg2__linear_0.08") == (2, "linear_0.08")
    assert _parse_shard_label(condition_label(4, "ushape_0.0")) == (4, "ushape_0.0")


def test_stage7d_structured_density_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage7d_structured_density(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage7d_structured_density(
        config, tmp_path / "shard",
        shard_labels=(condition_label(1, "linear_0.08"),), sample_sizes=(150,), batches=(0,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["degree"] == 1) & (unsharded["condition"] == "linear_0.08")
        & (unsharded["n"] == 150) & (unsharded["replicate"].isin([0, 1]))
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage7d_structured_density_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage7d_structured_density(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for label in all_shard_labels(config):
        for n in config.sample_sizes:
            for batch in (0, 1):
                run_stage7d_structured_density(
                    config, shards_dir / f"shard_{shard_index}",
                    shard_labels=(label,), sample_sizes=(n,), batches=(batch,), write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate(
        "mintnet.experiments.stage7d_structured_density", _SMOKE_CONFIG, shards_dir, aggregated_dir
    )

    dedup_columns = ["degree", "condition", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "stage7d_structured_density_report.md").is_file()
