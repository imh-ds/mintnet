from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage4j import Stage4jConfig
from mintnet.experiments.stage4j_fit import fitting_point_self_check


def _config() -> Stage4jConfig:
    return Stage4jConfig(
        sample_sizes=(400, 675, 725, 745),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_conditional_accuracy=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )


def _row(n, alpha, replicate, *, candidate: bool, correct: bool | None, fpr=0.0, status="ok", error=""):
    row = {
        "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "true_edge_prune_fpr": fpr, "status": status, "error": error,
    }
    for label in ("03", "04", "13", "14"):
        row[f"candidate_{label}"] = candidate
        row[f"correctly_pruned_{label}"] = correct if candidate else None
    return row


def test_evaluate_n_flags_dense_region_correctly():
    from mintnet.experiments.stage4j_reporting import evaluate_n

    rows = [_row(725, 0.10, r, candidate=True, correct=True) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 725, _config())

    assert decision.dense_region is True
    assert decision.status == "PROCEED"


def test_evaluate_n_flags_coarse_region_correctly():
    from mintnet.experiments.stage4j_reporting import evaluate_n

    rows = [_row(400, 0.10, r, candidate=True, correct=True) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 400, _config())

    assert decision.dense_region is False


def test_evaluate_n_reassesses_on_invalid_negative_alpha():
    from mintnet.experiments.stage4j_reporting import evaluate_n

    rows = [_row(745, -0.002, r, candidate=False, correct=None, status="error", error="ValueError: not a valid probability") for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 745, _config())

    assert decision.status == "REASSESS"
    assert any("not a valid probability" in f for f in decision.failures)


def test_report_writes_required_evidence_and_partial_dense_summary(tmp_path: Path) -> None:
    from mintnet.experiments.stage4j_reporting import write_stage4j_report

    fitting_points = ((300.0, 0.2), (500.0, 0.05), (700.0, 0.01), (710.0, 0.01), (750.0, 0.005))
    forms = fit_candidate_forms(fitting_points)
    selected = select_form(forms)
    self_check = fitting_point_self_check(selected, fitting_points)

    rows = []
    for n in (400, 675, 725, 745):
        for replicate in range(4):
            rows.append(_row(n, selected.predict(float(n)), replicate, candidate=True, correct=True))
    raw = pd.DataFrame(rows)

    decision = write_stage4j_report(raw, _config(), fitting_points, self_check, selected, tmp_path)

    assert len(decision.by_n) == len(_config().sample_sizes)
    assert sum(1 for d in decision.by_n if d.dense_region) == 2  # 725, 745
    for filename in ("decision.json", "stage4j_report.md", "alpha_n_fit.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4j_report.md").read_text(encoding="utf-8")
    assert "dense-region held-out points PROCEED" in report_text
