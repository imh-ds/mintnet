import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4h import load_stage4h_config, run_stage4h


def _bookend_stage4e_csv(tmp_path: Path) -> Path:
    """Hand-crafted synthetic Stage 4e-shaped evidence, per
    test_stage1i_runner.py's own precedent -- never depend on the real,
    git-ignored results/generated/ files existing on disk."""
    from mintnet.experiments.stage4g_fit import FITTING_ALPHAS, FITTING_SAMPLE_SIZES

    ordered_alphas = sorted(FITTING_ALPHAS, reverse=True)
    offset_by_n = {300: 0, 500: 1, 600: 1, 650: 2, 700: 2, 750: 3}

    rows = []
    for n in FITTING_SAMPLE_SIZES:
        offset = offset_by_n[n]
        for rank, alpha in enumerate(ordered_alphas):
            effective_rank = max(0, rank - offset)
            candidacy = max(0.0, 1.0 - effective_rank * 0.12)
            accuracy = min(1.0, 0.5 + effective_rank * 0.06)
            for replicate in range(10):
                candidate = (replicate / 10.0) < candidacy
                row = {
                    "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
                    "true_edge_prune_fpr": 0.0, "status": "ok", "error": "",
                }
                for label in ("03", "04", "13", "14"):
                    row[f"candidate_{label}"] = candidate
                    row[f"correctly_pruned_{label}"] = ((replicate * 3) % 10) / 10.0 < accuracy if candidate else np.nan
                rows.append(row)
    path = tmp_path / "stage4e_raw_metrics.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_stage4h_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4h_config(Path("configs/stage4h_composed_noise_smoke.yaml"))
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)

    first = run_stage4h(config, stage4e_evidence, tmp_path / "first")
    second = run_stage4h(config, stage4e_evidence, tmp_path / "second")

    assert len(first) == len(config.sample_sizes) * config.replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4h_uses_a_single_predicted_alpha_per_n(tmp_path: Path) -> None:
    config = load_stage4h_config(Path("configs/stage4h_composed_noise_smoke.yaml"))
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)

    raw = run_stage4h(config, stage4e_evidence, tmp_path / "evidence")

    for n in config.sample_sizes:
        assert raw.loc[raw["n"] == n, "alpha"].nunique() == 1


def test_stage4h_metrics_and_pair_columns_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4h_config(Path("configs/stage4h_composed_noise_smoke.yaml"))
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)

    raw = run_stage4h(config, stage4e_evidence, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for col in ("chain_indirect_tpr", "fork_indirect_tpr", "overlap_indirect_tpr", "true_edge_prune_fpr"):
        assert (ok[col] >= 0.0).all() and (ok[col] <= 1.0).all()
    assert (ok["final_false_edge_rate"] <= ok["screening_false_edge_rate"] + 1e-9).all()
    for label in ("6_9", "6_10", "7_9", "7_10"):
        candidate = ok[f"candidate_{label}"]
        correct = ok[f"correctly_pruned_{label}"]
        assert candidate.isin([True, False]).all()
        assert (correct.notna() == candidate).all()


def test_stage4h_provenance_records_stage4e_evidence_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4h_config((repository_root / "configs/stage4h_composed_noise_smoke.yaml").resolve())
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4h_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()
    expected_evidence_hash = hashlib.sha256(stage4e_evidence.read_bytes()).hexdigest()

    monkeypatch.chdir(tmp_path)
    run_stage4h(config, stage4e_evidence, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
    assert metadata["stage4e_raw_evidence_sha256"] == expected_evidence_hash
