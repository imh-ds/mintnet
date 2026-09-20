from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1b import Stage1bConfig
from mintnet.experiments.stage1b_reporting import (
    compute_calibration,
    evaluate_stage1b_gate,
    write_stage1b_report,
)


def _config() -> Stage1bConfig:
    return Stage1bConfig(
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


def _raw_rows(*, failed_fork_cell: bool = False) -> pd.DataFrame:
    """Return hand-checked evidence where the higher alpha pair passes development."""
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        for n in (500, 750, 1000):
            for alpha in (0.001, 0.05, 0.50):
                for motif in ("chain", "fork", "triangle"):
                    indirect_tpr = 1.0 if motif != "triangle" else float("nan")
                    true_edge_fpr = 0.0
                    if failed_fork_cell and (replicate, n, alpha, motif) == (3, 750, 0.05, "fork"):
                        indirect_tpr = 0.0
                    if alpha == 0.001:
                        indirect_tpr = 0.0 if motif != "triangle" else float("nan")
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


def test_gate_requires_the_development_pair_to_pass_each_validation_cell() -> None:
    """A weak validation fork cell must prevent progression after selection."""
    decision = evaluate_stage1b_gate(_raw_rows(failed_fork_cell=True), _config())

    assert decision.status == "REASSESS"
    assert "fork indirect-edge TPR" in decision.failures


def test_gate_reassesses_when_a_required_development_cell_is_missing() -> None:
    """Pooled development metrics must not conceal a missing required cell."""
    raw = _raw_rows()
    raw = raw.loc[
        ~(
            (raw["replicate"] == 0)
            & (raw["motif"] == "chain")
            & (raw["n"] == 500)
            & (raw["strength"] == 0.5)
            & (raw["alpha"] == 0.001)
        )
    ].copy()

    decision = evaluate_stage1b_gate(raw, _config())

    assert decision.status == "REASSESS"
    assert "missing development evidence" in decision.failures


def test_gate_reassesses_when_a_validation_replicate_is_missing() -> None:
    """A partial validation cell must not pass by averaging its remaining row."""
    raw = _raw_rows()
    raw = raw.loc[
        ~(
            (raw["replicate"] == 3)
            & (raw["motif"] == "fork")
            & (raw["n"] == 750)
            & (raw["strength"] == 0.5)
            & (raw["alpha"] == 0.05)
        )
    ].copy()

    decision = evaluate_stage1b_gate(raw, _config())

    assert decision.status == "REASSESS"
    assert "missing validation evidence" in decision.failures


def test_report_writes_passing_decision_and_required_evidence(tmp_path: Path) -> None:
    """Changing report integration must not omit the frozen gate evidence."""
    decision = write_stage1b_report(_raw_rows(), _config(), tmp_path)

    assert decision.status == "PROCEED"
    assert decision.selected_alpha_pair == (0.05, 0.50)
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage1b_report.md",
        "dpi_operating_curve.png",
        "performance_vs_alpha.png",
        "runtime_vs_n.png",
        "calibration_summary.csv",
    ):
        assert (tmp_path / filename).is_file()


def test_calibration_is_exploratory_and_uses_development_replicates_only() -> None:
    calibration = compute_calibration(_raw_rows(), _config())

    assert set(calibration["n"]) == {500, 750, 1000, "pooled"}
    assert (calibration["brier_score"] >= 0).all()
    assert (calibration["brier_score"] <= 1).all()
