from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from mintnet.experiments.cin_baseline import load_config, methods_for_case
from scripts.cin_gate_check import _validate_aggregate_provenance, evaluate_validation_gates


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
                    "pair_sidecar_file": f"{case}_validation_{replicate}_{method}_pairs.csv.gz",
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
                    "point_fit_seconds": 1.0,
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
    assert result.loc[result["gate"] == "A_ap_prevalence", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "B_ap_prevalence", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "E_nonlinear_gain", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "F_categorical_loss", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "G_categorical_loss", "status"].iloc[0] == "pass"
    assert result.loc[result["gate"] == "D_descriptive", "status"].iloc[0] == "unavailable"
    assert result.loc[result["gate"] == "I_descriptive", "status"].iloc[0] == "unavailable"
    assert result["n_contributing"].notna().all()

    failed = evaluate_validation_gates(
        _validation_raw(ap_prevalence=0.10), config, selected_delta=0.01, charter_sha256=config.charter_sha256
    )
    assert failed.loc[failed["gate"] == "A_ap_prevalence", "status"].iloc[0] == "fail"
    assert failed.loc[failed["gate"] == "B_ap_prevalence", "status"].iloc[0] == "fail"


def test_validation_gates_require_each_named_case_to_pass() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    raw = _validation_raw()
    raw.loc[raw["case"] == "A", "delta_01_precision"] = 0.50
    raw.loc[raw["case"] == "G", "ap_minus_prevalence"] = 0.05
    raw.loc[raw["case"] == "F", "categorical_excess_loss"] = 0.20

    result = evaluate_validation_gates(
        raw, config, selected_delta=0.01, charter_sha256=config.charter_sha256
    )

    statuses = result.set_index("gate")["status"]
    assert statuses["A_selected_precision"] == "fail"
    assert statuses["B_selected_precision"] == "pass"
    assert statuses["G_ap_prevalence"] == "fail"
    assert statuses["F_ap_prevalence"] == "pass"
    assert statuses["F_categorical_loss"] == "fail"
    assert statuses["G_categorical_loss"] == "pass"


def test_strong_set_gate_fails_when_any_replicate_set_is_unavailable() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    raw = _validation_raw()
    missing = (raw["case"] == "A") & (raw["method"] == "cin")
    raw.loc[raw.index[missing][0], "n_strong_edges"] = None

    result = evaluate_validation_gates(
        raw, config, selected_delta=0.01, charter_sha256=config.charter_sha256
    )

    gate = result.loc[result["gate"] == "A_strong_set_exists"].iloc[0]
    assert gate["status"] == "fail"
    assert gate["n_contributing"] == len(config.validation_replicates)


@pytest.mark.parametrize(
    ("point_fit_seconds", "expected"),
    [
        (599.9, "pass"),
        (600.0, "pass"),
        (600.1, "fail"),
        (None, "fail"),
        (-1.0, "fail"),
        (float("inf"), "fail"),
    ],
)
def test_case_c_runtime_gate_enforces_point_fit_budget(point_fit_seconds, expected) -> None:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    raw = _validation_raw()
    selected = (raw["case"] == "C") & (raw["method"] == "cin")
    raw.loc[selected, "point_fit_seconds"] = point_fit_seconds

    result = evaluate_validation_gates(
        raw, config, selected_delta=0.01, charter_sha256=config.charter_sha256
    )
    gate = result.loc[result["gate"] == "C_runtime_completion"].iloc[0]

    assert gate["threshold"] == config.point_fit_max_seconds
    assert gate["status"] == expected


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


def test_validation_gates_refuse_missing_complete_pair_sidecar_promise() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline.yaml")
    raw = _validation_raw()
    raw.loc[0, "pair_sidecar_file"] = None
    with pytest.raises(ValueError, match="pair sidecar"):
        evaluate_validation_gates(raw, config, selected_delta=0.01, charter_sha256=config.charter_sha256)


def test_gate_provenance_binds_raw_config_and_charter(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "cin_baseline.yaml"
    config = load_config(config_path)
    raw_path = tmp_path / "raw_metrics.csv"
    raw_path.write_text("case\nA\n", encoding="utf-8")
    resolved_path = tmp_path / "resolved_config.yaml"
    resolved_path.write_bytes(config_path.read_bytes())
    resolved_hash = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    config_hash = hashlib.sha256(config_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    raw_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    metadata_path = tmp_path / "metadata.json"
    metadata = {
        "provenance_validated": True,
        "config_sha256": resolved_hash,
        "source_config_sha256": config_hash,
        "charter_sha256": config.charter_sha256,
        "git_commit": "abc123",
        "aggregated_raw_metrics_sha256": raw_hash,
        "shard_count": 1,
        "shards": [{"shard": "shard-1"}],
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    _validate_aggregate_provenance(raw_path, config_path, config, metadata_path)

    raw_path.write_text("case\nB\n", encoding="utf-8")
    with pytest.raises(ValueError, match="raw metrics"):
        _validate_aggregate_provenance(raw_path, config_path, config, metadata_path)
