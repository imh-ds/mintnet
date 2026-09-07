from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage4i import Stage4iConfig
from mintnet.experiments.stage4i_fit import fitting_point_self_check


def _config() -> Stage4iConfig:
    return Stage4iConfig(
        sample_sizes=(400, 550, 750),
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


def test_evaluate_n_proceeds_with_comfortable_margin():
    from mintnet.experiments.stage4i_reporting import evaluate_n

    rows = [_row(400, 0.10, r, candidate=True, correct=True) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 400, _config())

    assert decision.status == "PROCEED"
    assert decision.alpha_hat == 0.10
    assert decision.conditional_accuracy == 1.0


def test_evaluate_n_reassesses_on_thin_margin():
    from mintnet.experiments.stage4i_reporting import evaluate_n

    rows = [_row(400, 0.10, 0, candidate=True, correct=True)]
    rows.append(_row(400, 0.10, 1, candidate=True, correct=True))
    rows.append(_row(400, 0.10, 2, candidate=True, correct=True))
    rows.append(_row(400, 0.10, 3, candidate=True, correct=False))
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 400, _config())

    assert decision.status == "REASSESS"
    assert any("conditional accuracy" in f for f in decision.failures)


def test_evaluate_n_reassesses_on_invalid_negative_alpha():
    from mintnet.experiments.stage4i_reporting import evaluate_n

    # Reproduces D-037's exact failure mode: a formula-predicted alpha
    # outside (0, 1) must be caught explicitly, not silently treated as a
    # normal missing-evidence case.
    rows = [_row(750, -0.0044, r, candidate=False, correct=None, status="error", error="ValueError: predicted alpha -0.0044 is not a valid probability") for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 750, _config())

    assert decision.status == "REASSESS"
    assert any("not a valid probability" in f for f in decision.failures)


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage4i_reporting import write_stage4i_report

    fitting_points = ((300.0, 0.2), (500.0, 0.05), (700.0, 0.01))
    forms = fit_candidate_forms(fitting_points)
    selected = select_form(forms)
    self_check = fitting_point_self_check(selected, fitting_points)

    rows = []
    for n in (400, 550):
        for replicate in range(4):
            rows.append(_row(n, selected.predict(float(n)), replicate, candidate=True, correct=True))
    raw = pd.DataFrame(rows)

    decision = write_stage4i_report(raw, _config(), fitting_points, self_check, selected, tmp_path)

    assert len(decision.by_n) == len(_config().sample_sizes)
    for filename in ("decision.json", "stage4i_report.md", "alpha_n_fit.png"):
        assert (tmp_path / filename).is_file()
