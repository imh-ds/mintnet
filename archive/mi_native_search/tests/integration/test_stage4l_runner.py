import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4l import P, load_stage4l_config, run_stage4l


def test_stage4l_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4l_config(Path("configs/stage4l_composed_noise_chain_fork_hub_smoke.yaml"))

    first = run_stage4l(config, tmp_path / "first")
    second = run_stage4l(config, tmp_path / "second")

    expected_rows = len(config.strengths) * len(config.sample_sizes) * config.replicates
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4l_p_is_fifteen() -> None:
    assert P == 15


def test_stage4l_covers_every_strength_n_combination(tmp_path: Path) -> None:
    config = load_stage4l_config(Path("configs/stage4l_composed_noise_chain_fork_hub.yaml"))
    config = config.__class__(
        strengths=(0.3, 0.5),
        sample_sizes=(750, 1500),
        replicates=4,
        master_seed=config.master_seed,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=config.minimum_indirect_prune_tpr,
        maximum_true_edge_prune_fpr=config.maximum_true_edge_prune_fpr,
        false_edge_rate_tolerance=config.false_edge_rate_tolerance,
    )

    raw = run_stage4l(config, tmp_path / "evidence")

    combos = set(zip(raw["strength"], raw["n"]))
    expected = {(s, n) for s in config.strengths for n in config.sample_sizes}
    assert combos == expected


def test_stage4l_uses_the_same_alpha_across_strengths_at_a_given_n(tmp_path: Path) -> None:
    config = load_stage4l_config(Path("configs/stage4l_composed_noise_chain_fork_hub_smoke.yaml"))

    raw = run_stage4l(config, tmp_path / "evidence")

    for n in config.sample_sizes:
        assert raw.loc[raw["n"] == n, "alpha"].nunique() == 1


def test_stage4l_metrics_and_pair_columns_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4l_config(Path("configs/stage4l_composed_noise_chain_fork_hub_smoke.yaml"))

    raw = run_stage4l(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for col in ("chain_indirect_tpr", "fork_indirect_tpr", "hub_indirect_tpr", "true_edge_prune_fpr"):
        assert (ok[col] >= 0.0).all() and (ok[col] <= 1.0).all()
    assert (ok["final_false_edge_rate"] <= ok["screening_false_edge_rate"] + 1e-9).all()
    for label in ("02", "35", "78"):
        candidate = ok[f"candidate_{label}"]
        correct = ok[f"correctly_pruned_{label}"]
        assert candidate.isin([True, False]).all()
        assert (correct.notna() == candidate).all()


def test_stage4l_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4l_config((repository_root / "configs/stage4l_composed_noise_chain_fork_hub_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4l_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4l(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
