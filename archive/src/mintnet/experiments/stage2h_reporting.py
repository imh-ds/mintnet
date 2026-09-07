"""Evidence rendering for the Stage 2h p=30 overlap-composed-pipeline
experiment. See docs/stage2h_charter.md.

Reuses Stage 2d's gate-evaluation and plotting logic unmodified
(`mintnet.experiments.stage2d_reporting.evaluate_stage2d_gate`,
`_plot_overlap_clean_clique_vs_tpr`). Only the report file name, title,
and number formatting (6 decimals, since `p=30`'s false-edge rates are
an order of magnitude smaller than Stage 2d's) are Stage-2h-specific.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2d import Stage2dConfig
from mintnet.experiments.stage2d_reporting import GateDecision, _plot_overlap_clean_clique_vs_tpr, evaluate_stage2d_gate


def write_stage2h_report(raw: pd.DataFrame, config: Stage2dConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage2d_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_overlap_clean_clique_vs_tpr(decision, output_dir / "overlap_clean_clique_vs_tpr.png")

    rows = [
        "| N | status | dpi_alpha | chain TPR | fork TPR | overlap TPR | true-edge FPR | "
        "screening FER | final FER | overlap clean rate | failures |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        def fmt(value: float | None) -> str:
            return "None" if value is None else f"{value:.6f}"

        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {d.dpi_alpha:.4f} | {fmt(d.chain_indirect_tpr)} | "
            f"{fmt(d.fork_indirect_tpr)} | {fmt(d.overlap_indirect_tpr)} | {fmt(d.true_edge_prune_fpr)} | "
            f"{fmt(d.screening_false_edge_rate)} | {fmt(d.final_false_edge_rate)} | "
            f"{fmt(d.overlap_clean_clique_rate)} | {failures} |"
        )
    table = "\n".join(rows)
    (output_dir / "stage2h_report.md").write_text(
        "# Stage 2h Overlap-Composed Pipeline Report (p=30)\n\n"
        f"{table}\n\n"
        "Screening at `alpha=.0001` (D-023's `p=30` rule, reused without "
        "re-derivation and *not* hand-tuned for this DGP's weaker "
        "signal), DPI at `alpha=f(N)` (D-012, unchanged). 10 true direct "
        "edges, 6 indirect edges, 419 null pairs -- see "
        "`docs/stage2h_charter.md` for the predeclared power calculation "
        "(naive clean-clique rate `.034` at `N=750`, `.697` at `N=1500`) "
        "this evidence tests. TPR/FPR reported separately per motif, not "
        "pooled, per the D-004 anti-pooling precedent.\n\n"
        "`overlap clean rate`: fraction of replicates where screening "
        "flagged all 10 pairs within the overlap motif's 5 nodes.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and "
        "`overlap_clean_clique_vs_tpr.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
