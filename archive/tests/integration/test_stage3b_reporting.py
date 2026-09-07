from pathlib import Path

import pandas as pd

from mintnet.experiments.stage3b import Stage3bConfig
from mintnet.experiments.stage3b_reporting import evaluate_stage3b_gate, write_stage3b_report


def _config(pi_min_candidates=(0.80, 0.90, 0.95, 0.98)) -> Stage3bConfig:
    return Stage3bConfig(
        sample_sizes=(750,),
        strength=0.5,
        screening_alpha=0.001,
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
        "dgp": "overlap",
        "n": 750,
        "replicate": replicate,
        "data_seed": 1,
        "bootstrap_seed": 2,
        "dpi_alpha": 0.15,
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
    """1 true-direct edge (always present, pi=1.0), 1 chain + 1 fork indirect
    edge (always correctly pruned by the point estimate, absent), 4 overlap
    indirect edges (per-edge present/pi controlled by the caller -- this is
    where D-018's known failure mode is reproduced), 2 null edges (always
    absent)."""
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


def test_filtering_rescues_overlap_tpr_when_wrongly_kept_edges_are_less_stable_than_pi_min():
    """3 of 4 overlap edges are wrongly retained by the point estimate
    (baseline TPR = 1/4 = .25, well below the .80 gate), but their pi_final
    (.85) is comfortably below a pi_min=.90 filter, which removes them --
    while the one already-correctly-pruned edge stays pruned and the always-
    present true edge (pi_final=1.0) survives untouched."""
    rows = []
    for replicate in range(4):
        rows.extend(
            _replicate_rows(
                replicate,
                overlap_present=[True, True, True, False],
                overlap_pi=[0.85, 0.85, 0.85, 0.20],
            )
        )
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3b_gate(raw, _config())
    d = decision.by_n[0]

    assert d.baseline_overlap_indirect_tpr == 0.25
    assert d.status == "PROCEED"
    assert d.selected_pi_min == 0.90
    assert d.validation_overlap_indirect_tpr == 1.0
    assert d.validation_true_edge_fpr == 0.0


def test_reassesses_when_wrongly_kept_edges_are_more_stable_than_every_candidate():
    """Same wrongly-kept overlap edges, but now their pi_final (.99) exceeds
    even the highest candidate pi_min -- no threshold can rescue this case,
    and the charter should say so rather than silently pick the least-bad
    option."""
    rows = []
    for replicate in range(4):
        rows.extend(
            _replicate_rows(
                replicate,
                overlap_present=[True, True, True, False],
                overlap_pi=[0.99, 0.99, 0.99, 0.20],
            )
        )
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3b_gate(raw, _config())
    d = decision.by_n[0]

    assert d.status == "REASSESS"
    assert d.selected_pi_min is None
    assert "no eligible pi_min on development replicates" in d.failures[0]


def test_never_selects_a_pi_min_that_removes_a_true_edge():
    """If even the lowest candidate pi_min would strip the true edge (its
    pi_final dips to .75), that threshold must be ineligible even though it
    would otherwise clear the overlap TPR bar."""
    rows = []
    for replicate in range(4):
        r = _replicate_rows(
            replicate,
            overlap_present=[True, True, True, False],
            overlap_pi=[0.60, 0.60, 0.60, 0.20],
        )
        r[0] = _row(replicate, 0, 1, "true_direct", final_point=True, pi_final=0.75)
        rows.extend(r)
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3b_gate(raw, _config(pi_min_candidates=(0.80,)))
    d = decision.by_n[0]

    assert d.development_candidates[0].eligible is False
    assert d.status == "REASSESS"


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    rows = []
    for replicate in range(4):
        rows.extend(
            _replicate_rows(
                replicate,
                overlap_present=[True, True, True, False],
                overlap_pi=[0.85, 0.85, 0.85, 0.20],
            )
        )
    raw = pd.DataFrame(rows)

    decision = write_stage3b_report(raw, _config(), tmp_path)

    assert len(decision.by_n) == 1
    for filename in ("decision.json", "stage3b_report.md", "overlap_tpr_vs_pi_min.png", "before_after_filtering.png"):
        assert (tmp_path / filename).is_file()
