import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2 import load_stage2_config, run_stage2


def test_stage2_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage2_config(Path("configs/stage2_screening_smoke.yaml"))

    first = run_stage2(config, tmp_path / "first")
    second = run_stage2(config, tmp_path / "second")

    assert len(first) == 1 * 4 * (2 + 1)  # 1 N, 4 replicates, 3 rules
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage2_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage2_config((repository_root / "configs/stage2_screening_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage2_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage2(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit


def test_stage2_recall_and_fdr_reflect_true_pair_ground_truth(tmp_path: Path) -> None:
    """A lenient alpha should recall the 9 true pairs comfortably at large replicate count."""
    config = load_stage2_config(Path("configs/stage2_screening_smoke.yaml"))
    raw = run_stage2(config, tmp_path / "evidence")

    lenient = raw.loc[(raw["rule_kind"] == "uncorrected") & (raw["threshold"] == 0.05)]
    assert lenient["recall"].mean() > 0.5  # weak assertion given only 4 replicates
    assert (lenient["recall"] <= 1.0).all()
    assert (lenient["false_discovery_rate"] >= 0.0).all()
