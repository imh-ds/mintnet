"""Correctness-only report for the CIN cost pilot."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cin_cost import CostConfig


def write_report(raw: pd.DataFrame, config: CostConfig, output_dir: Path) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    summary = raw.copy()
    summary.to_csv(target / "cost_summary.csv", index=False, lineterminator="\n")
    complete = int((summary.get("status", pd.Series(dtype=str)) == "complete").sum())
    lines = [
        "# CIN cost pilot", "",
        "This is a cost pilot; timings are single-dataset measurements on shared hosted runners.",
        "Local smoke timings are correctness-only and are not compared with the proposed gates.", "",
        f"Configured rows: {len(config.cells) * len(config.repeats)}.",
        f"Rows emitted: {len(summary)}; complete rows: {complete}; failed rows: {len(summary) - complete}.", "",
        "The report records phase timings, factorization counts, fallback counts, pair completion, and RSS.",
        "It does not attach truth or quality claims to stress inputs.",
    ]
    (target / "cost_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ["write_report"]
