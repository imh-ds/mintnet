import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4b import SHAPES, load_stage4b_config, run_stage4b


def test_stage4b_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4b_config(Path("configs/stage4b_hub_overlap_smoke.yaml"))

    first = run_stage4b(config, tmp_path / "first")
    second = run_stage4b(config, tmp_path / "second")

    assert len(first) == len(SHAPES) * len(config.sample_sizes) * len(config.alphas) * config.replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4b_metrics_reflect_ground_truth(tmp_path: Path) -> None:
    config = load_stage4b_config(Path("configs/stage4b_hub_overlap_smoke.yaml"))
    raw = run_stage4b(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for col in ("indirect_prune_tpr", "true_edge_prune_fpr"):
        assert (ok[col] >= 0.0).all() and (ok[col] <= 1.0).all()
    assert set(ok["shape"]) == set(SHAPES)


def test_stage4b_provenance_uses_config_repository_when_cwd_changes(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4b_config((repository_root / "configs/stage4b_hub_overlap_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4b_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4b(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
