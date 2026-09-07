"""Evidence rendering for the Stage 2i overlap-p=30 floor-search
experiment. See docs/stage2i_charter.md.

Reuses Stage 2d's gate-evaluation and plotting logic unmodified
(`mintnet.experiments.stage2d_reporting.evaluate_stage2d_gate`,
`_plot_overlap_clean_clique_vs_tpr`) -- the gate criteria are identical
to Stage 2h's, only the set of `N` values changes (the reused `1500`
bookend plus four new ones). Only the report file name, title, and
number formatting are Stage-2i-specific.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2d import Stage2dConfig
from mintnet.experiments.stage2d_reporting import GateDecision, _plot_overlap_clean_clique_vs_tpr, evaluate_stage2d_gate


def write_stage2i_report(raw: pd.DataFrame, config: Stage2dConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage2d_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_overlap_clean_clique_vs_tpr(decision, output_dir / "overlap_tpr_vs_n.png")

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
    (output_dir / "stage2i_report.md").write_text(
        "# Stage 2i Overlap p=30 Floor-Search Report\n\n"
        f"{table}\n\n"
        "`N=1500` row is reused verbatim from "
        "`results/generated/stage2h_overlap_composition_p30/raw_metrics.csv` "
        "(see `metadata.json`'s `bookend_raw_evidence_sha256` for its exact "
        "provenance), not re-simulated. `N=1600, 1750, 2000, 2500` are fresh "
        "evidence. See `docs/stage2i_charter.md` for the predeclared "
        "crossover estimate (`[1600, 1750]`) this evidence tests.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and `overlap_tpr_vs_n.png` "
        "for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
