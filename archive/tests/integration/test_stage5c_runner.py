import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from mintnet.experiments.stage5c import (
    DGPS,
    METHODS,
    _screening_alpha_for_p,
    load_stage5c_config,
    run_stage5c,
)


def test_screening_alpha_matches_stage2_anchors_exactly() -> None:
    assert _screening_alpha_for_p(15) == pytest.approx(0.001)
    assert _screening_alpha_for_p(30) == pytest.approx(0.0001)


def test_screening_alpha_decreases_as_p_grows() -> None:
    assert _screening_alpha_for_p(15) > _screening_alpha_for_p(21) > _screening_alpha_for_p(27) > _screening_alpha_for_p(30)


def test_stage5c_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage5c_config(Path("configs/stage5c_p_adjusted_alpha_smoke.yaml"))

    first = run_stage5c(config, tmp_path / "first")
    second = run_stage5c(config, tmp_path / "second")

    expected_rows = len(DGPS) * len(config.sample_sizes) * len(config.noise_multipliers) * config.replicates * len(METHODS)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage5c_report.md"):
            assert (output / filename).is_file()


def test_stage5c_covers_every_dgp_n_multiplier_method_combination(tmp_path: Path) -> None:
    config = load_stage5c_config(Path("configs/stage5c_p_adjusted_alpha_smoke.yaml"))

    raw = run_stage5c(config, tmp_path / "evidence")

    combos = set(zip(raw["dgp"], raw["n"], raw["noise_multiplier"], raw["method"]))
    expected = {(d, n, m, meth) for d in DGPS for n in config.sample_sizes for m in config.noise_multipliers for meth in METHODS}
    assert combos == expected


def test_stage5c_mint_screening_alpha_shrinks_with_multiplier(tmp_path: Path) -> None:
    config = load_stage5c_config(Path("configs/stage5c_p_adjusted_alpha_smoke.yaml"))

    raw = run_stage5c(config, tmp_path / "evidence")

    mint = raw.loc[(raw["method"] == "mint") & (raw["status"] == "ok")]
    alpha_by_multiplier = mint.groupby(["dgp", "noise_multiplier"])["screening_alpha"].first().unstack("noise_multiplier")
    assert (alpha_by_multiplier[2] < alpha_by_multiplier[1]).all()


def test_stage5c_three_dimensions_are_independently_shardable(tmp_path: Path) -> None:
    """Sharded by all three of (dgp, N, noise multiplier) -- unlike
    Stage 5b's two -- so a CI shard is exactly one cell, never more."""
    config = load_stage5c_config(Path("configs/stage5c_p_adjusted_alpha_smoke.yaml"))

    unsharded = run_stage5c(config, tmp_path / "unsharded")
    shard = run_stage5c(
        config, tmp_path / "shard",
        dgps=("chain_fork_hub",), sample_sizes=(750,), noise_multipliers=(1,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["dgp"] == "chain_fork_hub") & (unsharded["n"] == 750) & (unsharded["noise_multiplier"] == 1)
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))
    assert not (tmp_path / "shard" / "stage5c_report.md").exists()


def test_stage5c_seeds_are_disjoint_from_stage5b(tmp_path: Path) -> None:
    from mintnet.experiments.stage5b import _condition_seed as stage5b_seed
    from mintnet.experiments.stage5c import _condition_seed as stage5c_seed

    for dgp_index in range(2):
        for sample_index in range(2):
            for replicate in range(2):
                assert stage5b_seed(20260830, dgp_index, sample_index, 0, replicate) != stage5c_seed(
                    20260830, dgp_index, sample_index, 0, replicate
                )


def test_stage5c_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config_path = Path("configs/stage5c_p_adjusted_alpha_smoke.yaml")
    config = load_stage5c_config(config_path)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage5c(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    for dgp in DGPS:
        for n in config.sample_sizes:
            run_stage5c(
                config, shards_dir / f"{dgp}_{n}",
                dgps=(dgp,), sample_sizes=(n,), noise_multipliers=config.noise_multipliers, write_report=False,
            )

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage5c", config_path, shards_dir, aggregated_dir)

    key = ["dgp", "n", "noise_multiplier", "method", "replicate"]
    unsharded_sorted = unsharded.sort_values(key).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(key).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"),
        aggregated_sorted.drop(columns="elapsed_seconds"),
        check_dtype=False,
    )
    for filename in ("raw_metrics.csv", "report.json", "stage5c_report.md", "gap_by_noise_multiplier_vs_d048.png"):
        assert (aggregated_dir / filename).is_file()


def test_stage5c_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage5c_config(
        (repository_root / "configs/stage5c_p_adjusted_alpha_smoke.yaml").resolve()
    )
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage5c_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage5c(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
