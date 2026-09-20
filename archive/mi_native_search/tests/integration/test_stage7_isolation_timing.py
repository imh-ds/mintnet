from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7_isolation_timing import (
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage7_timing,
)

_SMOKE_CONFIG = Path("configs/stage7_isolation_timing_smoke.yaml")


def test_stage7_timing_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7_timing(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["motif"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()
    assert (raw["wall_seconds"] > 0).all()


def test_stage7_timing_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage7_timing(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage7_timing(
        config, tmp_path / "shard", motifs=("hub",), sample_sizes=(300,), replicates=(1,), write_report=False
    )

    expected = unsharded.loc[
        (unsharded["motif"] == "hub") & (unsharded["n"] == 300) & (unsharded["replicate"] == 1)
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    # wall_seconds is a timing measurement, not deterministic output --
    # everything else (in particular n_significance_tests, the proxy
    # for whether the same computation actually ran) must match exactly.
    pd.testing.assert_frame_equal(expected.drop(columns="wall_seconds"), actual.drop(columns="wall_seconds"))


def test_stage7_timing_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage7_timing(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for motif in config.motifs:
        for n in config.sample_sizes:
            for replicate in range(config.replicates):
                run_stage7_timing(
                    config, shards_dir / f"shard_{shard_index}",
                    motifs=(motif,), sample_sizes=(n,), replicates=(replicate,), write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage7_isolation_timing", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["motif", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="wall_seconds"), aggregated_sorted.drop(columns="wall_seconds")
    )
    assert (aggregated_dir / "timing_report.md").is_file()
