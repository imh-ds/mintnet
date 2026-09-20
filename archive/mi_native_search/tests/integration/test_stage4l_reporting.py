from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4l import Stage4lConfig


def _config() -> Stage4lConfig:
    return Stage4lConfig(
        strengths=(0.3, 0.5),
        sample_sizes=(750, 1500),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _row(
    strength, n, alpha, replicate, *,
    chain_tpr=1.0, fork_tpr=1.0, hub_tpr=1.0, true_fpr=0.0,
    screening_fer=0.0, final_fer=0.0, status="ok", error="",
    pair_candidates=None, pair_correct=None,
):
    pair_candidates = pair_candidates or {"02": True, "35": True, "78": True}
    pair_correct = pair_correct or {label: True for label in pair_candidates}
    row = {
        "strength": strength, "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "chain_indirect_tpr": chain_tpr, "fork_indirect_tpr": fork_tpr, "hub_indirect_tpr": hub_tpr,
        "true_edge_prune_fpr": true_fpr, "screening_false_edge_rate": screening_fer,
        "final_false_edge_rate": final_fer, "status": status, "error": error,
    }
    for label, is_candidate in pair_candidates.items():
        row[f"candidate_{label}"] = is_candidate
        row[f"correctly_pruned_{label}"] = pair_correct[label] if is_candidate else np.nan
        row[f"tested_neighbors_{label}"] = "1" if is_candidate else ""
    return row


def test_evaluate_cell_proceeds_with_clean_evidence():
    from mintnet.experiments.stage4l_reporting import evaluate_cell

    rows = [_row(0.3, 750, 0.10, r) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, 0.3, 750, _config())

    assert decision.status == "PROCEED"
    assert not decision.failures


def test_evaluate_cell_reassesses_on_low_chain_tpr():
    from mintnet.experiments.stage4l_reporting import evaluate_cell

    rows = [_row(0.3, 750, 0.10, r, chain_tpr=0.5) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, 0.3, 750, _config())

    assert decision.status == "REASSESS"
    assert any("chain indirect TPR" in f for f in decision.failures)


def test_evaluate_cell_reassesses_on_final_fer_exceeding_tolerance():
    from mintnet.experiments.stage4l_reporting import evaluate_cell

    rows = [_row(0.3, 750, 0.10, r, screening_fer=0.05, final_fer=0.10) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, 0.3, 750, _config())

    assert decision.status == "REASSESS"
    assert any("final false-edge rate" in f for f in decision.failures)


def test_report_writes_required_evidence_and_skips_comparison_without_stage4k_path(tmp_path: Path) -> None:
    from mintnet.experiments.stage4l_reporting import write_stage4l_report

    config = _config()
    rows = []
    for strength in config.strengths:
        for n in config.sample_sizes:
            chain_tpr = 0.5 if (strength == 0.3 and n == 750) else 1.0
            for replicate in range(4):
                rows.append(_row(strength, n, 0.10, replicate, chain_tpr=chain_tpr))
    raw = pd.DataFrame(rows)

    decision = write_stage4l_report(raw, config, tmp_path)

    assert decision.overall_status == "REASSESS"
    assert len(decision.by_cell) == 4
    for filename in ("decision.json", "stage4l_report.md", "indirect_tpr_by_strength_n.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4l_report.md").read_text(encoding="utf-8")
    assert "comparison skipped" in report_text


def test_report_includes_isolated_comparison_when_stage4k_path_given(tmp_path: Path) -> None:
    from mintnet.experiments.stage4l_reporting import write_stage4l_report

    config = _config()
    rows = []
    for strength in config.strengths:
        for n in config.sample_sizes:
            chain_tpr = 0.5 if (strength == 0.3 and n == 750) else 1.0
            for replicate in range(4):
                rows.append(_row(strength, n, 0.10, replicate, chain_tpr=chain_tpr))
    raw = pd.DataFrame(rows)

    stage4k_rows = []
    for motif in ("chain", "fork", "hub"):
        for replicate in range(1000):
            stage4k_rows.append(
                {
                    "motif": motif, "strength": 0.3, "n": 750, "alpha": 0.10, "replicate": replicate, "seed": 1,
                    "candidate": True, "correctly_pruned": True, "true_edge_prune_fpr": 0.0,
                    "status": "ok", "error": "",
                }
            )
    stage4k_path = tmp_path / "stage4k_raw_metrics.csv"
    pd.DataFrame(stage4k_rows).to_csv(stage4k_path, index=False)

    decision = write_stage4l_report(raw, config, tmp_path, stage4k_path)

    assert decision.overall_status == "REASSESS"
    report_text = (tmp_path / "stage4l_report.md").read_text(encoding="utf-8")
    assert "Isolated-vs-composed comparison (failing cells only" in report_text
    assert "isolated candidacy (Stage 4k)" in report_text
