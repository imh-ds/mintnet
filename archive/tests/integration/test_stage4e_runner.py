import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4e import load_stage4e_config, run_stage4e


def test_stage4e_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4e_config(Path("configs/stage4e_candidacy_metric_smoke.yaml"))

    first = run_stage4e(config, tmp_path / "first")
    second = run_stage4e(config, tmp_path / "second")

    assert len(first) == len(config.sample_sizes) * len(config.alphas) * config.replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4e_shares_seed_derivation_with_stage4b_overlap(tmp_path: Path) -> None:
    """Stage 4e must simulate the identical draws Stage 4d already analyzed
    -- reusing Stage 4b/4d's exact seed derivation for overlap's shape
    index, not an independent seeding scheme."""
    from mintnet.experiments.stage4b import Stage4bConfig
    from mintnet.experiments.stage4b import run_stage4b

    stage4b_config = Stage4bConfig(
        sample_sizes=(300,),
        hub_strength=0.5,
        alphas=(0.05,),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )
    stage4e_config = load_stage4e_config(Path("configs/stage4e_candidacy_metric_smoke.yaml"))
    stage4e_config_matched = stage4e_config.__class__(
        **{**stage4e_config.__dict__, "sample_sizes": (300,), "alphas": (0.05,)}
    )

    stage4b_raw = run_stage4b(stage4b_config, tmp_path / "stage4b")
    stage4e_raw = run_stage4e(stage4e_config_matched, tmp_path / "stage4e")

    stage4b_overlap_seeds = (
        stage4b_raw.loc[stage4b_raw["shape"] == "overlap", ["n", "replicate", "seed"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    stage4e_seeds = stage4e_raw[["n", "replicate", "seed"]].drop_duplicates().reset_index(drop=True)
    pd.testing.assert_frame_equal(stage4b_overlap_seeds, stage4e_seeds)


def test_stage4e_per_pair_columns_are_internally_consistent(tmp_path: Path) -> None:
    config = load_stage4e_config(Path("configs/stage4e_candidacy_metric_smoke.yaml"))
    raw = run_stage4e(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for label in ("03", "04", "13", "14"):
        candidate = ok[f"candidate_{label}"]
        correct = ok[f"correctly_pruned_{label}"]
        assert candidate.isin([True, False]).all()
        # correctly_pruned must be defined exactly when candidate is True, NaN otherwise.
        assert (correct.notna() == candidate).all()
    assert (ok["true_edge_prune_fpr"] >= 0.0).all() and (ok["true_edge_prune_fpr"] <= 1.0).all()


def test_stage4e_provenance_uses_config_repository_when_cwd_changes(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4e_config((repository_root / "configs/stage4e_candidacy_metric_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4e_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4e(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
