from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2j import P5, P10, Stage2jConfig


def _config() -> Stage2jConfig:
    return Stage2jConfig(
        sample_sizes=(750, 1500),
        strength=0.5,
        screening_alpha_grid=(0.05, 0.01, 0.001, 0.0001),
        fixed_alpha_p5=0.001,
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_recall=0.99,
        maximum_fdr=0.05,
        minimum_indirect_tpr=0.80,
        maximum_true_edge_fpr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _selection_row(n, replicate, alpha, *, true_positives, false_positives, true_pair_count=13):
    return {
        "n": n,
        "replicate": replicate,
        "seed": 1,
        "alpha": alpha,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "total_flagged": true_positives + false_positives,
        "true_pair_count": true_pair_count,
        "null_pair_count": 32,
        "status": "ok",
        "error": "",
    }


def test_select_alpha_p10_picks_smallest_eligible_and_confirms_on_validation():
    from mintnet.experiments.stage2j_reporting import evaluate_selection

    rows = []
    for replicate in range(4):
        # alpha=0.05 over-flags (fails FDR); alpha=0.001 clears both gates cleanly.
        rows.append(_selection_row(1500, replicate, 0.05, true_positives=13, false_positives=5))
        rows.append(_selection_row(1500, replicate, 0.001, true_positives=13, false_positives=0))
        rows.append(_selection_row(1500, replicate, 0.0001, true_positives=10, false_positives=0))
    selection_raw = pd.DataFrame(rows)

    decision = evaluate_selection(selection_raw, 1500, _config())

    assert decision.selected_alpha == 0.001
    assert decision.validation_recall == 1.0
    assert decision.validation_fdr == 0.0
    assert not decision.failures


def test_select_alpha_p10_reassesses_when_nothing_eligible():
    from mintnet.experiments.stage2j_reporting import evaluate_selection

    rows = [_selection_row(750, replicate, 0.05, true_positives=13, false_positives=10) for replicate in range(4)]
    selection_raw = pd.DataFrame(rows)

    decision = evaluate_selection(selection_raw, 750, _config())

    assert decision.selected_alpha is None
    assert "no eligible development alpha" in decision.failures


def _composition_row(p, n, replicate, *, chain_tpr, overlap_tpr, screening_fer, final_fer):
    return {
        "p": p,
        "n": n,
        "replicate": replicate,
        "seed": 1,
        "screening_alpha": 0.001,
        "dpi_alpha": 0.1,
        "chain_indirect_tpr": chain_tpr,
        "overlap_indirect_tpr": overlap_tpr,
        "true_edge_prune_fpr": 0.0,
        "screening_false_edge_rate": screening_fer,
        "final_false_edge_rate": final_fer,
        "overlap_clean_clique": float(overlap_tpr > 0),
        "status": "ok",
        "error": "",
    }


def test_p10_cell_proceeds_when_all_criteria_pass():
    from mintnet.experiments.stage2j_reporting import evaluate_cell

    rows = [
        _composition_row(P10, 1500, r, chain_tpr=1.0, overlap_tpr=0.9, screening_fer=0.0, final_fer=0.0)
        for r in range(4)
    ]
    composition_raw = pd.DataFrame(rows)

    decision = evaluate_cell(composition_raw, P10, 1500, _config())

    assert decision.status == "PROCEED"
    assert decision.chain_indirect_tpr == 1.0
    assert not decision.failures


def test_p5_cell_has_no_chain_or_false_edge_metrics_and_can_still_reassess():
    from mintnet.experiments.stage2j_reporting import evaluate_cell

    rows = [
        {
            "p": P5,
            "n": 750,
            "replicate": r,
            "seed": 1,
            "screening_alpha": 0.001,
            "dpi_alpha": 0.15,
            "chain_indirect_tpr": float("nan"),
            "overlap_indirect_tpr": 0.25,
            "true_edge_prune_fpr": 0.0,
            "screening_false_edge_rate": float("nan"),
            "final_false_edge_rate": float("nan"),
            "overlap_clean_clique": 0.0,
            "status": "ok",
            "error": "",
        }
        for r in range(4)
    ]
    composition_raw = pd.DataFrame(rows)

    decision = evaluate_cell(composition_raw, P5, 750, _config())

    assert decision.status == "REASSESS"
    assert decision.chain_indirect_tpr is None
    assert decision.screening_false_edge_rate is None
    assert decision.final_false_edge_rate is None
    assert any("overlap indirect TPR" in failure for failure in decision.failures)


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage2j_reporting import write_stage2j_report

    selection_rows = []
    for replicate in range(4):
        selection_rows.append(_selection_row(750, replicate, 0.001, true_positives=13, false_positives=0))
        selection_rows.append(_selection_row(1500, replicate, 0.001, true_positives=13, false_positives=0))
    selection_raw = pd.DataFrame(selection_rows)

    composition_rows = []
    for n in (750, 1500):
        for replicate in range(4):
            composition_rows.append(
                _composition_row(P10, n, replicate, chain_tpr=1.0, overlap_tpr=0.9, screening_fer=0.0, final_fer=0.0)
            )
            composition_rows.append(
                {
                    "p": P5, "n": n, "replicate": replicate, "seed": 1, "screening_alpha": 0.001,
                    "dpi_alpha": 0.1, "chain_indirect_tpr": float("nan"), "overlap_indirect_tpr": 0.9,
                    "true_edge_prune_fpr": 0.0, "screening_false_edge_rate": float("nan"),
                    "final_false_edge_rate": float("nan"), "overlap_clean_clique": 1.0,
                    "status": "ok", "error": "",
                }
            )
    composition_raw = pd.DataFrame(composition_rows)

    decision = write_stage2j_report(selection_raw, composition_raw, _config(), tmp_path)

    assert len(decision.by_cell) == 4
    for filename in ("decision.json", "stage2j_report.md", "overlap_tpr_by_p.png"):
        assert (tmp_path / filename).is_file()
