import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2b import load_stage2b_config
from mintnet.experiments.stage2f import run_stage2f


def test_stage2f_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage2b_config(Path("configs/stage2f_composition_p30_smoke.yaml"))

    first = run_stage2f(config, tmp_path / "first")
    second = run_stage2f(config, tmp_path / "second")

    assert len(first) == 1 * 4  # 1 N, 4 replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage2f_report.md"):
            assert (output / filename).is_file()


def test_stage2f_provenance_uses_its_own_charter_not_stage2bs(tmp_path: Path, monkeypatch) -> None:
    """The whole reason this module exists separately from
    mintnet.experiments.stage2b: evidence must hash docs/stage2f_charter.md,
    not docs/stage2b_charter.md."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage2b_config((repository_root / "configs/stage2f_composition_p30_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage2f_charter.md").read_bytes()
    ).hexdigest()
    wrong_hash = hashlib.sha256(
        (repository_root / "docs/stage2b_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage2f(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["charter_sha256"] != wrong_hash
    assert metadata["git_commit"] == expected_commit


def test_stage2f_ground_truth_matches_p30(tmp_path: Path) -> None:
    """p=30 gives 426 null pairs (C(30,2) - 9, per D-023) driving the
    composed pipeline's false-edge-rate denominator, not Stage 2b's 96 --
    checked directly against the config's own noise_count rather than
    assumed."""
    from itertools import combinations

    from mintnet.experiments.stage2b import TRUE_DIRECT_EDGES
    from mintnet.simulation import TRUE_PAIR_INDICES

    config = load_stage2b_config(Path("configs/stage2f_composition_p30_smoke.yaml"))
    p = 9 + config.noise_count
    assert p == 30
    all_pairs = set(combinations(range(p), 2))
    null_pairs = all_pairs - TRUE_PAIR_INDICES
    assert len(null_pairs) == 426
    assert TRUE_DIRECT_EDGES.issubset(TRUE_PAIR_INDICES)

    raw = run_stage2f(config, tmp_path / "evidence")
    assert raw.loc[raw["status"] == "ok", "screening_false_edge_rate"].between(0.0, 1.0).all()
