import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4a import load_stage1b_config, run_stage4a


def test_stage4a_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage1b_config(Path("configs/stage4a_sequential_smoke.yaml"))

    first = run_stage4a(config, tmp_path / "first")
    second = run_stage4a(config, tmp_path / "second")

    assert len(first) == 3 * 1 * 1 * 2 * len(config.alphas)
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4a_and_stage1b_simulate_identical_data(tmp_path: Path) -> None:
    """Stage 4a must isolate the pruning mechanism by reusing Stage 1b's exact seeds."""
    from mintnet.experiments.stage1b import load_stage1b_config as load_1b
    from mintnet.experiments.stage1b import run_stage1b

    stage1b_config = load_1b(Path("configs/stage1b_dpi_smoke.yaml"))
    stage4a_config = load_stage1b_config(Path("configs/stage4a_sequential_smoke.yaml"))
    # Both smoke configs share every DGP-relevant field except master_seed;
    # align them so the seed-derivation comparison below is meaningful.
    stage4a_config_matched = stage4a_config.__class__(
        **{**stage4a_config.__dict__, "master_seed": stage1b_config.master_seed}
    )

    stage1b_raw = run_stage1b(stage1b_config, tmp_path / "stage1b")
    stage4a_raw = run_stage4a(stage4a_config_matched, tmp_path / "stage4a")

    stage1b_seeds = stage1b_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ].reset_index(drop=True)
    stage4a_seeds = stage4a_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(stage1b_seeds, stage4a_seeds)


def test_stage4a_metrics_are_well_formed(tmp_path: Path) -> None:
    config = load_stage1b_config(Path("configs/stage4a_sequential_smoke.yaml"))
    raw = run_stage4a(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for col in ("indirect_prune_tpr", "true_edge_prune_fpr", "perfect_recovery"):
        finite = ok.loc[ok["motif"] != "triangle"] if col == "indirect_prune_tpr" else ok
        assert finite[col].dropna().between(0.0, 1.0).all()


def test_stage4a_provenance_uses_config_repository_when_cwd_changes(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1b_config((repository_root / "configs/stage4a_sequential_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4a_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4a(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
