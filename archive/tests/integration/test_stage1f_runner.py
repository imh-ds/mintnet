import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1f import load_stage1f_config, run_stage1f


def test_stage1f_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    """Changing Stage 1f seed derivation must change neither raw evidence run."""
    config = load_stage1f_config(Path("configs/stage1f_dpi_smoke.yaml"))

    first = run_stage1f(config, tmp_path / "first")
    second = run_stage1f(config, tmp_path / "second")

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


def test_stage1f_reuses_stage1e_data_since_alpha_does_not_affect_simulation(tmp_path: Path) -> None:
    """A narrower alpha grid must not perturb the underlying simulated data or seeds."""
    from mintnet.experiments.stage1e import load_stage1e_config, run_stage1e

    stage1e_config = load_stage1e_config(Path("configs/stage1e_dpi_smoke.yaml"))
    stage1f_config = load_stage1f_config(Path("configs/stage1f_dpi_smoke.yaml"))

    stage1e_raw = run_stage1e(stage1e_config, tmp_path / "stage1e")
    stage1f_raw = run_stage1f(stage1f_config, tmp_path / "stage1f")

    stage1e_partials = stage1e_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed", "partial_r_01", "partial_r_02", "partial_r_12"]
    ].reset_index(drop=True)
    stage1f_partials = stage1f_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed", "partial_r_01", "partial_r_02", "partial_r_12"]
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(stage1e_partials, stage1f_partials)


def test_stage1f_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    """Launching elsewhere must preserve the charter hash and repository commit."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1f_config((repository_root / "configs/stage1f_dpi_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1f_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1f(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
