from pathlib import Path

import pandas as pd

from mintnet.experiments.stage9c_bootstrap_rescue import (
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage9c,
)

_SMOKE_CONFIG = Path("configs/stage9c_bootstrap_rescue_smoke.yaml")


def test_stage9c_covers_every_expected_combination(tmp_path: Path) -> None:
    """chain_fork_hub only -- cheap at smoke scale (overlap qualifies at
    ~100% of replicates and pays the full bootstrap cost every time,
    confirmed manually during implementation; not worth the CI cost
    here since the bootstrap path itself is already covered by unit
    tests in test_bootstrap_stability.py/test_stability_rescue.py)."""
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage9c(config, tmp_path / "evidence", dgps=("chain_fork_hub",), write_report=False)

    combos = set(zip(raw["dgp"], raw["n"], raw["replicate"]))
    expected = {c for c in expected_combinations(config) if c[0] == "chain_fork_hub"}
    assert combos == expected
    assert len(raw) == len(expected)
    assert (raw["status"] == "ok").all()


def test_stage9c_replicate_range_restricts_to_exactly_that_range(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    chunk = run_stage9c(
        config, tmp_path / "chunk", dgps=("chain_fork_hub",), sample_sizes=(750,),
        replicate_range=(0, 2), write_report=False,
    )
    assert set(chunk["replicate"]) == {0, 1, 2}


def test_stage9c_replicate_range_caps_independently_per_chunk(tmp_path: Path) -> None:
    """Each replicate_range-restricted call gets its own FRESH cap
    budget (Stage 9b's own chunking semantics, not Stage 9a's own
    partition-preserving one) -- chaining chunks accumulates MORE
    bootstrapped instances in total, not a shared budget split."""
    config = load_config(_SMOKE_CONFIG)  # max_bootstrapped_replicates_per_cell=2
    first = run_stage9c(
        config, tmp_path / "a", dgps=("chain_fork_hub",), sample_sizes=(750,),
        replicate_range=(0, 4), write_report=False,
    )
    second = run_stage9c(
        config, tmp_path / "b", dgps=("chain_fork_hub",), sample_sizes=(750,),
        replicate_range=(0, 4), write_report=False,
    )
    columns = [c for c in first.columns if c != "elapsed_seconds"]
    pd.testing.assert_frame_equal(first[columns], second[columns])


def test_stage9c_aggregate_shards_reproduces_unsharded_evidence(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage9c(config, unsharded_dir, dgps=("chain_fork_hub",))

    shards_dir = tmp_path / "shards"
    for n in config.sample_sizes:
        run_stage9c(
            config, shards_dir / f"shard_{n}", dgps=("chain_fork_hub",), sample_sizes=(n,), write_report=False,
        )

    aggregated_dir = tmp_path / "aggregated"
    # expected_row_count/expected_combinations assume the full config
    # dgp grid (both chain_fork_hub and overlap) -- this dispatch is
    # deliberately restricted to chain_fork_hub only, so aggregate
    # locally without the generic script's own full-grid validation,
    # mirroring D-078's own recovery precedent.
    raw = pd.concat(
        (pd.read_csv(shards_dir / f"shard_{n}" / "raw_metrics.csv") for n in config.sample_sizes),
        ignore_index=True,
    )
    aggregated_dir.mkdir(parents=True)
    raw.to_csv(aggregated_dir / "raw_metrics.csv", index=False)
    from mintnet.experiments.stage9c_bootstrap_rescue_reporting import write_report

    write_report(raw, config, aggregated_dir)

    dedup_columns = ["dgp", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = raw.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "decision.json").is_file()
    assert (aggregated_dir / "exploded_qualifying.csv").is_file()
