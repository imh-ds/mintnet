"""Correctness-only report for the CIN cost pilot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .cin_cost import CostConfig


GATE_NAMES = (
    "G-time-small",
    "G-time-100",
    "G-mem",
    "G-complete",
    "G-factor",
    "G-fallback",
)
GATE_THRESHOLDS = {
    "G-time-small": 30.0,
    "G-time-100": 180.0,
    "G-mem": 1024.0,
    "G-factor": 45.0,
    "G-fallback": 0.01,
}


def _numeric_max(rows: pd.DataFrame, column: str) -> float | None:
    if column not in rows:
        return None
    values = pd.to_numeric(rows[column], errors="coerce").dropna()
    return float(values.max()) if not values.empty else None


def _status_counts(row: pd.Series) -> dict[str, int]:
    value = row.get("status_histogram_json")
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            return {str(key): int(number) for key, number in parsed.items()}
    status = row.get("status")
    return {str(status): 1} if pd.notna(status) else {}


def _verdict(value: float | None, predicate: Any) -> str:
    return "not_run" if value is None else ("pass" if predicate(value) else "fail")


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for values in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join("" if pd.isna(value) else str(value) for value in values) + " |")
    return "\n".join(lines)


def evaluate_gates(raw: pd.DataFrame, config: CostConfig) -> pd.DataFrame:
    """Evaluate Task 10 gates once per configured cell.

    Timing uses the slower available repeat. A boundary repeat is required when
    repeat 1 lies in the charter's 20-percent band around its applicable gate.
    """

    rows: list[dict[str, Any]] = []
    configured = {cell.cell_id: cell for cell in config.cells}
    for cell_id, cell_rows in raw.groupby("cell", sort=False):
        cell = configured.get(str(cell_id))
        if cell is None:
            continue
        elapsed = _numeric_max(cell_rows, "elapsed_seconds")
        repeat_one = cell_rows.loc[cell_rows.get("repeat", pd.Series(dtype=int)) == 1]
        timing_limit_name = "G-time-small" if cell.p <= 30 else "G-time-100"
        timing_limit = GATE_THRESHOLDS[timing_limit_name]
        repeat_one_elapsed = _numeric_max(repeat_one, "elapsed_seconds")
        repeat_required = bool(
            repeat_one_elapsed is not None
            and 0.8 * timing_limit <= repeat_one_elapsed <= 1.25 * timing_limit
        )
        repeats = {
            int(value)
            for value in pd.to_numeric(cell_rows.get("repeat", pd.Series(dtype=int)), errors="coerce").dropna()
        }
        repeat_satisfied = not repeat_required or 2 in repeats
        timing_verdict = _verdict(
            elapsed if repeat_satisfied else None,
            lambda value: value <= timing_limit,
        )
        memory = _numeric_max(cell_rows, "peak_rss_mb")
        factors = _numeric_max(cell_rows, "n_large_factorizations")
        fallback = _numeric_max(cell_rows, "fallback_fraction")
        status_ok = True
        status_seen = False
        for _, row in cell_rows.iterrows():
            counts = _status_counts(row)
            if counts:
                status_seen = True
                status_ok &= set(counts) <= {"complete"}
            complete = row.get("n_pairs_complete")
            total = row.get("n_pairs_total")
            if pd.notna(complete) and pd.notna(total):
                status_seen = True
                status_ok &= float(complete) == float(total)
        rows.append({
            "cell": cell.cell_id,
            "kind": cell.kind,
            "p": cell.p,
            "n": cell.n,
            "effective_elapsed_seconds": elapsed,
            "repeat_required": repeat_required,
            "repeat_satisfied": repeat_satisfied,
            "G-time-small": "n/a" if cell.p > 30 else timing_verdict,
            "G-time-100": "n/a" if cell.p <= 30 else timing_verdict,
            "G-mem": _verdict(memory, lambda value: value < GATE_THRESHOLDS["G-mem"]),
            "G-complete": "not_run" if not status_seen else ("pass" if status_ok else "fail"),
            "G-factor": _verdict(factors, lambda value: value <= GATE_THRESHOLDS["G-factor"]),
            "G-fallback": _verdict(fallback, lambda value: value <= GATE_THRESHOLDS["G-fallback"]),
        })
    return pd.DataFrame(rows)


def write_report(raw: pd.DataFrame, config: CostConfig, output_dir: Path) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    summary = raw.copy()
    gate_summary = evaluate_gates(raw, config)
    if not gate_summary.empty:
        additions = gate_summary.set_index("cell")
        for column in gate_summary.columns:
            if column == "cell" or column in summary.columns:
                continue
            summary[column] = summary["cell"].map(additions[column])
    summary.to_csv(target / "cost_summary.csv", index=False, lineterminator="\n")
    complete = int((summary.get("status", pd.Series(dtype=str)) == "complete").sum())
    configured_count = len(config.cells) * len(config.repeats)
    runner_description = "ubuntu-latest GitHub-hosted runner; one process and one numerical thread per shard."
    lines = [
        "# CIN cost pilot", "",
        "This is a cost pilot; timings are single-dataset measurements on shared hosted runners.",
        "Local smoke runs are correctness-only and are not evidence against the hosted gates.",
        runner_description, "",
        f"Configured rows: {configured_count}.",
        f"Rows emitted: {len(summary)}; complete rows: {complete}; failed rows: {len(summary) - complete}.", "",
        "The report records phase timings, factorization counts, fallback counts, pair completion, status histograms, diagnostics, and RSS.",
        "Cost inputs carry no graph truth and the report makes no model-quality claim about them.",
    ]
    if not gate_summary.empty:
        lines.extend(["", "## Gate summary", "", _markdown_table(gate_summary)])
    (target / "cost_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ["GATE_NAMES", "GATE_THRESHOLDS", "evaluate_gates", "write_report"]
