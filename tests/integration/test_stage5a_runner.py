import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage5a import DGPS, METHODS, load_stage5a_config, run_stage5a


def test_stage5a_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage5a_config(Path("configs/stage5a_comparator_benchmark_smoke.yaml"))

    first = run_stage5a(config, tmp_path / "first")
    second = run_stage5a(config, tmp_path / "second")

    expected_rows = len(DGPS) * len(config.sample_sizes) * config.replicates * len(METHODS)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage5a_report.md"):
            assert (output / filename).is_file()


def test_stage5a_covers_every_dgp_n_method_combination(tmp_path: Path) -> None:
    config = load_stage5a_config(Path("configs/stage5a_comparator_benchmark_smoke.yaml"))

    raw = run_stage5a(config, tmp_path / "evidence")

    combos = set(zip(raw["dgp"], raw["n"], raw["method"]))
    expected = {(d, n, m) for d in DGPS for n in config.sample_sizes for m in METHODS}
    assert combos == expected


def test_stage5a_both_methods_see_identical_underlying_draw(tmp_path: Path) -> None:
    """Paired same-draw design: both methods must be fit on identical data
    at each (dgp, N, replicate), since the draw depends only on seed."""
    config = load_stage5a_config(Path("configs/stage5a_comparator_benchmark_smoke.yaml"))

    raw = run_stage5a(config, tmp_path / "evidence")

    for dgp in DGPS:
        for n in config.sample_sizes:
            cell = raw.loc[(raw["dgp"] == dgp) & (raw["n"] == n)]
            seeds_by_method = cell.groupby("method")["seed"].apply(lambda s: tuple(sorted(s)))
            assert seeds_by_method.nunique() == 1


def test_stage5a_metrics_are_well_formed(tmp_path: Path) -> None:
    config = load_stage5a_config(Path("configs/stage5a_comparator_benchmark_smoke.yaml"))

    raw = run_stage5a(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for col in ("precision", "recall", "f1"):
        valid = ok[col].dropna()
        assert (valid >= 0.0).all() and (valid <= 1.0).all()
    assert (ok["shd"] >= 0.0).all()


def test_stage5a_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    """A shard restricted to one (dgp, N) subset must reproduce exactly
    the rows an unsharded run produces for that same subset -- the
    seed derivation is index-based on the full DGPS/sample_sizes grid,
    not the shard's own filtered view (docs/stage5a_charter.md's own
    seed requirement, load-bearing for the CI sharding workflow)."""
    config = load_stage5a_config(Path("configs/stage5a_comparator_benchmark_smoke.yaml"))

    unsharded = run_stage5a(config, tmp_path / "unsharded")
    shard = run_stage5a(
        config, tmp_path / "shard", dgps=("chain_fork_hub",), sample_sizes=(750,), write_report=False
    )

    expected = unsharded.loc[unsharded["dgp"] == "chain_fork_hub"].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))
    assert not (tmp_path / "shard" / "stage5a_report.md").exists()


def test_stage5a_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    """Exercises the generic aggregator (scripts/aggregate_shards.py)
    against stage5a's own shard-aggregation contract -- the same script
    .github/workflows/sharded_benchmark.yml calls for any future
    shardable experiment, not just this one."""
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config_path = Path("configs/stage5a_comparator_benchmark_smoke.yaml")
    config = load_stage5a_config(config_path)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage5a(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    for dgp in DGPS:
        run_stage5a(
            config, shards_dir / dgp, dgps=(dgp,), sample_sizes=config.sample_sizes, write_report=False
        )

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage5a", config_path, shards_dir, aggregated_dir)

    unsharded_sorted = unsharded.sort_values(["dgp", "n", "method", "replicate"]).reset_index(drop=True)
    aggregated_sorted = aggregated.sort_values(["dgp", "n", "method", "replicate"]).reset_index(drop=True)
    # The aggregated frame round-trips through CSV, so an empty "error"
    # string becomes NaN on read back -- both mean "no error"; normalize
    # before comparing rather than treat it as a real discrepancy.
    unsharded_sorted["error"] = unsharded_sorted["error"].replace("", pd.NA).fillna("")
    aggregated_sorted["error"] = aggregated_sorted["error"].fillna("")
    pd.testing.assert_frame_equal(
        unsharded_sorted.drop(columns="elapsed_seconds"),
        aggregated_sorted.drop(columns="elapsed_seconds"),
        check_dtype=False,
    )
    for filename in ("raw_metrics.csv", "report.json", "stage5a_report.md", "f1_by_n_by_shape.png"):
        assert (aggregated_dir / filename).is_file()


def test_stage5a_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage5a_config(
        (repository_root / "configs/stage5a_comparator_benchmark_smoke.yaml").resolve()
    )
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage5a_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage5a(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
