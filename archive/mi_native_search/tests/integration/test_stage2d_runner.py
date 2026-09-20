import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2d import load_stage2d_config, run_stage2d


def test_stage2d_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage2d_config(Path("configs/stage2d_composition_smoke.yaml"))

    first = run_stage2d(config, tmp_path / "first")
    second = run_stage2d(config, tmp_path / "second")

    assert len(first) == 1 * 4  # 1 N, 4 replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage2d_metrics_reflect_ground_truth(tmp_path: Path) -> None:
    config = load_stage2d_config(Path("configs/stage2d_composition_smoke.yaml"))
    raw = run_stage2d(config, tmp_path / "evidence")

    assert raw["status"].eq("ok").all()
    for col in ("chain_indirect_tpr", "fork_indirect_tpr", "overlap_indirect_tpr", "true_edge_prune_fpr"):
        assert (raw[col] >= 0.0).all() and (raw[col] <= 1.0).all()
    # Composition only removes candidate edges within validated cliques; it never
    # adds new ones, so the final false-edge rate can never exceed screening's own.
    assert (raw["final_false_edge_rate"] <= raw["screening_false_edge_rate"] + 1e-9).all()


def test_stage2d_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage2d_config((repository_root / "configs/stage2d_composition_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage2d_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage2d(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
