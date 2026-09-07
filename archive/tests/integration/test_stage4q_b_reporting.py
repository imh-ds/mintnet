from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4q_b import Stage4qBConfig


def _config() -> Stage4qBConfig:
    return Stage4qBConfig(
        sample_sizes=(400,),
        strength=0.5,
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_conditional_accuracy=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )


def _row(n, alpha, replicate, *, composite_tpr=1.0, candidate=True, correct=True):
    row = {
        "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "chain_indirect_tpr": 1.0, "fork_indirect_tpr": 1.0, "overlap_indirect_tpr": composite_tpr,
        "true_edge_prune_fpr": 0.0, "status": "ok", "error": "",
    }
    for label in ("6_9", "6_10", "7_9", "7_10"):
        row[f"candidate_{label}"] = candidate
        row[f"correctly_pruned_{label}"] = correct if candidate else np.nan
    return row


def test_evaluate_n_reveals_gap_between_composite_and_decomposed():
    from mintnet.experiments.stage4q_b_reporting import evaluate_n

    # composite TPR reads 1.0 (non-detection conflated with correctness),
    # but only half the pairs are genuine candidates.
    rows = []
    for r in range(2):  # validation replicates 2-3
        rows.append(_row(400, 0.10, r + 2, composite_tpr=1.0, candidate=(r == 0), correct=True))
    raw = pd.DataFrame(rows)

    comparison = evaluate_n(raw, 400, _config())

    assert comparison.composite_overlap_tpr == 1.0
    assert comparison.candidacy_rate == 0.5
    assert comparison.conditional_accuracy == 1.0  # perfect among actual candidates


def test_evaluate_n_reports_no_candidates_status():
    from mintnet.experiments.stage4q_b_reporting import evaluate_n

    rows = [_row(400, 0.10, r + 2, candidate=False) for r in range(2)]
    raw = pd.DataFrame(rows)

    comparison = evaluate_n(raw, 400, _config())

    assert comparison.status == "no candidates"
    assert comparison.conditional_accuracy is None


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage4q_b_reporting import write_stage4q_b_report

    config = _config()
    rows = [_row(400, 0.10, r, composite_tpr=1.0, candidate=True, correct=True) for r in range(4)]
    raw = pd.DataFrame(rows)

    comparisons = write_stage4q_b_report(raw, config, tmp_path)

    assert len(comparisons) == 1
    for filename in ("comparison.json", "stage4q_b_report.md", "composite_vs_decomposed.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4q_b_report.md").read_text(encoding="utf-8")
    assert "gap" in report_text.lower()
