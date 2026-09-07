import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1h import load_stage1h_config, run_stage1h


def test_stage1h_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    """Changing Stage 1h seed derivation must change neither raw evidence run."""
    config = load_stage1h_config(Path("configs/stage1h_dpi_smoke.yaml"))

    first = run_stage1h(config, tmp_path / "first")
    second = run_stage1h(config, tmp_path / "second")

    assert len(first) == 3 * 2 * 1 * 4 * len(config.alphas)
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


def test_stage1h_reuses_stage1e_data_for_shared_sample_sizes(tmp_path: Path) -> None:
    """Extending the N grid must not perturb seeds already used by R2e/R2f/R2g."""
    from mintnet.experiments.stage1e import load_stage1e_config, run_stage1e

    stage1e_config = load_stage1e_config(Path("configs/stage1e_dpi_smoke.yaml"))
    stage1h_config = load_stage1h_config(Path("configs/stage1h_dpi_smoke.yaml"))

    stage1e_raw = run_stage1e(stage1e_config, tmp_path / "stage1e")
    stage1h_raw = run_stage1h(stage1h_config, tmp_path / "stage1h")

    stage1e_partials = stage1e_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed", "partial_r_01", "partial_r_02", "partial_r_12"]
    ].reset_index(drop=True)
    stage1h_partials = stage1h_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed", "partial_r_01", "partial_r_02", "partial_r_12"]
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(stage1e_partials, stage1h_partials)


def test_stage1h_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    """Launching elsewhere must preserve the charter hash and repository commit."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1h_config((repository_root / "configs/stage1h_dpi_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1h_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1h(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
