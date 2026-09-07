"""Evidence rendering for the Stage 2e p=30 screening experiment. See
docs/stage2e_charter.md.

Reuses Stage 2's gate-evaluation and aggregation logic unmodified
(`mintnet.experiments.stage2_reporting.evaluate_stage2_gate`,
`aggregate_stage2`, `_plot_operating_curve` -- all generic over the
config's `pi_min`-analog thresholds and ground-truth counts, needing no
change for `p=30`). Only the report file name and title are
Stage-2e-specific, per this project's provenance discipline: reusing
Stage 2's own `write_stage2_report` unmodified would label this
charter's evidence as Stage 2's.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2 import Stage2Config
from mintnet.experiments.stage2_reporting import GateDecision, _plot_operating_curve, aggregate_stage2, evaluate_stage2_gate


def write_stage2e_report(raw: pd.DataFrame, config: Stage2Config, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage2(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage2_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_operating_curve(aggregate, output_dir / "screening_operating_curve.png")

    rows = [
        "| N | status | rule | threshold | validation recall | validation FDR | failures |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        rule = "None" if d.selected_rule_kind is None else d.selected_rule_kind
        threshold = "None" if d.selected_threshold is None else f"{d.selected_threshold:.4f}"
        recall = "None" if d.validation_recall is None else f"{d.validation_recall:.4f}"
        fdr = "None" if d.validation_fdr is None else f"{d.validation_fdr:.4f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(f"| {d.n} | {d.status} | {rule} | {threshold} | {recall} | {fdr} | {failures} |")
    table = "\n".join(rows)
    (output_dir / "stage2e_report.md").write_text(
        "# Stage 2e Candidate-Edge Screening Report (p=30)\n\n"
        f"{table}\n\n"
        "9 true candidate pairs, 426 null pairs (`p=30`), vs. Stage 2's "
        "9 true / 96 null at `p=15` -- see `docs/stage2e_charter.md` for "
        "the predeclared FDR-vs-alpha expectation this evidence tests.\n\n"
        "See `aggregate_metrics.csv`, `raw_metrics.csv`, `decision.json`, and "
        "`screening_operating_curve.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
