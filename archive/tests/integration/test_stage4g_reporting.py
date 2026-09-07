from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage4g import Stage4gConfig


def _config() -> Stage4gConfig:
    return Stage4gConfig(
        sample_sizes=(400, 550),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_conditional_accuracy=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )


def _row(n, alpha, replicate, *, candidate: bool, correct: bool | None, fpr=0.0):
    row = {"n": n, "alpha": alpha, "replicate": replicate, "seed": 1, "true_edge_prune_fpr": fpr, "status": "ok", "error": ""}
    for label in ("03", "04", "13", "14"):
        row[f"candidate_{label}"] = candidate
        row[f"correctly_pruned_{label}"] = correct if candidate else None
    return row


def test_evaluate_n_proceeds_with_comfortable_margin():
    from mintnet.experiments.stage4g_reporting import evaluate_n

    rows = [_row(400, 0.10, r, candidate=True, correct=True) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 400, _config())

    assert decision.status == "PROCEED"
    assert decision.alpha_hat == 0.10
    assert decision.conditional_accuracy == 1.0


def test_evaluate_n_reassesses_on_thin_margin():
    from mintnet.experiments.stage4g_reporting import evaluate_n

    # Development replicates (0-1) are all correct; validation replicates
    # (2-3) split 3-correct/1-incorrect pairs = .75 pooled, below the .80
    # gate -- evaluate_n must use only the validation partition.
    rows = [_row(400, 0.10, 0, candidate=True, correct=True)]
    rows.append(_row(400, 0.10, 1, candidate=True, correct=True))
    rows.append(_row(400, 0.10, 2, candidate=True, correct=True))
    rows.append(_row(400, 0.10, 3, candidate=True, correct=False))
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 400, _config())

    assert decision.status == "REASSESS"
    assert any("conditional accuracy" in f for f in decision.failures)


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage4g_reporting import write_stage4g_report

    fitting_points = ((300.0, 0.2), (500.0, 0.05), (750.0, 0.005))
    forms = fit_candidate_forms(fitting_points)
    selected = select_form(forms)

    rows = []
    for n in (400, 550):
        for replicate in range(4):
            rows.append(_row(n, selected.predict(float(n)), replicate, candidate=True, correct=True))
    raw = pd.DataFrame(rows)

    decision = write_stage4g_report(raw, _config(), fitting_points, selected, tmp_path)

    assert len(decision.by_n) == 2
    for filename in ("decision.json", "stage4g_report.md", "alpha_n_fit.png"):
        assert (tmp_path / filename).is_file()
