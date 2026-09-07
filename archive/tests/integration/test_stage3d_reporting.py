from pathlib import Path

import pandas as pd

from mintnet.experiments.stage3d import Stage3dConfig
from mintnet.experiments.stage3d_reporting import evaluate_stage3d_gate, write_stage3d_report


def _config() -> Stage3dConfig:
    return Stage3dConfig(
        sample_sizes=(750,),
        strength=0.5,
        screening_alpha=0.001,
        replicates=4,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        bootstraps=50,
        master_seed=20260829,
        pi_min_candidates=(0.70, 0.80, 0.90),
        minimum_stability_recall=0.90,
        maximum_stability_fdr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _row(replicate, i, j, category, *, pi_final, final_point) -> dict[str, object]:
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


def _replicate_rows(replicate: int, *, true_pi: float, null_pi: float, overlap_pi: float) -> list[dict[str, object]]:
    """10 true-direct, 1 chain + 1 fork indirect, 4 overlap indirect (all
    still present in the point estimate -- D-018's known failure mode --
    but at a controllable pi_final), and 10 null pairs."""
    rows: list[dict[str, object]] = []
    for k in range(10):
        rows.append(_row(replicate, k, k + 20, "true_direct", pi_final=true_pi, final_point=True))
    rows.append(_row(replicate, 30, 31, "indirect_chain", pi_final=0.3, final_point=False))
    rows.append(_row(replicate, 32, 33, "indirect_fork", pi_final=0.3, final_point=False))
    for k in range(4):
        rows.append(_row(replicate, 40 + k, 50 + k, "indirect_overlap", pi_final=overlap_pi, final_point=True))
    for k in range(10):
        rows.append(_row(replicate, 60 + k, 70 + k, "null", pi_final=null_pi, final_point=False))
    return rows


def test_proceeds_at_pi_min_regardless_of_wrongly_kept_indirect_overlap_edges():
    """The general gate only inspects true_direct/null -- it should PROCEED
    even though indirect_overlap edges are still present in every replicate's
    point estimate (final_point=True), the exact D-018 failure mode this
    gate is not designed to catch."""
    rows = []
    for replicate in range(4):
        rows.extend(_replicate_rows(replicate, true_pi=1.0, null_pi=0.0, overlap_pi=0.75))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3d_gate(raw, _config())
    d = decision.by_n[0]

    assert d.status == "PROCEED"
    assert d.selected_pi_min == 0.70
    assert d.validation_stability_recall == 1.0
    assert d.validation_stability_fdr == 0.0
    # Descriptive-only: these edges are wrongly kept in every point estimate,
    # invisible to the gate that just PROCEEDed.
    assert d.indirect_summary.category_pi_final_mean["indirect_overlap"] == 0.75


def test_reassesses_when_true_edges_are_never_stable_enough():
    rows = []
    for replicate in range(4):
        rows.extend(_replicate_rows(replicate, true_pi=0.5, null_pi=0.0, overlap_pi=0.75))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage3d_gate(raw, _config())
    d = decision.by_n[0]

    assert d.status == "REASSESS"
    assert d.selected_pi_min is None


def test_report_writes_required_evidence_including_indirect_table(tmp_path: Path) -> None:
    rows = []
    for replicate in range(4):
        rows.extend(_replicate_rows(replicate, true_pi=1.0, null_pi=0.0, overlap_pi=0.75))
    raw = pd.DataFrame(rows)

    decision = write_stage3d_report(raw, _config(), tmp_path)

    assert len(decision.by_n) == 1
    for filename in ("decision.json", "stage3d_report.md", "stability_by_category.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage3d_report.md").read_text(encoding="utf-8")
    assert "indirect_overlap" in report_text
    assert "does not mean D-018" in report_text
