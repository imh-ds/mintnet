"""Reporting for the Stage 7 isolation-tier timing/feasibility
measurement. Purely descriptive (no gate) -- this measurement's own
purpose is to size the real charter run's replicate count, not to
validate anything. See docs/stage7_charter.md.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage7_isolation_timing import Stage7TimingConfig


def summarize(raw: pd.DataFrame) -> pd.DataFrame:
    ok = raw.loc[raw["status"] == "ok"].copy()
    if ok.empty:
        return pd.DataFrame(
            columns=["motif", "n", "n_ok", "n_errors", "mean_seconds", "median_seconds",
                     "max_seconds", "mean_tests", "max_tests"]
        )
    grouped = ok.groupby(["motif", "n"])
    errors = raw.loc[raw["status"] != "ok"].groupby(["motif", "n"]).size()

    summary = grouped.agg(
        n_ok=("wall_seconds", "size"),
        mean_seconds=("wall_seconds", "mean"),
        median_seconds=("wall_seconds", "median"),
        max_seconds=("wall_seconds", "max"),
        mean_tests=("n_significance_tests", "mean"),
        max_tests=("n_significance_tests", "max"),
    ).reset_index()
    summary["n_errors"] = summary.apply(
        lambda r: int(errors.get((r["motif"], r["n"]), 0)), axis=1
    )
    return summary[
        ["motif", "n", "n_ok", "n_errors", "mean_seconds", "median_seconds", "max_seconds", "mean_tests", "max_tests"]
    ]


def write_report(raw: pd.DataFrame, config: Stage7TimingConfig, output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(raw)
    summary.to_csv(output_dir / "timing_summary.csv", index=False)

    ok = raw.loc[raw["status"] == "ok"]
    total_measured_seconds = float(ok["wall_seconds"].sum()) if not ok.empty else 0.0

    lines = [
        "# Stage 7 Isolation-Tier Timing/Feasibility Measurement (mi-native)\n",
        "Diagnostic only -- sizes the real Stage 7 charter run's replicate count "
        "per docs/stage7_charter.md's own 'Compute-cost disclosure' section. Not a gate.\n",
        f"k_CMI={config.k_cmi}, k_perm={config.k_perm}, permutations={config.permutations}, "
        f"alpha={config.alpha} (provisional, measurement purposes only).\n",
        f"Total measured wall-clock time across all cells: {total_measured_seconds:.1f}s "
        f"({total_measured_seconds / 3600:.2f}h) -- the sum of per-replicate costs, "
        "not this run's own actual elapsed time (cells ran in parallel CI shards).\n",
        "## Per (motif, N): replicate cost and significance-test count\n",
        "| motif | N | ok | errors | mean s | median s | max s | mean tests | max tests |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in summary.iterrows():
        lines.append(
            f"| {r.motif} | {r.n} | {r.n_ok} | {r.n_errors} | {r.mean_seconds:.2f} | "
            f"{r.median_seconds:.2f} | {r.max_seconds:.2f} | {r.mean_tests:.1f} | {int(r.max_tests)} |"
        )
    lines.append("")
    lines.append(
        "Use `mean_seconds` x intended-replicate-count x n(motif,N cells) to project the real "
        "charter run's own total compute budget before finalizing its replicate count, per the "
        "charter's own explicit instruction not to assume affordability.\n"
    )
    (output_dir / "timing_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary
