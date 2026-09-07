import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage5d import DGPS, METHODS, load_stage5d_config, run_stage5d


def test_stage5d_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage5d_config(Path("configs/stage5d_strength_sweep_smoke.yaml"))

    first = run_stage5d(config, tmp_path / "first")
    second = run_stage5d(config, tmp_path / "second")

    expected_rows = len(DGPS) * len(config.sample_sizes) * len(config.strengths) * config.replicates * len(METHODS)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage5d_report.md"):
            assert (output / filename).is_file()


def test_stage5d_covers_every_dgp_n_strength_method_combination(tmp_path: Path) -> None:
    config = load_stage5d_config(Path("configs/stage5d_strength_sweep_smoke.yaml"))

    raw = run_stage5d(config, tmp_path / "evidence")

    combos = set(zip(raw["dgp"], raw["n"], raw["strength"], raw["method"]))
    expected = {(d, n, s, meth) for d in DGPS for n in config.sample_sizes for s in config.strengths for meth in METHODS}
    assert combos == expected


def test_stage5d_screening_alpha_matches_native_p_exactly(tmp_path: Path) -> None:
    """At the native noise multiplier, p=15 for both shapes, so
    alpha(p) must equal D-047's own original .001 exactly."""
    config = load_stage5d_config(Path("configs/stage5d_strength_sweep_smoke.yaml"))

    raw = run_stage5d(config, tmp_path / "evidence")

    mint = raw.loc[(raw["method"] == "mint") & (raw["status"] == "ok")]
    assert (mint["p"] == 15).all()
    assert mint["screening_alpha"].sub(0.001).abs().max() < 1e-12


def test_stage5d_seeds_are_disjoint_from_stage5c(tmp_path: Path) -> None:
    from mintnet.experiments.stage5c import _condition_seed as stage5c_seed
    from mintnet.experiments.stage5d import _condition_seed as stage5d_seed

    for dgp_index in range(2):
        for sample_index in range(2):
            for replicate in range(2):
                assert stage5c_seed(20260830, dgp_index, sample_index, 0, replicate) != stage5d_seed(
                    20260830, dgp_index, sample_index, 0, replicate
                )


def test_stage5d_three_dimensions_are_independently_shardable(tmp_path: Path) -> None:
    config = load_stage5d_config(Path("configs/stage5d_strength_sweep_smoke.yaml"))

    unsharded = run_stage5d(config, tmp_path / "unsharded")
    shard = run_stage5d(
        config, tmp_path / "shard",
        dgps=("chain_fork_hub",), sample_sizes=(750,), strengths=(0.3,), write_report=False,
    )

    expected = unsharded.loc[
        (unsharded["dgp"] == "chain_fork_hub") & (unsharded["n"] == 750) & (unsharded["strength"] == 0.3)
    ].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))
    assert not (tmp_path / "shard" / "stage5d_report.md").exists()


def test_stage5d_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config_path = Path("configs/stage5d_strength_sweep_smoke.yaml")
    config = load_stage5d_config(config_path)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage5d(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    for dgp in DGPS:
        for n in config.sample_sizes:
            run_stage5d(
                config, shards_dir / f"{dgp}_{n}",
                dgps=(dgp,), sample_sizes=(n,), strengths=config.strengths, write_report=False,
            )

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage5d", config_path, shards_dir, aggregated_dir)

    key = ["dgp", "n", "strength", "method", "replicate"]
    unsharded_sorted = unsharded.sort_values(key).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(key).reset_index(drop=True)
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"),
        aggregated_sorted.drop(columns="elapsed_seconds"),
        check_dtype=False,
    )
    for filename in ("raw_metrics.csv", "report.json", "stage5d_report.md", "gap_by_strength.png"):
        assert (aggregated_dir / filename).is_file()


def test_stage5d_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage5d_config(
        (repository_root / "configs/stage5d_strength_sweep_smoke.yaml").resolve()
    )
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage5d_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage5d(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
