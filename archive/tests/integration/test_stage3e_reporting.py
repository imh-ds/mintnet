from pathlib import Path

import pandas as pd

from mintnet.experiments.stage3b import Stage3bConfig
from mintnet.experiments.stage3b_reporting import evaluate_stage3b_gate


def _config(pi_min_candidates=(0.80, 0.90, 0.95, 0.98)) -> Stage3bConfig:
    return Stage3bConfig(
        sample_sizes=(1500,),
        strength=0.5,
        screening_alpha=0.0001,
        replicates=4,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        bootstraps=50,
        master_seed=20260829,
        pi_min_candidates=pi_min_candidates,
        minimum_overlap_indirect_tpr=0.80,
        maximum_true_edge_fpr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _row(replicate, i, j, category, *, final_point, pi_final) -> dict[str, object]:
    return {
        "dgp": "overlap_p30",
        "n": 1500,
        "replicate": replicate,
        "data_seed": 1,
        "bootstrap_seed": 2,
        "dpi_alpha": 0.10,
        "i": i,
        "j": j,
        "category": category,
        "screened_point": final_point,
        "final_point": final_point,
        "pi_candidate": pi_final,
        "pi_final": pi_final,
        "successful_bootstraps": 50,
        "failed_bootstraps": 0,
        "status": "ok",
        "error": "",
    }


def _replicate_rows(replicate: int, *, overlap_present: list[bool], overlap_pi: list[float]) -> list[dict[str, object]]:
    rows = [_row(replicate, 0, 1, "true_direct", final_point=True, pi_final=1.0)]
    rows.append(_row(replicate, 2, 3, "indirect_chain", final_point=False, pi_final=0.3))
    rows.append(_row(replicate, 4, 5, "indirect_fork", final_point=False, pi_final=0.3))
    for k in range(4):
        rows.append(
            _row(
                replicate,
                10 + k,
                20 + k,
                "indirect_overlap",
                final_point=overlap_present[k],
                pi_final=overlap_pi[k],
            )
        )
    for k in range(2):
        rows.append(_row(replicate, 30 + k, 40 + k, "null", final_point=False, pi_final=0.0))
    return rows


def test_this_p30_dgp_reuses_stage3bs_gate_logic_unmodified():
    """A small, well-separated case (mirroring Stage 3e's own prediction that
    a smaller miss should need at most Stage 3b's pi_min=.80) should PROCEED
    -- confirms the reused evaluate_stage3b_gate works correctly on the
    'overlap_p30' dgp tag this charter introduces, not just 'overlap'."""
    rows = []
    for replicate in range(4):
        rows.extend(
            _replicate_rows(
                replicate,
                overlap_present=[True, True, False, False],
                overlap_pi=[0.6, 0.6, 0.2, 0.2],
            )
        )
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3b_gate(raw, _config())
    d = decision.by_n[0]

    assert d.status == "PROCEED"
    assert d.selected_pi_min == 0.80
    assert d.validation_overlap_indirect_tpr == 1.0
    assert d.validation_true_edge_fpr == 0.0


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage3e_reporting import write_stage3e_report

    rows = []
    for replicate in range(4):
        rows.extend(
            _replicate_rows(
                replicate,
                overlap_present=[True, True, False, False],
                overlap_pi=[0.6, 0.6, 0.2, 0.2],
            )
        )
    raw = pd.DataFrame(rows)

    decision = write_stage3e_report(raw, _config(), tmp_path)

    assert len(decision.by_n) == 1
    for filename in ("decision.json", "stage3e_report.md", "overlap_tpr_vs_pi_min.png", "before_after_filtering.png"):
        assert (tmp_path / filename).is_file()
