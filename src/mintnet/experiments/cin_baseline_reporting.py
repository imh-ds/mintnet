"""Audit-oriented reporting and development-threshold selection for CIN."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .cin_baseline import DELTA_TOKENS, PanelConfig, expected_row_count


DELTA_BY_TOKEN = dict(zip(DELTA_TOKENS, (0.0, 0.005, 0.01, 0.02)))
TOKEN_BY_DELTA = {value: token for token, value in DELTA_BY_TOKEN.items()}
REPORT_METRICS = (
    "ap", "prevalence", "ap_minus_prevalence", "strong_edge_recall",
    "categorical_excess_loss", "n_failed_pairs", "elapsed_seconds",
    "orientation_gap_q95",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _load_pairs(raw: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    promised = raw.get("pair_sidecar_file", pd.Series(dtype=object)).dropna()
    if promised.empty:
        return pd.DataFrame()
    combined = Path(output_dir) / "sidecars" / "pairs_all.csv.gz"
    if combined.exists():
        return pd.read_csv(combined, compression="gzip")
    tables: list[pd.DataFrame] = []
    for file_name in promised.astype(str):
        path = Path(output_dir) / "sidecars" / Path(file_name).name
        if not path.exists():
            raise FileNotFoundError(f"promised sidecar is missing: {file_name}")
        tables.append(pd.read_csv(path, compression="gzip"))
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def _delta_token(delta: float) -> str:
    value = round(float(delta), 12)
    for candidate, token in TOKEN_BY_DELTA.items():
        if value == candidate:
            return token
    raise ValueError(f"delta {delta} is not represented by the panel raw schema")


def _candidate_case_metrics(rows: pd.DataFrame, token: str, case: str) -> dict[str, Any]:
    subset = rows.loc[(rows["case"] == case) & (rows["method"] == "cin")].copy()
    precision = pd.to_numeric(subset.get(f"delta_{token}_precision"), errors="coerce")
    empty = subset.get(f"delta_{token}_empty", pd.Series(True, index=subset.index)).fillna(True).astype(bool)
    available = precision.notna() & ~empty
    recalls = pd.to_numeric(subset.get(f"delta_{token}_recall"), errors="coerce")
    return {
        "case": case,
        "n": int(len(subset)),
        "n_nonempty": int(available.sum()),
        "nonempty_fraction": float(available.mean()) if len(subset) else float("nan"),
        "precision": float(precision.loc[available].mean()) if available.any() else float("nan"),
        "strong_recall": float(recalls.dropna().mean()) if recalls.notna().any() else float("nan"),
    }


def select_development_delta(raw: pd.DataFrame, config: PanelConfig) -> dict[str, Any]:
    """Select the display delta from development CIN A/B rows only."""

    development = raw.loc[
        (raw["phase"] == "development")
        & (raw["method"] == "cin")
    ].copy()
    candidates: list[dict[str, Any]] = []
    for delta in config.delta_candidates:
        token = _delta_token(delta)
        case_metrics = [_candidate_case_metrics(development, token, case) for case in ("A", "B")]
        qualified = all(
            metric["n"] > 0
            and metric["precision"] >= 0.70
            and metric["nonempty_fraction"] >= 0.80
            for metric in case_metrics
        )
        valid_precisions = [metric["precision"] for metric in case_metrics if np.isfinite(metric["precision"])]
        valid_recalls = [metric["strong_recall"] for metric in case_metrics if np.isfinite(metric["strong_recall"])]
        candidates.append({
            "delta": float(delta),
            "token": token,
            "phase": "development",
            "qualified": qualified,
            "case_metrics": case_metrics,
            "minimum_precision": float(min(valid_precisions)) if len(valid_precisions) == 2 else float("nan"),
            "mean_strong_recall": float(np.mean(valid_recalls)) if len(valid_recalls) == 2 else float("nan"),
        })

    if any(not (development["case"] == case).any() for case in ("A", "B")):
        return {
            "selection_phase": "development",
            "selection_status": "unavailable",
            "selected_delta": None,
            "selected_token": None,
            "expected_gate_failure": True,
            "fallback_reason": "A/B development rows are required for threshold selection",
            "rule": "qualify A/B at precision >= 0.70 and nonempty fraction >= 0.80; maximize strong recall, then choose smaller delta",
            "charter_sha256": config.charter_sha256,
            "candidates": candidates,
        }

    qualified = [candidate for candidate in candidates if candidate["qualified"]]
    if qualified:
        selected = max(
            qualified,
            key=lambda candidate: (
                candidate["mean_strong_recall"],
                -candidate["delta"],
            ),
        )
        expected_gate_failure = False
        fallback_reason = None
    else:
        selected = max(
            candidates,
            key=lambda candidate: (
                candidate["minimum_precision"] if np.isfinite(candidate["minimum_precision"]) else -np.inf,
                -candidate["delta"],
            ),
        )
        expected_gate_failure = True
        fallback_reason = "no candidate met development precision/nonempty rule"

    return {
        "selection_phase": "development",
        "selection_status": "selected",
        "selected_delta": selected["delta"],
        "selected_token": selected["token"],
        "expected_gate_failure": expected_gate_failure,
        "fallback_reason": fallback_reason,
        "rule": "qualify A/B at precision >= 0.70 and nonempty fraction >= 0.80; maximize strong recall, then choose smaller delta",
        "charter_sha256": config.charter_sha256,
        "candidates": candidates,
    }


def _mcse(values: pd.Series) -> tuple[float, int, float]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    count = int(len(numeric))
    if count == 0:
        return float("nan"), 0, float("nan")
    mean = float(numeric.mean())
    error = float(numeric.std(ddof=1) / np.sqrt(count)) if count > 1 else float("nan")
    return mean, count, error


def aggregate_panel_metrics(
    raw: pd.DataFrame,
    pairs: pd.DataFrame,
    config: PanelConfig,
    selected_delta: float | None,
) -> pd.DataFrame:
    """Return long-form means, MCSEs, and denominators for report metrics."""

    del pairs  # Raw rows contain the audited scalar contract; sidecars are validated separately.
    if raw.empty:
        return pd.DataFrame(columns=("case", "phase", "method", "metric", "mean", "mcse", "n"))
    metrics = list(REPORT_METRICS)
    if selected_delta is not None:
        token = _delta_token(selected_delta)
        metrics.extend((f"delta_{token}_precision", f"delta_{token}_recall", f"delta_{token}_displayed_fraction"))
    records: list[dict[str, Any]] = []
    for (case, phase, method), group in raw.groupby(["case", "phase", "method"], dropna=False):
        for metric in metrics:
            if metric not in group:
                continue
            mean, count, error = _mcse(group[metric])
            records.append({
                "case": case,
                "phase": phase,
                "method": method,
                "metric": metric,
                "mean": mean,
                "mcse": error,
                "n": count,
            })
    return pd.DataFrame(records, columns=("case", "phase", "method", "metric", "mean", "mcse", "n"))


def _summary_rows(raw: pd.DataFrame) -> pd.DataFrame:
    return (
        raw.groupby(["case", "phase", "method"], dropna=False)
        .agg(
            rows=("status", "size"),
            complete=("status", lambda values: int((values == "complete").sum())),
            incomplete=("status", lambda values: int((values == "incomplete").sum())),
            failures=("status", lambda values: int((values == "error").sum())),
        )
        .reset_index()
    )


def write_report(raw: pd.DataFrame, config: PanelConfig, output_dir: Path) -> None:
    target = Path(output_dir)
    pairs = _load_pairs(raw, target)
    selection = select_development_delta(raw, config)
    summary = _summary_rows(raw)
    metric_summary = aggregate_panel_metrics(raw, pairs, config, selection["selected_delta"])
    summary.to_csv(target / "baseline_summary.csv", index=False, lineterminator="\n")
    metric_summary.to_csv(target / "panel_metrics.csv", index=False, lineterminator="\n")
    (target / "development_selection.json").write_text(
        json.dumps(_json_safe(selection), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    payload = {
        "configured_rows": expected_row_count(config),
        "emitted_rows": len(raw),
        "pair_rows": len(pairs),
        "status_counts": raw["status"].value_counts(dropna=False).to_dict(),
        "selected_delta": selection["selected_delta"],
        "charter_sha256": config.charter_sha256,
    }
    (target / "baseline_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# CIN statistical panel",
        "",
        f"Rows emitted: {len(raw)}; pair sidecar rows audited: {len(pairs)}.",
        f"Development-selected display delta: {selection['selected_delta']}",
        "Counts are preserved behind every aggregate; incomplete and failed methods remain visible.",
        "Monte Carlo standard errors are descriptive and do not establish tail probabilities or FDR control.",
        "Oracle CMI, regression, null, stability, and variance-only/XOR sections are descriptive or unsupported where no gate applies.",
        "This panel does not establish causal effects or broad recovery claims beyond named validation scopes.",
    ]
    (target / "baseline_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "aggregate_panel_metrics", "select_development_delta", "write_report",
]
