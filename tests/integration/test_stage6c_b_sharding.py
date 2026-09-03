from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6c_b import expected_combinations, expected_row_count, load_config
from mintnet.experiments.stage6c import run_stage_b

_SMOKE_CONFIG = Path("configs/stage6c_null_calibration_smoke.yaml")


def test_stage6c_b_covers_every_expected_combination(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    raw = run_stage_b(config, tmp_path / "evidence", max_workers=1, write_report=False)

    combos = set(zip(raw["k_perm_label"], raw["label"], raw["n"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)


def test_stage6c_b_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    """A shard restricted to one (k_perm_label, label, N) cell must
    reproduce exactly the rows an unsharded run produces for that same
    cell -- seeds are derived from K_PERM_LABELS.index(...) and the
    full NULL_CONDITIONS/sample_sizes grid, not the shard's own
    filtered view (required for scripts/aggregate_shards.py's own
    contract, and the reason the earlier hash()-based seed was a bug:
    hash() is randomized per-process, so a separate CI shard process
    would have drawn different data for the identical cell)."""
    config = load_config(_SMOKE_CONFIG)

    unsharded = run_stage_b(config, tmp_path / "unsharded", max_workers=1, write_report=False)
    shard = run_stage_b(
        config, tmp_path / "shard", max_workers=1,
        k_perm_labels=("kperm10",), labels=("s1_null",), sample_sizes=(300,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["k_perm_label"] == "kperm10") & (unsharded["label"] == "s1_null") & (unsharded["n"] == 300)
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected, actual)


def test_stage6c_b_invalid_shard_combination_yields_zero_rows_not_an_error(tmp_path: Path) -> None:
    """|S|=0 (s0_null) never uses k_perm (global permutation) -- a CI
    shard dispatched for (kperm10, s0_null, N) is a legitimate empty
    cell, not a bug, since the generic sharding workflow dispatches the
    full cross product of every dimension and not every combination is
    valid for this experiment."""
    config = load_config(_SMOKE_CONFIG)

    shard = run_stage_b(
        config, tmp_path / "empty_shard", max_workers=1,
        k_perm_labels=("kperm10",), labels=("s0_null",), sample_sizes=(150,), write_report=False,
    )
    assert len(shard) == 0
    assert (tmp_path / "empty_shard" / "raw_metrics.csv").is_file()


def test_stage6c_b_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config = load_config(_SMOKE_CONFIG)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage_b(config, unsharded_dir, max_workers=1)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for k_perm_label in config.k_perm_labels:
        for label in ("s0_null", "s1_null", "s2_null", "s3_null"):
            for n in config.sample_sizes:
                run_stage_b(
                    config, shards_dir / f"shard_{shard_index}", max_workers=1,
                    k_perm_labels=(k_perm_label,), labels=(label,), sample_sizes=(n,), write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage6c_b", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    dedup_columns = ["k_perm_label", "label", "n", "replicate"]
    unsharded_sorted = unsharded.sort_values(dedup_columns).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(dedup_columns).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].replace("", pd.NA).fillna("")
    # One of the 16 dispatched shards (s0_null x kperm10) is a
    # legitimately empty CI shard (|S|=0 never uses k_perm); its
    # header-only CSV makes pandas infer "object" rather than the
    # in-memory frame's own int64 for every int column on concat -- a
    # CSV round-trip dtype quirk, not a real discrepancy (no actual
    # empty-shard rows exist in either frame to compare).
    for column in ("k_perm_resolved", "k_cmi", "s", "n", "replicate", "seed"):
        aggregated_sorted[column] = aggregated_sorted[column].astype("int64")
    pd.testing.assert_frame_equal(unsharded_sorted, aggregated_sorted)
    assert (aggregated_dir / "stage_b_report.md").is_file()
