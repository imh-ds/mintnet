import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2 import load_stage2_config
from mintnet.experiments.stage2e import run_stage2e


def test_stage2e_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage2_config(Path("configs/stage2e_screening_p30_smoke.yaml"))

    first = run_stage2e(config, tmp_path / "first")
    second = run_stage2e(config, tmp_path / "second")

    assert len(first) == 1 * 4 * (2 + 1)  # 1 N, 4 replicates, 3 rules
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage2e_report.md"):
            assert (output / filename).is_file()


def test_stage2e_provenance_uses_its_own_charter_not_stage2s(tmp_path: Path, monkeypatch) -> None:
    """The whole reason this module exists separately from mintnet.experiments.stage2:
    evidence must hash docs/stage2e_charter.md, not docs/stage2_charter.md."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage2_config((repository_root / "configs/stage2e_screening_p30_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage2e_charter.md").read_bytes()
    ).hexdigest()
    wrong_hash = hashlib.sha256(
        (repository_root / "docs/stage2_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage2e(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["charter_sha256"] != wrong_hash
    assert metadata["git_commit"] == expected_commit


def test_stage2e_ground_truth_matches_p30(tmp_path: Path) -> None:
    """p=30 with 9 true-motif variables gives 9 true pairs and 426 null pairs
    (C(30,2) - 9), not Stage 2's 96 -- the entire point of this charter."""
    config = load_stage2_config(Path("configs/stage2e_screening_p30_smoke.yaml"))
    raw = run_stage2e(config, tmp_path / "evidence")

    row = raw.iloc[0]
    assert row["true_pair_count"] == 9
    assert row["null_pair_count"] == 426
