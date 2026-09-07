"""Evidence rendering for the Stage 2g p=30 hub-composed-pipeline
experiment. See docs/stage2g_charter.md.

Reuses Stage 2c's gate-evaluation and plotting logic unmodified
(`mintnet.experiments.stage2c_reporting.evaluate_stage2c_gate`,
`_plot_false_edge_comparison`). Only the report file name, title, and
number formatting (6 decimals, since `p=30`'s rates are an order of
magnitude smaller than Stage 2c's) are Stage-2g-specific.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2c import Stage2cConfig
from mintnet.experiments.stage2c_reporting import GateDecision, _plot_false_edge_comparison, evaluate_stage2c_gate


def write_stage2g_report(raw: pd.DataFrame, config: Stage2cConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage2c_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_false_edge_comparison(decision, output_dir / "false_edge_rate_comparison.png")

    rows = [
        "| N | status | dpi_alpha | indirect TPR | true-edge FPR | screening FER | final FER | shape rate | failures |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        def fmt(value: float | None) -> str:
            return "None" if value is None else f"{value:.6f}"

        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {d.dpi_alpha:.4f} | {fmt(d.indirect_prune_tpr)} | "
            f"{fmt(d.true_edge_prune_fpr)} | {fmt(d.screening_false_edge_rate)} | "
            f"{fmt(d.final_false_edge_rate)} | {fmt(d.triad_rate)} | {failures} |"
        )
    table = "\n".join(rows)
    (output_dir / "stage2g_report.md").write_text(
        "# Stage 2g Hub-Composed Pipeline Report (p=30)\n\n"
        f"{table}\n\n"
        "Screening at `alpha=.0001` (D-023's `p=30` rule, reused without "
        "re-derivation), DPI at `alpha=f(N)` (D-012, unchanged). 7 true "
        "direct edges, 5 indirect edges, 423 null pairs -- see "
        "`docs/stage2g_charter.md` for the predeclared expectation "
        "(final false-edge rate `~.0001`, indirect TPR `~.82`-`.85`) "
        "this evidence tests.\n\n"
        "`shape rate`: fraction of the three true motif components "
        "(chain/fork triads, hub 4-clique) that formed their validated "
        "shape and so had DPI applied, rather than some other shape.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and "
        "`false_edge_rate_comparison.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
