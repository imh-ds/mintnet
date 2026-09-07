import hashlib
import json
import subprocess
from itertools import combinations
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2c import TRUE_CANDIDATE_PAIRS, load_stage2c_config
from mintnet.experiments.stage2g import NOISE_COUNT, P, run_stage2g


def test_stage2g_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage2c_config(Path("configs/stage2g_hub_composition_p30_smoke.yaml"))

    first = run_stage2g(config, tmp_path / "first")
    second = run_stage2g(config, tmp_path / "second")

    assert len(first) == 1 * 4  # 1 N, 4 replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage2g_report.md"):
            assert (output / filename).is_file()


def test_stage2g_provenance_uses_its_own_charter_not_stage2cs(tmp_path: Path, monkeypatch) -> None:
    """The whole reason this module exists separately from
    mintnet.experiments.stage2c: evidence must hash docs/stage2g_charter.md,
    not docs/stage2c_charter.md."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage2c_config((repository_root / "configs/stage2g_hub_composition_p30_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage2g_charter.md").read_bytes()
    ).hexdigest()
    wrong_hash = hashlib.sha256(
        (repository_root / "docs/stage2c_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage2g(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["charter_sha256"] != wrong_hash
    assert metadata["git_commit"] == expected_commit


def test_stage2g_ground_truth_matches_p30_hub_composition() -> None:
    """p=30 with the 10-variable chain/fork/hub DGP gives 12 true candidate
    pairs and 423 null pairs (C(30,2) - 12), not Stage 2c's 93."""
    assert NOISE_COUNT == 20
    assert P == 30
    all_pairs = set(combinations(range(P), 2))
    null_pairs = all_pairs - TRUE_CANDIDATE_PAIRS
    assert len(TRUE_CANDIDATE_PAIRS) == 12
    assert len(null_pairs) == 423
