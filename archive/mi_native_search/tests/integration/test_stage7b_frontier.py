from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7b_frontier import (
    expected_combinations,
    expected_row_count,
    load_config,
    run_stage7b,
)

_SMOKE_CONFIG = Path("configs/stage7b_frontier_smoke.yaml")


def test_stage7b_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7b(config, tmp_path / "evidence", write_report=False)

    combos = set(zip(raw["target_rho"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_stage7b_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage7b(config, tmp_path / "unsharded", write_report=False)
    shard = run_stage7b(
        config, tmp_path / "shard",
        target_rhos=(0.08,), sample_sizes=(300,), batches=(0,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["target_rho"] == 0.08) & (unsharded["n"] == 300) & (unsharded["replicate"].isin([0, 1]))
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))


def test_stage7b_null_cell_rejection_rate_tracks_nominal_alpha(tmp_path: Path) -> None:
    """Weak evidence at smoke scale, not a real calibration check --
    just confirms the target_rho=0 in-family null cell is wired
    correctly (rejection rate should be a monotonically non-decreasing
    function of alpha, bounded in [0,1])."""
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage7b(config, tmp_path / "evidence", write_report=False)

    from mintnet.experiments.stage7b_frontier_reporting import build_curves

    curves = build_curves(raw, config)
    for n in config.sample_sizes:
        null_curve = curves.loc[(curves["target_rho"] == 0.0) & (curves["n"] == n)].sort_values("alpha")
        rates = null_curve["weak_edge_rejection_rate"].to_numpy()
        assert (rates >= 0).all() and (rates <= 1).all()
        assert (rates[1:] >= rates[:-1] - 1e-9).all(), f"non-monotonic at n={n}"  # non-decreasing in alpha


def test_stage7b_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage7b(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for target_rho in config.target_rhos:
        for n in config.sample_sizes:
            for batch in (0, 1):
                run_stage7b(
                    config, shards_dir / f"shard_{shard_index}",
                    target_rhos=(target_rho,), sample_sizes=(n,), batches=(batch,), write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage7b_frontier", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["target_rho", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"), aggregated_sorted.drop(columns="elapsed_seconds")
    )
    assert (aggregated_dir / "stage7b_report.md").is_file()
