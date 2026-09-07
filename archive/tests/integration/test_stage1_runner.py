import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1 import load_stage1_config, run_stage1


def test_stage1_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    """Changing Stage 1 seed derivation must change neither raw evidence run."""
    config = load_stage1_config(Path("configs/stage1_dpi_smoke.yaml"))

    first = run_stage1(config, tmp_path / "first")
    second = run_stage1(config, tmp_path / "second")

    assert len(first) == 3 * 1 * 1 * 2 * len(config.taus)
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


def test_stage1_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    """Launching elsewhere must preserve the charter hash and repository commit."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1_config((repository_root / "configs/stage1_dpi_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
