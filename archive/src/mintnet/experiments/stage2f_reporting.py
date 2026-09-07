"""Evidence rendering for the Stage 2f p=30 composed-pipeline experiment.
See docs/stage2f_charter.md.

Reuses Stage 2b's gate-evaluation and plotting logic unmodified
(`mintnet.experiments.stage2b_reporting.evaluate_stage2b_gate`,
`_plot_false_edge_comparison` -- both generic over the config's
thresholds and ground-truth counts). Only the report file name and
title are Stage-2f-specific, per this project's provenance discipline.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2b import Stage2bConfig
from mintnet.experiments.stage2b_reporting import GateDecision, _plot_false_edge_comparison, evaluate_stage2b_gate


def write_stage2f_report(raw: pd.DataFrame, config: Stage2bConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage2b_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_false_edge_comparison(decision, output_dir / "false_edge_rate_comparison.png")

    rows = [
        "| N | status | dpi_alpha | indirect TPR | true-edge FPR | screening FER | final FER | triad rate | failures |",
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
    (output_dir / "stage2f_report.md").write_text(
        "# Stage 2f Composed Pipeline Report (p=30)\n\n"
        f"{table}\n\n"
        "Screening at `alpha=.0001` (D-023's `p=30`-selected rule, not "
        "D-013's `p=15` one), DPI at `alpha=f(N)` (D-012, unchanged). 7 "
        "true direct edges, 2 indirect edges, 426 null pairs -- see "
        "`docs/stage2f_charter.md` for the predeclared final-false-edge-"
        "rate expectation (`~.00012`, D-023's screening-alone per-edge "
        "FPR at this `p`) this evidence tests.\n\n"
        "`triad rate`: fraction of the three true motif components that "
        "formed a clean 3-node candidate triad (and so had DPI applied) "
        "rather than some other shape.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and "
        "`false_edge_rate_comparison.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
