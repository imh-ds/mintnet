from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1 import Stage1Config
from mintnet.experiments.stage1_reporting import evaluate_stage1_gate, write_stage1_report


def _config() -> Stage1Config:
    return Stage1Config(
        sample_sizes=(500, 750, 1000),
        strengths=(0.5,),
        triangle_families=("moderate",),
        k=5,
        taus=(0.0, 0.2, 0.4),
        replicates=4,
        master_seed=20260829,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.8,
        maximum_triangle_true_edge_prune_fpr=0.1,
    )


def _raw_rows(*, failed_fork_cell: bool = False) -> pd.DataFrame:
    """Return hand-checked evidence where the lower tau pair passes development."""
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        for n in (500, 750, 1000):
            for tau in (0.0, 0.2, 0.4):
                for motif in ("chain", "fork", "triangle"):
                    indirect_tpr = 1.0 if motif != "triangle" else float("nan")
                    true_edge_fpr = 0.0
                    if failed_fork_cell and (replicate, n, tau, motif) == (3, 750, 0.2, "fork"):
                        indirect_tpr = 0.0
                    if tau == 0.4:
                        indirect_tpr = 0.0 if motif != "triangle" else float("nan")
                        true_edge_fpr = 1.0
                    rows.append(
                        {
                            "motif": motif,
                            "family": "moderate" if motif == "triangle" else "gaussian",
                            "strength": 0.5,
                            "n": n,
                            "k": 5,
                            "tau": tau,
                            "replicate": replicate,
                            "seed": 1,
                            "retained_01": True,
                            "retained_02": motif == "triangle",
                            "retained_12": True,
                            "indirect_prune_tpr": indirect_tpr,
                            "true_edge_prune_fpr": true_edge_fpr,
                            "perfect_recovery": 1.0 if tau != 0.4 else 0.0,
                            "elapsed_seconds": 0.001,
                            "status": "ok",
                            "error": "",
                        }
                    )
    return pd.DataFrame(rows)


def test_gate_requires_the_development_pair_to_pass_each_validation_cell() -> None:
    """A weak validation fork cell must prevent progression after selection."""
    decision = evaluate_stage1_gate(_raw_rows(failed_fork_cell=True), _config())

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
            & (raw["tau"] == 0.0)
        )
    ].copy()

    decision = evaluate_stage1_gate(raw, _config())

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
            & (raw["tau"] == 0.2)
        )
    ].copy()

    decision = evaluate_stage1_gate(raw, _config())

    assert decision.status == "REASSESS"
    assert "missing validation evidence" in decision.failures


def test_report_writes_passing_decision_and_required_evidence(tmp_path: Path) -> None:
    """Changing report integration must not omit the frozen gate evidence."""
    decision = write_stage1_report(_raw_rows(), _config(), tmp_path)

    assert decision.status == "PROCEED"
    assert decision.selected_tau_pair == (0.0, 0.2)
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage1_report.md",
        "dpi_operating_curve.png",
        "performance_vs_tau.png",
        "runtime_vs_n.png",
    ):
        assert (tmp_path / filename).is_file()
