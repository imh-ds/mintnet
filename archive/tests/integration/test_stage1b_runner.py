import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1b import load_stage1b_config, run_stage1b


def test_stage1b_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    """Changing Stage 1b seed derivation must change neither raw evidence run."""
    config = load_stage1b_config(Path("configs/stage1b_dpi_smoke.yaml"))

    first = run_stage1b(config, tmp_path / "first")
    second = run_stage1b(config, tmp_path / "second")

    assert len(first) == 3 * 1 * 1 * 2 * len(config.alphas)
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in (
            "raw_metrics.csv",
            "resolved_config.yaml",
            "metadata.json",
        ):
            assert (output / filename).is_file()


def test_stage1b_and_stage1_simulate_identical_data(tmp_path: Path) -> None:
    """R2b must isolate the pruning mechanism by reusing Stage 1's exact seeds."""
    from mintnet.experiments.stage1 import load_stage1_config, run_stage1

    stage1_config = load_stage1_config(Path("configs/stage1_dpi_smoke.yaml"))
    stage1b_config = load_stage1b_config(Path("configs/stage1b_dpi_smoke.yaml"))

    stage1_raw = run_stage1(stage1_config, tmp_path / "stage1")
    stage1b_raw = run_stage1b(stage1b_config, tmp_path / "stage1b")

    stage1_seeds = stage1_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ].reset_index(drop=True)
    stage1b_seeds = stage1b_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(stage1_seeds, stage1b_seeds)


def test_stage1b_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    """Launching elsewhere must preserve the charter hash and repository commit."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1b_config((repository_root / "configs/stage1b_dpi_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1b_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1b(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
