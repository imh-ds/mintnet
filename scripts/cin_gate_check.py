"""Evaluate the frozen CIN Task 11 validation gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from mintnet.experiments.cin_baseline import (
    PanelConfig,
    methods_for_case,
)


def _expected_validation_rows(config: PanelConfig) -> int:
    return sum(len(methods_for_case(case)) for case in config.cases) * len(config.validation_replicates)


def _expected_validation_keys(config: PanelConfig) -> set[tuple[str, str, int, str]]:
    return {
        (case, "validation", replicate, method)
        for case in config.cases
        for replicate in config.validation_replicates
        for method in methods_for_case(case)
    }


def _numeric(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()


def _gate(
    name: str,
    threshold: object,
    values: pd.Series,
    predicate: Callable[[float], bool],
    *,
    scope: str = "gated",
) -> dict[str, object]:
    numeric = _numeric(values)
    if numeric.empty:
        return {
            "gate": name, "threshold": threshold, "observed": None,
            "n_contributing": 0, "status": "unavailable", "scope": scope,
        }
    observed = float(numeric.mean())
    return {
        "gate": name, "threshold": threshold, "observed": observed,
        "n_contributing": int(len(numeric)),
        "status": "pass" if predicate(observed) else "fail",
        "scope": scope,
    }


def _descriptive(name: str, raw: pd.DataFrame, case: str) -> dict[str, object]:
    count = int((raw["case"] == case).sum())
    return {
        "gate": name, "threshold": "descriptive", "observed": float(count),
        "n_contributing": count, "status": "unavailable", "scope": "descriptive",
    }


def _validate_input(
    raw: pd.DataFrame,
    config: PanelConfig,
    *,
    selected_delta: float,
    charter_sha256: str,
) -> None:
    if selected_delta not in config.delta_candidates:
        raise ValueError(f"selected delta {selected_delta} is not in the frozen configuration")
    if charter_sha256 != config.charter_sha256:
        raise ValueError("selection charter hash does not match the configured charter")
    if "charter_sha256" not in raw.columns or raw["charter_sha256"].isna().any():
        raise ValueError("validation rows are missing charter provenance")
    if set(raw["charter_sha256"].astype(str)) != {config.charter_sha256}:
        raise ValueError("validation charter hash mismatch")
    if "phase" not in raw.columns or raw["phase"].eq("development").any():
        raise ValueError("validation input contains development rows")
    if set(raw["phase"].dropna().astype(str)) != {"validation"}:
        raise ValueError("validation input must contain only validation rows")
    identity_columns = ["case", "phase", "replicate", "method"]
    if raw.duplicated(identity_columns).any():
        raise ValueError("validation input contains duplicate identities")
    expected = _expected_validation_keys(config)
    actual = set(
        (
            str(row.case), str(row.phase), int(row.replicate), str(row.method)
        )
        for row in raw[identity_columns].itertuples(index=False)
    )
    if len(raw) != _expected_validation_rows(config) or actual != expected:
        raise ValueError(
            f"expected validation rows {_expected_validation_rows(config)}, got {len(raw)}"
        )
    missing = {"status", "ap", "prevalence", "ap_minus_prevalence"} - set(raw.columns)
    if missing:
        raise ValueError(f"validation rows are missing required fields: {sorted(missing)}")
    if "pair_sidecar_file" not in raw.columns:
        raise ValueError("validation rows are missing pair sidecar promises")
    complete = raw["status"].eq("complete")
    promised = raw["pair_sidecar_file"].notna() & raw["pair_sidecar_file"].astype(str).str.strip().ne("")
    if (complete & ~promised).any():
        raise ValueError("complete validation rows are missing a pair sidecar promise")


def evaluate_validation_gates(
    raw: pd.DataFrame,
    config: PanelConfig,
    *,
    selected_delta: float,
    charter_sha256: str,
) -> pd.DataFrame:
    """Validate the frozen validation input and return one row per gate."""

    _validate_input(
        raw,
        config,
        selected_delta=selected_delta,
        charter_sha256=charter_sha256,
    )
    token = {0.005: "005", 0.01: "01", 0.02: "02"}[round(selected_delta, 12)]
    cin = raw.loc[raw["method"] == "cin"].copy()
    gates: list[dict[str, object]] = []
    complete_fraction = raw["status"].eq("complete").astype(float)
    gates.append(_gate("completion", 1.0, complete_fraction, lambda value: value == 1.0))

    for case in ("A", "B"):
        case_rows = cin.loc[cin["case"] == case]
        gates.append(_gate(
            f"{case}_ap_prevalence",
            0.20,
            case_rows["ap_minus_prevalence"],
            lambda value: value >= 0.20,
        ))
        gates.append(_gate(
            f"{case}_selected_precision",
            0.70,
            case_rows[f"delta_{token}_precision"],
            lambda value: value >= 0.70,
        ))
        nonempty = (~case_rows[f"delta_{token}_empty"].fillna(True).astype(bool)).astype(float)
        gates.append(_gate(
            f"{case}_selected_nonempty", 0.80, nonempty, lambda value: value >= 0.80
        ))
        recall_column = f"delta_{token}_strong_recall"
        recalls = case_rows[recall_column] if recall_column in case_rows else pd.Series(dtype=float)
        gates.append(_gate(
            f"{case}_selected_strong_recall", 0.50, recalls, lambda value: value >= 0.50
        ))
        strong_count = pd.to_numeric(
            case_rows.get("n_strong_edges", pd.Series(np.nan, index=case_rows.index)),
            errors="coerce",
        ).fillna(0)
        gates.append(_gate(
            f"{case}_strong_set_exists",
            1.0,
            (strong_count > 0).astype(float),
            lambda value: value == 1.0,
        ))

    e = raw.loc[raw["case"] == "E", ["replicate", "method", "ap"]].pivot(
        index="replicate", columns="method", values="ap"
    )
    e_gain = e["cin"] - e["cin_linear"] if {"cin", "cin_linear"} <= set(e.columns) else pd.Series(dtype=float)
    gates.append(_gate("E_nonlinear_gain", 0.10, e_gain, lambda value: value >= 0.10))

    for case in ("F", "G", "H"):
        case_rows = cin.loc[cin["case"] == case]
        gates.append(_gate(
            f"{case}_ap_prevalence",
            0.15,
            case_rows["ap_minus_prevalence"],
            lambda value: value >= 0.15,
        ))
    for case in ("F", "G"):
        case_rows = cin.loc[cin["case"] == case]
        gates.append(_gate(
            f"{case}_categorical_loss",
            0.10,
            case_rows["categorical_excess_loss"],
            lambda value: value <= 0.10,
        ))

    c = cin.loc[cin["case"] == "C"]
    point_fit_seconds = pd.to_numeric(
        c.get("point_fit_seconds", pd.Series(np.nan, index=c.index)), errors="coerce"
    )
    within_point_fit_budget = (
        np.isfinite(point_fit_seconds)
        & point_fit_seconds.ge(0)
        & point_fit_seconds.le(config.point_fit_max_seconds)
    )
    c_complete = c["status"].eq("complete") & within_point_fit_budget
    gates.append(_gate(
        "C_runtime_completion",
        config.point_fit_max_seconds,
        c_complete.astype(float),
        lambda value: value == 1.0,
    ))
    gates.extend([_descriptive("D_descriptive", raw, "D"), _descriptive("I_descriptive", raw, "I")])
    return pd.DataFrame(
        gates,
        columns=("gate", "threshold", "observed", "n_contributing", "status", "scope"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    from mintnet.experiments.cin_baseline import load_config

    config = load_config(args.config)
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    selected_delta = selection.get("selected_delta")
    if selected_delta is None:
        raise SystemExit("development selection has no frozen delta")
    raw = pd.read_csv(args.raw)
    result = evaluate_validation_gates(
        raw,
        config,
        selected_delta=float(selected_delta),
        charter_sha256=str(selection.get("charter_sha256", "")),
    )
    payload: dict[str, Any] = {
        "charter_sha256": config.charter_sha256,
        "selected_delta": float(selected_delta),
        "configured_validation_rows": _expected_validation_rows(config),
        "gates": result.to_dict(orient="records"),
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result.to_string(index=False))
    required = result.loc[result["scope"] == "gated", "status"]
    return 1 if required.isin(["fail", "unavailable"]).any() else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["evaluate_validation_gates", "main"]
