from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7_isolation import (
    CONDITIONS,
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage7_isolation,
)

_SMOKE_CONFIG = Path("configs/stage7_isolation_smoke.yaml")


def test_stage7_isolation_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7_isolation(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["motif"], raw["strength_index"], raw["n"], raw["replicate"], raw["alpha"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_stage7_isolation_recovers_chain_and_triangle_structure_at_a_lenient_alpha(tmp_path: Path) -> None:
    """Weak evidence, not the frozen gate (too few replicates/permutations
    at smoke scale) -- just confirms the wiring produces sane decisions
    at a lenient alpha: chain's indirect pair mostly pruned, triangle's
    three genuine edges mostly retained."""
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7_isolation(config, tmp_path / "evidence", write_report=False)

    chain_lenient = raw.loc[(raw["motif"] == "chain") & (raw["alpha"] == 0.05)]
    assert chain_lenient["indirect_prune_tpr"].mean() > 0.5

    triangle_lenient = raw.loc[(raw["motif"] == "triangle") & (raw["alpha"] == 0.50)]
    assert triangle_lenient["true_edge_prune_fpr"].mean() < 0.5


def test_stage7_isolation_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage7_isolation(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage7_isolation(
        config, tmp_path / "shard",
        conditions=("triangle_1",), sample_sizes=(300,), batches=(0,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["motif"] == "triangle") & (unsharded["strength_index"] == 1)
        & (unsharded["n"] == 300) & (unsharded["replicate"].isin([0, 1]))
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage7_isolation_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage7_isolation(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for condition in CONDITIONS:
        for n in config.sample_sizes:
            for batch in (0, 1):
                run_stage7_isolation(
                    config, shards_dir / f"shard_{shard_index}",
                    conditions=(condition,), sample_sizes=(n,), batches=(batch,), write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage7_isolation", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["motif", "strength_index", "n", "replicate", "alpha"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "stage7_isolation_report.md").is_file()
