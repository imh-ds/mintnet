from pathlib import Path

import pandas as pd

from mintnet.experiments.stage3 import Stage3Config
from mintnet.experiments.stage3_reporting import evaluate_secondary_diagnostic, evaluate_stage3_gate, write_stage3_report


def _config() -> Stage3Config:
    return Stage3Config(
        primary_sample_sizes=(750,),
        primary_strength=0.5,
        primary_triangle_family="moderate",
        primary_noise_count=6,
        primary_screening_alpha=0.001,
        primary_replicates=4,
        primary_development_replicates=(0, 1),
        primary_validation_replicates=(2, 3),
        secondary_sample_size=750,
        secondary_strength=0.5,
        secondary_screening_alpha=0.001,
        secondary_replicates=2,
        bootstraps=50,
        master_seed=20260829,
        pi_min_candidates=(0.70, 0.80, 0.90),
        minimum_stability_recall=0.90,
        maximum_stability_fdr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _primary_replicate_rows(replicate: int, *, true_pi: float, null_pi: float) -> list[dict[str, object]]:
    """3 true-direct edges, 2 indirect edges, 5 null edges -- enough to exercise
    the recall/FDR/no-regression computations without the real 105-pair DGP."""
    rows: list[dict[str, object]] = []
    for k in range(3):
        rows.append(_row("primary", 750, replicate, k, k + 1, "true_direct", pi_final=true_pi, final_point=true_pi >= 0.5))
    for k in range(2):
        rows.append(_row("primary", 750, replicate, 10 + k, 20 + k, "indirect", pi_final=0.5, final_point=False))
    for k in range(5):
        rows.append(_row("primary", 750, replicate, 30 + k, 40 + k, "null", pi_final=null_pi, final_point=null_pi >= 0.5))
    return rows


def _row(dgp, n, replicate, i, j, category, *, pi_final, final_point) -> dict[str, object]:
    return {
        "dgp": dgp,
        "n": n,
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


def _secondary_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for replicate in range(2):
        rows.append(_row("secondary_overlap_diagnostic", 750, replicate, 0, 1, "true_direct", pi_final=1.0, final_point=True))
        rows.append(_row("secondary_overlap_diagnostic", 750, replicate, 2, 3, "indirect_overlap", pi_final=0.55, final_point=True))
        rows.append(_row("secondary_overlap_diagnostic", 750, replicate, 4, 5, "null", pi_final=0.0, final_point=False))
    return rows


def test_proceeds_when_true_edges_stable_and_null_edges_unstable():
    rows = []
    for replicate in range(4):
        rows.extend(_primary_replicate_rows(replicate, true_pi=1.0, null_pi=0.0))
    rows.extend(_secondary_rows())
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3_gate(raw, _config())

    assert len(decision.by_n) == 1
    d = decision.by_n[0]
    assert d.status == "PROCEED"
    assert d.selected_pi_min == 0.70  # smallest eligible, all three thresholds pass here
    assert d.validation_stability_recall == 1.0
    assert d.validation_stability_fdr == 0.0


def test_reassesses_when_true_edges_are_never_stable_enough():
    rows = []
    for replicate in range(4):
        # true-direct edges only stable 50% of the time -- below the .90 recall
        # bar at every candidate pi_min, so no threshold should be eligible.
        rows.extend(_primary_replicate_rows(replicate, true_pi=0.5, null_pi=0.0))
    rows.extend(_secondary_rows())
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3_gate(raw, _config())

    d = decision.by_n[0]
    assert d.status == "REASSESS"
    assert d.selected_pi_min is None
    assert "no eligible pi_min on development replicates" in d.failures[0]


def test_reassesses_when_a_replicate_recorded_an_error():
    rows = []
    for replicate in range(4):
        rows.extend(_primary_replicate_rows(replicate, true_pi=1.0, null_pi=0.0))
    error_row = _row("primary", 750, 0, -1, -1, "", pi_final=float("nan"), final_point=False)
    error_row["status"] = "error"
    error_row["error"] = "RuntimeError: boom"
    rows.append(error_row)
    rows.extend(_secondary_rows())
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3_gate(raw, _config())

    d = decision.by_n[0]
    assert d.status == "REASSESS"
    assert "errors" in d.failures[0]


def test_secondary_diagnostic_reports_per_category_stability():
    raw = pd.DataFrame(_secondary_rows())
    diagnostic = evaluate_secondary_diagnostic(raw, _config())

    assert diagnostic.replicates_ok == 2
    assert diagnostic.category_pi_final_mean["true_direct"] == 1.0
    assert diagnostic.category_pi_final_mean["indirect_overlap"] == 0.55
    assert diagnostic.category_pi_final_mean["null"] == 0.0


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    rows = []
    for replicate in range(4):
        rows.extend(_primary_replicate_rows(replicate, true_pi=1.0, null_pi=0.0))
    rows.extend(_secondary_rows())
    raw = pd.DataFrame(rows)

    decision = write_stage3_report(raw, _config(), tmp_path)

    assert len(decision.by_n) == 1
    for filename in ("decision.json", "stage3_report.md", "stability_by_category.png", "secondary_overlap_diagnostic.png"):
        assert (tmp_path / filename).is_file()
