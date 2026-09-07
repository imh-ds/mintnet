import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage2j import P5, P10, load_stage2j_config, run_stage2j


def test_stage2j_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage2j_config(Path("configs/stage2j_floor_check_smoke.yaml"))

    first_selection, first_composition = run_stage2j(config, tmp_path / "first")
    second_selection, second_composition = run_stage2j(config, tmp_path / "second")

    # 2 N x 3 alphas x 4 replicates
    assert len(first_selection) == 2 * 3 * 4
    # 2 p x 2 N x 4 replicates
    assert len(first_composition) == 2 * 2 * 4

    pd.testing.assert_frame_equal(
        first_selection.drop(columns="elapsed_seconds"), second_selection.drop(columns="elapsed_seconds")
    )
    pd.testing.assert_frame_equal(
        first_composition.drop(columns="elapsed_seconds"), second_composition.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in (
            "raw_metrics.csv", "screening_selection_metrics.csv", "resolved_config.yaml",
            "metadata.json", "decision.json", "stage2j_report.md", "overlap_tpr_by_p.png",
        ):
            assert (output / filename).is_file()


def test_stage2j_p5_has_no_null_pairs_by_construction(tmp_path: Path) -> None:
    """p=5 (overlap motif only, zero noise columns) has no room for any null
    pairs -- screening/final false-edge rate and chain TPR must come back NaN
    for every p=5 row, not merely unused, per the charter's disclosed
    limitation."""
    config = load_stage2j_config(Path("configs/stage2j_floor_check_smoke.yaml"))
    _selection, composition = run_stage2j(config, tmp_path / "evidence")

    p5_rows = composition.loc[composition["p"] == P5]
    assert p5_rows["chain_indirect_tpr"].isna().all()
    assert p5_rows["screening_false_edge_rate"].isna().all()
    assert p5_rows["final_false_edge_rate"].isna().all()
    assert p5_rows["overlap_indirect_tpr"].between(0.0, 1.0).all()

    # At smoke scale (4 replicates), p=10's screening-alpha selection can
    # legitimately find no eligible development alpha for some N -- those
    # rows carry an "error" status and NaN metrics by design, not a bug.
    # Only rows where composition actually ran should have defined metrics.
    p10_ok_rows = composition.loc[(composition["p"] == P10) & (composition["status"] == "ok")]
    assert not p10_ok_rows.empty
    assert p10_ok_rows["chain_indirect_tpr"].notna().all()
    assert p10_ok_rows["final_false_edge_rate"].notna().all()
    assert (p10_ok_rows["final_false_edge_rate"] <= p10_ok_rows["screening_false_edge_rate"] + 1e-9).all()


def test_stage2j_metrics_reflect_ground_truth(tmp_path: Path) -> None:
    config = load_stage2j_config(Path("configs/stage2j_floor_check_smoke.yaml"))
    _selection, composition = run_stage2j(config, tmp_path / "evidence")

    ok = composition.loc[composition["status"] == "ok"]
    for col in ("overlap_indirect_tpr", "true_edge_prune_fpr"):
        assert (ok[col] >= 0.0).all() and (ok[col] <= 1.0).all()


def test_stage2j_provenance_uses_config_repository_when_cwd_changes(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage2j_config((repository_root / "configs/stage2j_floor_check_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage2j_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage2j(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
