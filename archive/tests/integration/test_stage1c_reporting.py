from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1c import Stage1cConfig
from mintnet.experiments.stage1c_reporting import (
    compute_calibration,
    evaluate_stage1c_gate,
    write_stage1c_report,
)


def _config() -> Stage1cConfig:
    return Stage1cConfig(
        sample_sizes=(500, 750, 1000),
        strengths=(0.5,),
        triangle_families=("moderate",),
        alphas=(0.001, 0.05, 0.50),
        replicates=4,
        master_seed=20260829,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.8,
        maximum_triangle_true_edge_prune_fpr=0.1,
    )


def _raw_rows(*, n_500_always_fails: bool = False) -> pd.DataFrame:
    """Hand-checked evidence where the higher alpha pair passes at N >= 750."""
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        for n in (500, 750, 1000):
            for alpha in (0.001, 0.05, 0.50):
                for motif in ("chain", "fork", "triangle"):
                    indirect_tpr = 1.0 if motif != "triangle" else float("nan")
                    true_edge_fpr = 0.0
                    if alpha == 0.001:
                        indirect_tpr = 0.0 if motif != "triangle" else float("nan")
                        true_edge_fpr = 1.0
                    if n_500_always_fails and n == 500 and motif == "triangle":
                        true_edge_fpr = 1.0
                    rows.append(
                        {
                            "motif": motif,
                            "family": "moderate" if motif == "triangle" else "gaussian",
                            "strength": 0.5,
                            "n": n,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": 1,
                            "retained_01": True,
                            "retained_02": motif == "triangle",
                            "retained_12": True,
                            "partial_r_01": 0.5,
                            "partial_r_02": 0.0,
                            "partial_r_12": 0.5,
                            "p_value_01": 0.001,
                            "p_value_02": 0.9,
                            "p_value_12": 0.001,
                            "confidence_01": 0.999,
                            "confidence_02": 0.1,
                            "confidence_12": 0.999,
                            "indirect_prune_tpr": indirect_tpr,
                            "true_edge_prune_fpr": true_edge_fpr,
                            "perfect_recovery": 1.0 if alpha != 0.001 else 0.0,
                            "elapsed_seconds": 0.001,
                            "status": "ok",
                            "error": "",
                        }
                    )
    return pd.DataFrame(rows)


def test_gate_ignores_n_500_below_the_raised_floor() -> None:
    """N = 500 failing everything must not block a pair that passes at N >= 750."""
    decision = evaluate_stage1c_gate(_raw_rows(n_500_always_fails=True), _config())

    assert decision.status == "PROCEED"
    assert decision.selected_alpha_pair == (0.05, 0.50)


def test_gate_reassesses_when_a_required_development_cell_is_missing() -> None:
    """Pooled development metrics must not conceal a missing N >= 750 cell."""
    raw = _raw_rows()
    raw = raw.loc[
        ~(
            (raw["replicate"] == 0)
            & (raw["motif"] == "chain")
            & (raw["n"] == 750)
            & (raw["strength"] == 0.5)
            & (raw["alpha"] == 0.05)
        )
    ].copy()

    decision = evaluate_stage1c_gate(raw, _config())

    assert decision.status == "REASSESS"
    assert "missing development evidence" in decision.failures


def test_report_writes_passing_decision_and_required_evidence(tmp_path: Path) -> None:
    """Changing report integration must not omit the frozen gate evidence."""
    decision = write_stage1c_report(_raw_rows(), _config(), tmp_path)

    assert decision.status == "PROCEED"
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage1c_report.md",
        "dpi_operating_curve.png",
        "performance_vs_alpha.png",
        "runtime_vs_n.png",
        "calibration_summary.csv",
    ):
        assert (tmp_path / filename).is_file()


def test_calibration_still_reports_n_500_descriptively() -> None:
    """N = 500 is excluded from the gate but retained in exploratory evidence."""
    calibration = compute_calibration(_raw_rows(), _config())

    assert set(calibration["n"]) == {500, 750, 1000, "pooled"}
