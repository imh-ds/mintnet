from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4e import Stage4eConfig


def _config() -> Stage4eConfig:
    return Stage4eConfig(
        sample_sizes=(500, 750),
        alphas=(0.05, 0.10, 0.20),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_conditional_accuracy=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )


def _row(n, alpha, replicate, *, candidates: dict[str, bool | None], fpr: float):
    row: dict[str, object] = {
        "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "true_edge_prune_fpr": fpr, "status": "ok", "error": "",
    }
    for label, is_candidate in candidates.items():
        if is_candidate is None:
            row[f"candidate_{label}"] = False
            row[f"correctly_pruned_{label}"] = np.nan
        else:
            row[f"candidate_{label}"] = True
            row[f"correctly_pruned_{label}"] = is_candidate
    return row


def test_conditional_accuracy_ignores_non_candidates():
    from mintnet.experiments.stage4e_reporting import _pooled_metrics

    rows = []
    for replicate in range(4):
        # 03 and 04 always candidates, correctly pruned; 13 never a candidate
        # (should be excluded, not counted as wrongly retained); 14 candidate
        # but wrongly retained -- overall accuracy should reflect only the 3
        # candidate pairs (03, 04, 14), not all 4.
        rows.append(
            _row(750, 0.10, replicate, candidates={"03": True, "04": True, "13": None, "14": False}, fpr=0.0)
        )
    raw = pd.DataFrame(rows)

    candidacy_rate, conditional_accuracy, fpr = _pooled_metrics(raw, 750, 0.10)

    # 2 correct out of 3 candidates = .667, well below the .80 gate --
    # excluding pair 13 (never a candidate) from both numerator and
    # denominator entirely, rather than counting it as wrongly retained.
    assert candidacy_rate == 3 / 4
    assert abs(conditional_accuracy - (2 / 3)) < 1e-9
    assert fpr == 0.0


def test_below_gate_accuracy_leaves_no_eligible_development_alpha():
    from mintnet.experiments.stage4e_reporting import evaluate_n

    rows = []
    for replicate in range(4):
        rows.append(
            _row(750, 0.10, replicate, candidates={"03": True, "04": True, "13": None, "14": False}, fpr=0.0)
        )
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 750, _config())

    assert decision.status == "REASSESS"
    assert "no eligible development alpha" in decision.failures


def test_select_alpha_requires_at_least_one_candidate():
    from mintnet.experiments.stage4e_reporting import select_alpha

    rows = []
    for replicate in range(4):
        rows.append(_row(500, 0.05, replicate, candidates={"03": None, "04": None, "13": None, "14": None}, fpr=0.0))
        rows.append(_row(500, 0.10, replicate, candidates={"03": True, "04": True, "13": True, "14": True}, fpr=0.0))
    raw = pd.DataFrame(rows)

    selected = select_alpha(raw, 500, _config())

    assert selected == 0.10  # 0.05 has zero candidates, ineligible regardless of accuracy


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage4e_reporting import write_stage4e_report

    rows = []
    for n in (500, 750):
        for replicate in range(4):
            rows.append(
                _row(n, 0.10, replicate, candidates={"03": True, "04": True, "13": True, "14": True}, fpr=0.0)
            )
    raw = pd.DataFrame(rows)

    decision = write_stage4e_report(raw, _config(), tmp_path)

    assert len(decision.by_n) == 2
    for filename in ("decision.json", "stage4e_report.md", "candidacy_vs_accuracy_by_n.png"):
        assert (tmp_path / filename).is_file()
