from pathlib import Path

import pandas as pd

from mintnet.experiments.stage3c import Stage3cConfig
from mintnet.experiments.stage3c_reporting import evaluate_stage3c_gate, write_stage3c_report


def _config(pi_min_candidates=(0.70, 0.80, 0.90)) -> Stage3cConfig:
    return Stage3cConfig(
        sample_sizes=(750,),
        strength=0.5,
        screening_alpha=0.001,
        replicates=4,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        bootstraps=50,
        master_seed=20260829,
        pi_min_candidates=pi_min_candidates,
        minimum_stability_recall=0.90,
        maximum_stability_fdr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _row(replicate, i, j, category, *, pi_final, final_point) -> dict[str, object]:
    return {
        "dgp": "hub",
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


def _replicate_rows(replicate: int, *, true_pi: float, null_pi: float) -> list[dict[str, object]]:
    """7 true-direct edges, 5 indirect edges, and enough null edges to make
    FDR/no-regression math meaningful, mirroring Stage 2c's ground truth
    counts without needing the full 105-pair DGP."""
    rows: list[dict[str, object]] = []
    for k in range(7):
        rows.append(_row(replicate, k, k + 10, "true_direct", pi_final=true_pi, final_point=true_pi >= 0.5))
    for k in range(5):
        rows.append(_row(replicate, 20 + k, 30 + k, "indirect", pi_final=0.5, final_point=False))
    for k in range(10):
        rows.append(_row(replicate, 40 + k, 50 + k, "null", pi_final=null_pi, final_point=null_pi >= 0.5))
    return rows


def test_proceeds_when_true_edges_stable_and_null_edges_unstable():
    rows = []
    for replicate in range(4):
        rows.extend(_replicate_rows(replicate, true_pi=1.0, null_pi=0.0))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3c_gate(raw, _config())
    d = decision.by_n[0]

    assert d.status == "PROCEED"
    assert d.selected_pi_min == 0.70
    assert d.validation_stability_recall == 1.0
    assert d.validation_stability_fdr == 0.0


def test_reassesses_when_true_edges_are_never_stable_enough():
    rows = []
    for replicate in range(4):
        rows.extend(_replicate_rows(replicate, true_pi=0.5, null_pi=0.0))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3c_gate(raw, _config())
    d = decision.by_n[0]

    assert d.status == "REASSESS"
    assert d.selected_pi_min is None
    assert "no eligible pi_min on development replicates" in d.failures[0]


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    rows = []
    for replicate in range(4):
        rows.extend(_replicate_rows(replicate, true_pi=1.0, null_pi=0.0))
    raw = pd.DataFrame(rows)

    decision = write_stage3c_report(raw, _config(), tmp_path)

    assert len(decision.by_n) == 1
    for filename in ("decision.json", "stage3c_report.md", "stability_by_category.png"):
        assert (tmp_path / filename).is_file()
