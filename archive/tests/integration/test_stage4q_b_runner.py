import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4p import DGPS, _condition_seed as stage4p_condition_seed
from mintnet.experiments.stage4q_b import load_stage4q_b_config, run_stage4q_b


def test_stage4q_b_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4q_b_config(Path("configs/stage4q_b_decomposed_metric_smoke.yaml"))

    first = run_stage4q_b(config, tmp_path / "first")
    second = run_stage4q_b(config, tmp_path / "second")

    expected_rows = len(config.sample_sizes) * config.replicates
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4q_b_seeds_match_stage4p_overlap_exactly(tmp_path: Path) -> None:
    """Part B must reproduce Stage 4p's own overlap/sequential draws
    bit-for-bit -- same seed derivation, same dgp_index."""
    config = load_stage4q_b_config(Path("configs/stage4q_b_decomposed_metric_smoke.yaml"))
    overlap_index = DGPS.index("overlap")

    raw = run_stage4q_b(config, tmp_path / "evidence")

    for sample_index, n in enumerate(config.sample_sizes):
        for replicate in raw.loc[raw["n"] == n, "replicate"].unique():
            expected_seed = stage4p_condition_seed(config.master_seed, overlap_index, sample_index, replicate)
            actual_seed = raw.loc[(raw["n"] == n) & (raw["replicate"] == replicate), "seed"].iloc[0]
            assert actual_seed == expected_seed


def test_stage4q_b_captures_per_pair_columns_for_all_four_overlap_pairs(tmp_path: Path) -> None:
    config = load_stage4q_b_config(Path("configs/stage4q_b_decomposed_metric_smoke.yaml"))

    raw = run_stage4q_b(config, tmp_path / "evidence")

    for label in ("6_9", "6_10", "7_9", "7_10"):
        assert f"candidate_{label}" in raw.columns
        assert f"correctly_pruned_{label}" in raw.columns


def test_stage4q_b_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4q_b_config((repository_root / "configs/stage4q_b_decomposed_metric_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4q_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4q_b(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
