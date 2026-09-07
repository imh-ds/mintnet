"""Evidence rendering for the Stage 3e p=30 overlap stability-filtering-
rescue experiment. See docs/stage3e_charter.md.

Reuses Stage 3b's gate-evaluation and plotting logic unmodified
(`mintnet.experiments.stage3b_reporting.evaluate_stage3b_gate`,
`_plot_overlap_tpr_vs_pi_min`, `_plot_before_after` -- all generic over
the config's thresholds and the raw evidence's category column). Only
the report file name and title are Stage-3e-specific.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage3b import Stage3bConfig
from mintnet.experiments.stage3b_reporting import (
    GateDecision,
    _plot_before_after,
    _plot_overlap_tpr_vs_pi_min,
    evaluate_stage3b_gate,
)


def write_stage3e_report(raw: pd.DataFrame, config: Stage3bConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage3b_gate(raw, config)

    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )

    _plot_overlap_tpr_vs_pi_min(decision, config, output_dir / "overlap_tpr_vs_pi_min.png")
    _plot_before_after(decision, output_dir / "before_after_filtering.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | status | dpi_alpha | selected pi_min | baseline overlap TPR | filtered overlap TPR | "
        "baseline true-edge FPR | filtered true-edge FPR | failures |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        pi_min = "None" if d.selected_pi_min is None else f"{d.selected_pi_min:.2f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {d.dpi_alpha:.4f} | {pi_min} | {fmt(d.baseline_overlap_indirect_tpr)} | "
            f"{fmt(d.validation_overlap_indirect_tpr)} | {fmt(d.baseline_true_edge_fpr)} | "
            f"{fmt(d.validation_true_edge_fpr)} | {failures} |"
        )
    table = "\n".join(rows)

    (output_dir / "stage3e_report.md").write_text(
        "# Stage 3e Stability-Filtering Rescue Report (p=30 Overlap)\n\n"
        f"{table}\n\n"
        "`N=1500`/`1600` are D-026/D-027's REASSESS cases (baseline overlap "
        "TPR `.762`/`.786`, both below the `.80` gate); `N=1750` is the "
        "first PROCEED, included as a no-regression check. `baseline` "
        "columns are the unmodified point-estimate pipeline; `filtered` "
        "columns apply the selected `pi_min`, evaluated on validation "
        "replicates. See `docs/stage3e_charter.md` for the predeclared "
        "(directional, not numeric) expectation this evidence tests.\n\n"
        "See `raw_metrics.csv`, `decision.json`, `overlap_tpr_vs_pi_min.png`, "
        "and `before_after_filtering.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
