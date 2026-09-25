from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mintnet.experiments.cin_baseline import load_config, methods_for_case
from scripts.cin_gate_check import evaluate_validation_gates


ROOT = Path(__file__).resolve().parents[2]


def _validation_raw(*, ap_prevalence: float = 0.25, e_gain: float = 0.2) -> pd.DataFrame:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    rows: list[dict[str, object]] = []
    for replicate in config.validation_replicates:
        for case in config.cases:
            for method in methods_for_case(case):
                ap = 0.30
                if case == "E" and method == "cin_linear":
                    ap -= e_gain
                row = {
                    "case": case,
                    "phase": "validation",
                    "replicate": replicate,
                    "method": method,
                    "status": "complete",
                    "charter_sha256": config.charter_sha256,
                    "ap": ap,
                    "prevalence": 0.05,
                    "ap_minus_prevalence": ap_prevalence if case in {"A", "B", "F", "G", "H"} else ap - 0.05,
                    "n_pairs_complete": 10,
                    "n_pairs_total": 10,
                    "n_failed_pairs": 0,
                    "delta_01_precision": 0.80,
                    "delta_01_empty": False,
                    "delta_01_recall": 0.60,
                    "delta_01_displayed_fraction": 0.90,
                    "n_strong_edges": 1,
                    "strong_edge_set_available": True,
                    "strong_edge_recall": 0.60,
                    "categorical_excess_loss": 0.05 if case in {"F", "G"} else None,
                    "elapsed_seconds": 1.0,
                }
                rows.append(row)
    raw = pd.DataFrame(rows)
    assert len(raw) == 400
    return raw


def test_validation_gates_report_pass_fail_and_unavailable_scopes() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    result = evaluate_validation_gates(
        _validation_raw(), config, selected_delta=0.01, charter_sha256=config.charter_sha256
    )

    assert set(result["status"]) <= {"pass", "fail", "unavailable"}
    assert result.loc[result["gate"] == "A_B_ap_prevalence", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "E_nonlinear_gain", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "FG_categorical_loss", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "D_descriptive", "status"].iloc[0] == "unavailable"
    assert result.loc[result["gate"] == "I_descriptive", "status"].iloc[0] == "unavailable"
    assert result["n_contributing"].notna().all()

    failed = evaluate_validation_gates(
        _validation_raw(ap_prevalence=0.10), config, selected_delta=0.01, charter_sha256=config.charter_sha256
    )
    assert failed.loc[failed["gate"] == "A_B_ap_prevalence", "status"].iloc[0] == "fail"


def test_validation_gates_refuse_development_contamination_and_count_mismatch() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    raw = _validation_raw()
    contaminated = pd.concat(
        [raw, raw.iloc[[0]].assign(phase="development", replicate=0)], ignore_index=True
    )
    with pytest.raises(ValueError, match="development"):
        evaluate_validation_gates(contaminated, config, selected_delta=0.01, charter_sha256=config.charter_sha256)

    with pytest.raises(ValueError, match="expected validation rows"):
        evaluate_validation_gates(raw.iloc[:-1], config, selected_delta=0.01, charter_sha256=config.charter_sha256)


def test_validation_gates_refuse_charter_mismatch() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    raw = _validation_raw()
    raw.loc[0, "charter_sha256"] = "wrong"
    with pytest.raises(ValueError, match="charter"):
        evaluate_validation_gates(raw, config, selected_delta=0.01, charter_sha256=config.charter_sha256)
