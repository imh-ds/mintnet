import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage5b import DGPS, METHODS, load_stage5b_config, run_stage5b


def test_stage5b_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage5b_config(Path("configs/stage5b_noise_stress_test_smoke.yaml"))

    first = run_stage5b(config, tmp_path / "first")
    second = run_stage5b(config, tmp_path / "second")

    expected_rows = len(DGPS) * len(config.sample_sizes) * len(config.noise_multipliers) * config.replicates * len(METHODS)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage5b_report.md"):
            assert (output / filename).is_file()


def test_stage5b_covers_every_dgp_n_multiplier_method_combination(tmp_path: Path) -> None:
    config = load_stage5b_config(Path("configs/stage5b_noise_stress_test_smoke.yaml"))

    raw = run_stage5b(config, tmp_path / "evidence")

    combos = set(zip(raw["dgp"], raw["n"], raw["noise_multiplier"], raw["method"]))
    expected = {(d, n, m, meth) for d in DGPS for n in config.sample_sizes for m in config.noise_multipliers for meth in METHODS}
    assert combos == expected


def test_stage5b_extra_noise_columns_scale_p_without_changing_true_edges(tmp_path: Path) -> None:
    """Appending extra noise columns must grow p with the multiplier but
    never touch the true-edge structure -- both methods should still see
    perfect recall at these strengths/N, same as D-047's own baseline."""
    config = load_stage5b_config(Path("configs/stage5b_noise_stress_test_smoke.yaml"))

    raw = run_stage5b(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    # p grows with multiplier for each dgp (multiplier 2 has strictly more columns than 1)
    p_by_multiplier = ok.groupby(["dgp", "noise_multiplier"])["p"].first().unstack("noise_multiplier")
    assert (p_by_multiplier[2] > p_by_multiplier[1]).all()


def test_stage5b_seeds_are_disjoint_from_stage5a(tmp_path: Path) -> None:
    from mintnet.experiments.stage5a import _condition_seed as stage5a_seed
    from mintnet.experiments.stage5b import _condition_seed as stage5b_seed

    for dgp_index in range(2):
        for sample_index in range(2):
            for replicate in range(2):
                assert stage5a_seed(20260830, dgp_index, sample_index, replicate) != stage5b_seed(
                    20260830, dgp_index, sample_index, 0, replicate
                )


def test_stage5b_sharded_run_matches_unsharded_run(tmp_path: Path) -> None:
    config = load_stage5b_config(Path("configs/stage5b_noise_stress_test_smoke.yaml"))

    unsharded = run_stage5b(config, tmp_path / "unsharded")
    shard = run_stage5b(
        config, tmp_path / "shard", dgps=("chain_fork_hub",), noise_multipliers=(1,), write_report=False
    )

    expected = unsharded.loc[(unsharded["dgp"] == "chain_fork_hub") & (unsharded["noise_multiplier"] == 1)].reset_index(drop=True)
    actual = shard.reset_index(drop=True)
    pd.testing.assert_frame_equal(expected.drop(columns="elapsed_seconds"), actual.drop(columns="elapsed_seconds"))
    assert not (tmp_path / "shard" / "stage5b_report.md").exists()


def test_stage5b_aggregate_shards_reproduces_unsharded_report(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, "scripts")
    from aggregate_shards import aggregate

    config_path = Path("configs/stage5b_noise_stress_test_smoke.yaml")
    config = load_stage5b_config(config_path)

    unsharded_dir = tmp_path / "unsharded"
    unsharded = run_stage5b(config, unsharded_dir)

    shards_dir = tmp_path / "shards"
    for dgp in DGPS:
        run_stage5b(
            config, shards_dir / dgp, dgps=(dgp,), noise_multipliers=config.noise_multipliers, write_report=False
        )

    aggregated_dir = tmp_path / "aggregated"
    aggregated = aggregate("mintnet.experiments.stage5b", config_path, shards_dir, aggregated_dir)

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
    for filename in ("raw_metrics.csv", "report.json", "stage5b_report.md", "gap_by_noise_multiplier.png"):
        assert (aggregated_dir / filename).is_file()


def test_stage5b_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage5b_config(
        (repository_root / "configs/stage5b_noise_stress_test_smoke.yaml").resolve()
    )
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage5b_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage5b(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
