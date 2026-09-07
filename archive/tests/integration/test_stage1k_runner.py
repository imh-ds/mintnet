import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1k import load_stage1k_config, run_stage1k


def test_stage1k_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage1k_config(Path("configs/stage1k_hub_smoke.yaml"))

    first = run_stage1k(config, tmp_path / "first")
    second = run_stage1k(config, tmp_path / "second")

    assert len(first) == 1 * 4
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage1k_metrics_are_in_range(tmp_path: Path) -> None:
    config = load_stage1k_config(Path("configs/stage1k_hub_smoke.yaml"))
    raw = run_stage1k(config, tmp_path / "evidence")

    assert raw["status"].eq("ok").all()
    assert (raw["indirect_prune_tpr"] >= 0.0).all() and (raw["indirect_prune_tpr"] <= 1.0).all()
    assert (raw["true_edge_prune_fpr"] >= 0.0).all() and (raw["true_edge_prune_fpr"] <= 1.0).all()


def test_stage1k_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1k_config((repository_root / "configs/stage1k_hub_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1k_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1k(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
