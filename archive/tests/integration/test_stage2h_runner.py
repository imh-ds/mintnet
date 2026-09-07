import hashlib
import json
import subprocess
from itertools import combinations
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2d import TRUE_CANDIDATE_PAIRS, load_stage2d_config
from mintnet.experiments.stage2h import NOISE_COUNT, P, run_stage2h


def test_stage2h_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage2d_config(Path("configs/stage2h_overlap_composition_p30_smoke.yaml"))

    first = run_stage2h(config, tmp_path / "first")
    second = run_stage2h(config, tmp_path / "second")

    assert len(first) == 1 * 4  # 1 N, 4 replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage2h_report.md"):
            assert (output / filename).is_file()


def test_stage2h_provenance_uses_its_own_charter_not_stage2ds(tmp_path: Path, monkeypatch) -> None:
    """The whole reason this module exists separately from
    mintnet.experiments.stage2d: evidence must hash docs/stage2h_charter.md,
    not docs/stage2d_charter.md."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage2d_config((repository_root / "configs/stage2h_overlap_composition_p30_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage2h_charter.md").read_bytes()
    ).hexdigest()
    wrong_hash = hashlib.sha256(
        (repository_root / "docs/stage2d_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage2h(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["charter_sha256"] != wrong_hash
    assert metadata["git_commit"] == expected_commit


def test_stage2h_ground_truth_matches_p30_overlap_composition() -> None:
    """p=30 with the 11-variable chain/fork/overlap DGP gives 16 true
    candidate pairs and 419 null pairs (C(30,2) - 16), not Stage 2d's 89."""
    assert NOISE_COUNT == 19
    assert P == 30
    all_pairs = set(combinations(range(P), 2))
    null_pairs = all_pairs - TRUE_CANDIDATE_PAIRS
    assert len(TRUE_CANDIDATE_PAIRS) == 16
    assert len(null_pairs) == 419
