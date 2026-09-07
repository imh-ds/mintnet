import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4f import load_stage4f_config, run_stage4f


def test_stage4f_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4f_config(Path("configs/stage4f_anomaly_diagnostic_smoke.yaml"))

    first = run_stage4f(config, tmp_path / "first")
    second = run_stage4f(config, tmp_path / "second")

    expected_rows = len(config.sample_sizes) * len(config.alphas) * config.replicates * 4  # 4 cross-branch pairs
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4f_shares_seed_derivation_with_stage4e(tmp_path: Path) -> None:
    """Stage 4f must examine the identical draws Stage 4e already analyzed."""
    from mintnet.experiments.stage4e import Stage4eConfig, run_stage4e

    stage4e_config = Stage4eConfig(
        sample_sizes=(300,),
        alphas=(0.10,),
        replicates=20,
        master_seed=20260830,
        development_replicates=(0, 9),
        validation_replicates=(10, 19),
        minimum_conditional_accuracy=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )
    stage4f_config = load_stage4f_config(Path("configs/stage4f_anomaly_diagnostic_smoke.yaml"))

    stage4e_raw = run_stage4e(stage4e_config, tmp_path / "stage4e")
    stage4f_raw = run_stage4f(stage4f_config, tmp_path / "stage4f")

    stage4e_seeds = stage4e_raw[["n", "replicate", "seed"]].drop_duplicates().reset_index(drop=True)
    stage4f_seeds = stage4f_raw[["n", "replicate", "seed"]].drop_duplicates().reset_index(drop=True)
    pd.testing.assert_frame_equal(stage4e_seeds, stage4f_seeds)


def test_stage4f_partial_correlation_only_defined_for_candidates(tmp_path: Path) -> None:
    config = load_stage4f_config(Path("configs/stage4f_anomaly_diagnostic_smoke.yaml"))
    raw = run_stage4f(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    candidates = ok.loc[ok["candidate"] == True]  # noqa: E712
    non_candidates = ok.loc[ok["candidate"] == False]  # noqa: E712
    assert not candidates.empty
    assert candidates["r_partial"].notna().all()
    assert candidates["correctly_pruned"].notna().all()
    if not non_candidates.empty:
        assert non_candidates["r_partial"].isna().all()
        assert non_candidates["correctly_pruned"].isna().all()


def test_stage4f_provenance_uses_config_repository_when_cwd_changes(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4f_config((repository_root / "configs/stage4f_anomaly_diagnostic_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4f_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4f(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
