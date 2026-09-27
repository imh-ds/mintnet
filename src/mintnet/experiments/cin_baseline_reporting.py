"""Audit-oriented reporting and development-threshold selection for CIN."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .cin_baseline import DELTA_TOKENS, PanelConfig, _dataset, expected_row_count


DELTA_BY_TOKEN = dict(zip(DELTA_TOKENS, (0.0, 0.005, 0.01, 0.02)))
TOKEN_BY_DELTA = {value: token for token, value in DELTA_BY_TOKEN.items()}
REPORT_METRICS = (
    "ap", "prevalence", "ap_minus_prevalence", "strong_edge_recall",
    "categorical_excess_loss", "n_failed_pairs", "elapsed_seconds",
    "orientation_gap_q95",
)
IDENTITY_COLUMNS = {
    "case", "phase", "replicate", "method", "charter_sha256", "error_type",
    "error", "stability_error", "pair_sidecar_file", "stability_sidecar_file",
}


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
    for _, raw_row in raw.loc[promised.index].iterrows():
        file_name = str(raw_row["pair_sidecar_file"])
        path = Path(output_dir) / "sidecars" / Path(file_name).name
        if not path.exists():
            raise FileNotFoundError(f"promised sidecar is missing: {file_name}")
        table = pd.read_csv(path, compression="gzip")
        for column in ("case", "phase", "replicate", "method"):
            if column in raw_row and column not in table:
                table.insert(0, column, raw_row[column])
        tables.append(table)
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def _load_stability(raw: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    combined = Path(output_dir) / "sidecars" / "stability_all.csv.gz"
    if combined.exists():
        return pd.read_csv(combined, compression="gzip")
    promised = raw.get("stability_sidecar_file", pd.Series(dtype=object)).dropna()
    tables: list[pd.DataFrame] = []
    for _, raw_row in raw.loc[promised.index].iterrows():
        file_name = str(raw_row["stability_sidecar_file"])
        path = Path(output_dir) / "sidecars" / Path(file_name).name
        if not path.exists():
            raise FileNotFoundError(f"promised stability sidecar is missing: {file_name}")
        table = pd.read_csv(path, compression="gzip")
        for column in ("case", "phase", "replicate", "method"):
            if column in raw_row and column not in table:
                table.insert(0, column, raw_row[column])
        tables.append(table)
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
    recalls = pd.to_numeric(subset.get(f"delta_{token}_strong_recall"), errors="coerce")
    return {
        "case": case,
        "n": int(len(subset)),
        "n_nonempty": int(available.sum()),
        "nonempty_fraction": float(available.mean()) if len(subset) else float("nan"),
        "precision": float(precision.loc[available].mean()) if available.any() else float("nan"),
        "strong_recall": float(recalls.dropna().mean()) if recalls.notna().any() else float("nan"),
    }


def _unavailable_development_selection(
    config: PanelConfig,
    reason: str,
    *,
    observed_identities: int,
) -> dict[str, Any]:
    expected_identities = 2 * len(config.development_replicates)
    return {
        "selection_phase": "development",
        "selection_status": "unavailable",
        "selected_delta": None,
        "selected_token": None,
        "expected_gate_failure": True,
        "fallback_reason": reason,
        "rule": "qualify A/B at precision >= 0.70 and nonempty fraction >= 0.80; maximize strong recall, then choose smaller delta",
        "charter_sha256": config.charter_sha256,
        "development_identities_expected": expected_identities,
        "development_identities_observed": observed_identities,
        "candidates": [],
    }


def select_development_delta(raw: pd.DataFrame, config: PanelConfig) -> dict[str, Any]:
    """Select the display delta from development CIN A/B rows only."""

    identity_columns = {"case", "phase", "replicate", "method", "charter_sha256"}
    if not identity_columns <= set(raw.columns):
        return _unavailable_development_selection(
            config,
            "development rows are missing identity or charter columns",
            observed_identities=0,
        )
    development = raw.loc[
        (raw["phase"] == "development")
        & (raw["method"] == "cin")
        & raw["case"].isin(("A", "B"))
    ].copy()
    expected_identities = {
        (case, "development", replicate, "cin")
        for case in ("A", "B")
        for replicate in config.development_replicates
    }
    observed_count = len(development)
    if development.duplicated(["case", "phase", "replicate", "method"]).any():
        return _unavailable_development_selection(
            config,
            "A/B development input contains duplicate identities",
            observed_identities=observed_count,
        )
    if development["charter_sha256"].isna().any() or set(
        development["charter_sha256"].astype(str)
    ) != {config.charter_sha256}:
        return _unavailable_development_selection(
            config,
            "A/B development charter hash does not match the configured charter",
            observed_identities=observed_count,
        )
    replicate_values = pd.to_numeric(development["replicate"], errors="coerce")
    if (
        not np.isfinite(replicate_values).all()
        or not replicate_values.mod(1).eq(0).all()
    ):
        return _unavailable_development_selection(
            config,
            "A/B development input contains an invalid replicate identity",
            observed_identities=observed_count,
        )
    observed_identities = {
        (str(row.case), str(row.phase), int(row.replicate), str(row.method))
        for row in development.assign(replicate=replicate_values).itertuples(index=False)
    }
    if (
        observed_count != len(expected_identities)
        or observed_identities != expected_identities
    ):
        return _unavailable_development_selection(
            config,
            "A/B development identities do not match the configured replicate set",
            observed_identities=observed_count,
        )
    required_metrics = {
        f"delta_{_delta_token(delta)}_{field}"
        for delta in config.delta_candidates
        for field in ("precision", "empty", "strong_recall")
    }
    if not required_metrics <= set(development.columns):
        return _unavailable_development_selection(
            config,
            "A/B development rows are missing required threshold metrics",
            observed_identities=observed_count,
        )
    strong_counts = pd.to_numeric(
        development.get("n_strong_edges", pd.Series(np.nan, index=development.index)),
        errors="coerce",
    )
    recall_columns = [
        f"delta_{_delta_token(delta)}_strong_recall" for delta in config.delta_candidates
    ]
    if (
        not strong_counts.gt(0).all()
        or not np.isfinite(development[recall_columns].apply(pd.to_numeric, errors="coerce")).all().all()
    ):
        return _unavailable_development_selection(
            config,
            "A/B development strong-edge denominators or threshold recalls are unavailable",
            observed_identities=observed_count,
        )
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
    if raw.empty:
        return pd.DataFrame(columns=("case", "phase", "method", "metric", "mean", "mcse", "n", "availability"))
    del pairs  # Pair-level truth is not preserved in the exported sidecar; scalar truth metrics are in raw rows.
    metrics = list(dict.fromkeys((*REPORT_METRICS, *(
        column for column in raw.columns
        if column not in IDENTITY_COLUMNS
        and not column.endswith("_seed")
        and column not in {"n", "p", "replicate"}
        and (pd.api.types.is_numeric_dtype(raw[column]) or pd.api.types.is_bool_dtype(raw[column]))
    ))))
    if selected_delta is not None:
        token = _delta_token(selected_delta)
        metrics.extend((f"delta_{token}_{field}" for field in ("precision", "recall", "strong_recall", "displayed_fraction")))
    metrics = list(dict.fromkeys(metrics))
    records: list[dict[str, Any]] = []
    for (case, phase, method), group in raw.groupby(["case", "phase", "method"], dropna=False):
        for metric in metrics:
            values = group[metric] if metric in group else pd.Series(np.nan, index=group.index)
            mean, count, error = _mcse(values)
            records.append({
                "case": case,
                "phase": phase,
                "method": method,
                "metric": metric,
                "mean": mean,
                "mcse": error,
                "n": count,
                "availability": "available" if count else "unavailable",
            })
    return pd.DataFrame(records, columns=("case", "phase", "method", "metric", "mean", "mcse", "n", "availability"))


def _stability_summary(
    raw: pd.DataFrame,
    pairs: pd.DataFrame,
    stability: pd.DataFrame,
    config: PanelConfig,
) -> pd.DataFrame:
    """Summarize stable-subset precision/recall using the frozen simulation truth."""
    columns = ("case", "phase", "method", "metric", "mean", "mcse", "n", "availability")
    thresholds = tuple(round(value / 10, 1) for value in range(1, 11))
    metric_names = tuple(
        f"stability_{field}_at_{threshold:.1f}"
        for threshold in thresholds
        for field in ("precision", "recall", "selected_count")
    )
    if stability.empty or pairs.empty:
        return pd.DataFrame(
            [{"case": "all", "phase": "validation", "method": "cin", "metric": metric,
              "mean": np.nan, "mcse": np.nan, "n": 0, "availability": "unavailable"}
             for metric in metric_names],
            columns=columns,
        )
    required = {"fit_id", "repeat_id", "node_i", "node_j", "status", "weight_nats_raw", "gain_i_to_j", "gain_j_to_i"}
    if not required <= set(stability.columns):
        raise ValueError(f"stability sidecar is missing columns: {sorted(required - set(stability.columns))}")
    records: dict[tuple[str, str, str, float], list[float]] = {}
    identity = ["case", "phase", "replicate", "method"]
    if not set(identity) <= set(stability.columns) or not set(identity) <= set(pairs.columns):
        raise ValueError("validated sidecars are missing panel identity columns")
    for _, raw_row in raw.loc[raw.get("stability_sidecar_file", pd.Series(index=raw.index, dtype=object)).notna()].iterrows():
        repeats_requested = int(raw_row.get("stability_repeats_requested", config.stability_repeats))
        if repeats_requested < 1 or str(raw_row.get("stability_status", "")) == "error":
            continue
        row_identity = tuple(raw_row[column] for column in identity)
        match = pd.Series(True, index=stability.index)
        point_match = pd.Series(True, index=pairs.index)
        for column, value in zip(identity, row_identity):
            match &= stability[column].astype(str).eq(str(value))
            point_match &= pairs[column].astype(str).eq(str(value))
        repeat_table = stability.loc[match]
        point_table = pairs.loc[point_match]
        if repeat_table.empty or point_table.empty:
            continue
        case = str(raw_row["case"])
        generated = _dataset(
            case,
            int(raw_row["structure_seed"]),
            int(raw_row["sample_seed"]),
            config.n_overrides.get(case),
        )
        truth = {(str(left), str(right)) for left, right in generated[2]}
        by_pair: dict[tuple[str, str], pd.DataFrame] = {
            (str(left), str(right)): group
            for (left, right), group in repeat_table.groupby(["node_i", "node_j"], dropna=False)
        }
        point = point_table.loc[
            point_table["status"].eq("complete")
            & pd.to_numeric(point_table["weight_nats_raw"], errors="coerce").gt(0)
        ]
        predicted_by_threshold: dict[float, set[tuple[str, str]]] = {threshold: set() for threshold in thresholds}
        for pair, group in by_pair.items():
            complete = group.loc[group["status"].eq("complete")]
            if len(complete) != repeats_requested:
                continue
            weights = pd.to_numeric(complete["weight_nats_raw"], errors="coerce")
            gain_i = pd.to_numeric(complete["gain_i_to_j"], errors="coerce")
            gain_j = pd.to_numeric(complete["gain_j_to_i"], errors="coerce")
            repeat_fraction = float((weights.gt(0) & gain_i.gt(0) & gain_j.gt(0)).mean())
            if not bool(((point["node_i"].astype(str) == pair[0]) & (point["node_j"].astype(str) == pair[1])).any()):
                continue
            for threshold in thresholds:
                if repeat_fraction >= threshold:
                    predicted_by_threshold[threshold].add(pair)
        for threshold, predicted in predicted_by_threshold.items():
            precision = float(len(predicted & truth) / len(predicted)) if predicted else np.nan
            recall = float(len(predicted & truth) / len(truth)) if truth else np.nan
            prefix = (case, str(raw_row["phase"]), str(raw_row["method"]))
            records.setdefault((*prefix, threshold), []).extend((precision, recall, float(len(predicted))))
    output: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str, float], list[float]] = records
    expected_groups = {
        (str(row.case), str(row.phase), str(row.method), threshold)
        for row in raw.itertuples(index=False)
        if getattr(row, "stability_sidecar_file", None) is not None and pd.notna(getattr(row, "stability_sidecar_file", None))
        for threshold in thresholds
    }
    for key in sorted(expected_groups):
        values = groups.get(key, [])
        case, phase, method, threshold = key
        for index, field in enumerate(("precision", "recall", "selected_count")):
            numeric = pd.Series([values[offset] for offset in range(index, len(values), 3)])
            mean, count, error = _mcse(numeric)
            output.append({"case": case, "phase": phase, "method": method,
                           "metric": f"stability_{field}_at_{threshold:.1f}",
                           "mean": mean, "mcse": error, "n": count,
                           "availability": "available" if count else "unavailable"})
    return pd.DataFrame(output, columns=columns)


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
    stability = _load_stability(raw, target)
    selection = select_development_delta(raw, config)
    summary = _summary_rows(raw)
    metric_summary = aggregate_panel_metrics(raw, pairs, config, selection["selected_delta"])
    stability_summary = _stability_summary(raw, pairs, stability, config)
    metric_summary = pd.concat([metric_summary, stability_summary], ignore_index=True)
    summary.to_csv(target / "baseline_summary.csv", index=False, lineterminator="\n")
    metric_summary.to_csv(target / "panel_metrics.csv", index=False, lineterminator="\n")
    (target / "development_selection.json").write_text(
        json.dumps(_json_safe(selection), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    stability_status_counts = raw.get("stability_status", pd.Series(dtype=object)).fillna("not_requested").value_counts(dropna=False).to_dict()
    payload = {
        "configured_rows": expected_row_count(config),
        "emitted_rows": len(raw),
        "pair_rows": len(pairs),
        "status_counts": raw["status"].value_counts(dropna=False).to_dict(),
        "selected_delta": selection["selected_delta"],
        "charter_sha256": config.charter_sha256,
        "stability_status_counts": stability_status_counts,
        "stability_records": int(len(stability)),
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
        "",
        "## Metric summaries",
        "",
        "Mean, Monte Carlo standard error (MCSE), and contributing row count are shown. An unavailable value has no contributing finite observations; it is not zero.",
        "",
        "| Case | Phase | Method | Metric | Mean | MCSE | n | Availability |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for record in metric_summary.loc[metric_summary["case"] != "all"].to_dict(orient="records"):
        mean = "unavailable" if pd.isna(record["mean"]) else f"{record['mean']:.6g}"
        mcse = "unavailable" if pd.isna(record["mcse"]) else f"{record['mcse']:.6g}"
        lines.append(f"| {record['case']} | {record['phase']} | {record['method']} | {record['metric']} | {mean} | {mcse} | {record['n']} | {record['availability']} |")
    lines.extend(["", "## Stability descriptives", "",
                  "Stability is repeatability under the configured subsampling procedure, not an edge probability. Pair fractions use complete requested repeats only; incomplete repeats are kept unavailable.",
                  "", "| Metric | Mean | n pairs | Availability |", "|---|---:|---:|---|"])
    for record in stability_summary.to_dict(orient="records"):
        mean = "unavailable" if pd.isna(record["mean"]) else f"{record['mean']:.6g}"
        lines.append(f"| {record['metric']} | {mean} | {record['n']} | {record['availability']} |")
    lines.extend(["", "## Row and stability statuses", "", "| Status | Rows |", "|---|---:|"])
    status_counts = raw["status"].value_counts(dropna=False).to_dict() if "status" in raw else {}
    for status, count in sorted(status_counts.items(), key=lambda item: str(item[0])):
        lines.append(f"| {status} | {count} |")
    for status, count in sorted(stability_status_counts.items(), key=lambda item: str(item[0])):
        lines.append(f"| stability: {status} | {count} |")
    (target / "baseline_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "aggregate_panel_metrics", "select_development_delta", "write_report",
]
