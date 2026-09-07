import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4i import load_stage4i_config, run_stage4i


def _bookend_stage4e_csv(tmp_path: Path) -> Path:
    """Hand-crafted synthetic Stage 4e-shaped evidence, per
    test_stage4g_runner.py's own precedent -- never depend on the real,
    git-ignored results/generated/ files existing on disk. Mirrors the
    real tradeoff (candidacy falls, accuracy rises, as alpha shrinks), with
    the crossing point shifting by N, so the fitting points are not all
    identical (an all-identical fitting curve makes R^2 divide by zero)
    and the .80 candidacy floor genuinely selects different alphas.
    """
    from mintnet.experiments.stage4g_fit import FITTING_ALPHAS
    from mintnet.experiments.stage4i_fit import FITTING_SAMPLE_SIZES

    ordered_alphas = sorted(FITTING_ALPHAS, reverse=True)
    offset_by_n = {300: 0, 500: 1, 600: 1, 650: 2, 700: 2, 750: 3}

    rows = []
    for n in FITTING_SAMPLE_SIZES:
        offset = offset_by_n[n]
        for rank, alpha in enumerate(ordered_alphas):
            effective_rank = max(0, rank - offset)
            candidacy = max(0.0, 1.0 - effective_rank * 0.12)
            accuracy = min(1.0, 0.5 + effective_rank * 0.06)
            for replicate in range(10):  # all within development bounds (0-999)
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


def test_stage4i_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4i_config(Path("configs/stage4i_alpha_repair_smoke.yaml"))
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)

    first = run_stage4i(config, stage4e_evidence, tmp_path / "first")
    second = run_stage4i(config, stage4e_evidence, tmp_path / "second")

    assert len(first) == len(config.sample_sizes) * config.replicates
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "fitting_points.json"):
            assert (output / filename).is_file()


def test_stage4i_fitting_set_excludes_n_750(tmp_path: Path) -> None:
    from mintnet.experiments.stage4i_fit import FITTING_SAMPLE_SIZES

    assert 750 not in FITTING_SAMPLE_SIZES


def test_stage4i_uses_a_single_predicted_alpha_per_n_not_a_grid(tmp_path: Path) -> None:
    config = load_stage4i_config(Path("configs/stage4i_alpha_repair_smoke.yaml"))
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)

    raw = run_stage4i(config, stage4e_evidence, tmp_path / "evidence")

    for n in config.sample_sizes:
        assert raw.loc[raw["n"] == n, "alpha"].nunique() == 1


def test_stage4i_reports_error_status_when_predicted_alpha_is_invalid(tmp_path: Path) -> None:
    # Reuse the real, git-ignored Stage 4e evidence's own known shape: the
    # refit formula predicts a negative alpha at N=750 (D-037's own finding,
    # re-derived here from the synthetic fixture's crossing point at high N).
    config = load_stage4i_config(Path("configs/stage4i_alpha_repair_smoke.yaml"))
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)

    raw = run_stage4i(config, stage4e_evidence, tmp_path / "evidence")

    predicted = raw["alpha"].iloc[0]
    if predicted <= 0.0 or predicted >= 1.0:
        assert (raw["status"] == "error").all()
        assert raw["error"].str.contains("not a valid probability").all()


def test_stage4i_provenance_records_stage4e_evidence_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4i_config((repository_root / "configs/stage4i_alpha_repair_smoke.yaml").resolve())
    stage4e_evidence = _bookend_stage4e_csv(tmp_path)
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4i_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()
    expected_evidence_hash = hashlib.sha256(stage4e_evidence.read_bytes()).hexdigest()

    monkeypatch.chdir(tmp_path)
    run_stage4i(config, stage4e_evidence, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
    assert metadata["stage4e_raw_evidence_sha256"] == expected_evidence_hash
