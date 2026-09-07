from pathlib import Path

import pandas as pd
import pytest

from mintnet.experiments.stage1j import Stage1jConfig
from mintnet.experiments.stage1j_fit import FittedForm
from mintnet.experiments.stage1j_reporting import evaluate_stage1j_gate, write_stage1j_report


def _config() -> Stage1jConfig:
    return Stage1jConfig(
        sample_sizes=(900, 1250),
        strengths=(0.3, 0.5, 0.7),
        triangle_families=("balanced", "moderate", "strong"),
        replicates=4,
        master_seed=20260829,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_triangle_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )


def _selected_form() -> FittedForm:
    return FittedForm("linear_log_n", (0.5, -0.05), r_squared=0.99, n_parameters=2)


def _raw_rows() -> pd.DataFrame:
    """N=900: comfortable margin (passes). N=1250: margin below the required 0.02 (fails)."""
    values_by_n = {
        900: {"chain_tpr": 0.90, "fork_tpr": 0.90, "triangle_fpr": 0.05},  # margins: .10, .10, .05
        1250: {"chain_tpr": 0.81, "fork_tpr": 0.90, "triangle_fpr": 0.05},  # chain margin: .01 < .02
    }
    rows: list[dict[str, object]] = []
    for n, values in values_by_n.items():
        for replicate in range(4):
            for strength in (0.3, 0.5, 0.7):
                for motif, tpr in (("chain", values["chain_tpr"]), ("fork", values["fork_tpr"])):
                    rows.append(
                        {
                            "motif": motif,
                            "family": "gaussian",
                            "strength": strength,
                            "n": n,
                            "alpha": 0.10,
                            "replicate": replicate,
                            "seed": 1,
                            "retained_01": True,
                            "retained_02": False,
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
                            "indirect_prune_tpr": tpr,
                            "true_edge_prune_fpr": float("nan"),
                            "perfect_recovery": 1.0,
                            "elapsed_seconds": 0.001,
                            "status": "ok",
                            "error": "",
                        }
                    )
                rows.append(
                    {
                        "motif": "triangle",
                        "family": "moderate",
                        "strength": strength,
                        "n": n,
                        "alpha": 0.10,
                        "replicate": replicate,
                        "seed": 1,
                        "retained_01": True,
                        "retained_02": True,
                        "retained_12": True,
                        "partial_r_01": 0.5,
                        "partial_r_02": 0.3,
                        "partial_r_12": 0.5,
                        "p_value_01": 0.001,
                        "p_value_02": 0.05,
                        "p_value_12": 0.001,
                        "confidence_01": 0.999,
                        "confidence_02": 0.95,
                        "confidence_12": 0.999,
                        "indirect_prune_tpr": float("nan"),
                        "true_edge_prune_fpr": values["triangle_fpr"],
                        "perfect_recovery": 1.0,
                        "elapsed_seconds": 0.001,
                        "status": "ok",
                        "error": "",
                    }
                )
    return pd.DataFrame(rows)


def test_gate_requires_margin_at_least_the_configured_threshold():
    decision = evaluate_stage1j_gate(_raw_rows(), _config(), _selected_form())

    by_n = {d.n: d for d in decision.by_n}
    assert by_n[900].status == "PROCEED"
    assert by_n[900].margin == pytest.approx(0.05)
    assert by_n[1250].status == "REASSESS"
    assert "margin" in by_n[1250].failures[0]


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    decision = write_stage1j_report(_raw_rows(), _config(), _selected_form(), tmp_path)

    assert decision.selected_form == "linear_log_n"
    for filename in ("decision.json", "stage1j_report.md", "alpha_n_fit.png"):
        assert (tmp_path / filename).is_file()
