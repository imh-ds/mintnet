"""Gate evaluation and evidence rendering for the Stage 4d sequential-
engine floor-search charter. See docs/stage4d_charter.md.

Reuses Stage 4b's gate-evaluation logic unmodified
(`mintnet.experiments.stage4b_reporting.evaluate_stage4b_gate` --
generic over the config's `sample_sizes`, so it works unchanged across
the full six-point curve this charter assembles). Only the report
title/text, the TPR-vs-N curve plot, and the predeclared early-stop
determination are new.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage4b import SHAPES, Stage4bConfig
from mintnet.experiments.stage4b_reporting import GateDecision, evaluate_stage4b_gate

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

# Base-mechanism floor, already established independent of composition
# strategy (Stage 1h/1i, docs/decision_log.md D-009 through D-011) --
# used only for the report's descriptive early-stop determination, not
# as a gate input.
BASE_MECHANISM_TRANSITION = {300: "REASSESS (decisive)", 500: "REASSESS", 600: "REASSESS", 650: "REASSESS (near-miss)", 700: "PROCEED (thin)", 750: "PROCEED"}


def _plot_tpr_vs_n(decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    for shape, marker in (("hub", "o"), ("overlap", "s")):
        cells = sorted((d for d in decision.by_cell if d.shape == shape), key=lambda d: d.n)
        ns = [d.n for d in cells]
        tpr = [d.indirect_prune_tpr for d in cells]
        axis.plot(ns, tpr, marker=marker, label=f"{shape} indirect TPR")
    axis.axhline(0.80, color="gray", linestyle="--", linewidth=0.8, label="TPR gate (.80)")
    axis.set_xlabel("N")
    axis.set_ylabel("Indirect-edge TPR")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _early_stop_met(decision: GateDecision) -> tuple[bool, str]:
    """Descriptive check of this charter's own predeclared early-stop rule:
    hub's transition in [600,700] (matching the base mechanism) and
    overlap's floor at or above 650."""
    hub_cells = {d.n: d for d in decision.by_cell if d.shape == "hub"}
    overlap_cells = {d.n: d for d in decision.by_cell if d.shape == "overlap"}

    hub_ok = all(
        hub_cells[n].status == "REASSESS" for n in (300, 500, 600) if n in hub_cells
    ) and any(hub_cells[n].status == "PROCEED" for n in (650, 700) if n in hub_cells)
    overlap_floor = next((n for n in sorted(overlap_cells) if overlap_cells[n].status == "PROCEED"), None)
    overlap_ok = overlap_floor is not None and overlap_floor >= 650

    if hub_ok and overlap_ok:
        return True, "Met: hub's transition matches the known base-mechanism range, and overlap's floor is >= 650."
    return False, "Not met: at least one shape's transition falls outside this charter's predeclared expectation."


def write_stage4d_report(raw: pd.DataFrame, config: Stage4bConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4b_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_cell": [asdict(d) for d in decision.by_cell]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    _plot_tpr_vs_n(decision, output_dir / "indirect_tpr_vs_n.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| shape | N | status | alpha | indirect TPR | true-edge FPR | margin | base-mechanism reference |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for shape in SHAPES:
        for d in sorted((c for c in decision.by_cell if c.shape == shape), key=lambda c: c.n):
            alpha = "None" if d.selected_alpha is None else f"{d.selected_alpha:.4f}"
            reference = BASE_MECHANISM_TRANSITION.get(d.n, "n/a")
            rows.append(
                f"| {d.shape} | {d.n} | {d.status} | {alpha} | {fmt(d.indirect_prune_tpr)} | "
                f"{fmt(d.true_edge_prune_fpr)} | {fmt(d.margin)} | {reference} |"
            )
    table = "\n".join(rows)

    met, explanation = _early_stop_met(decision)
    (output_dir / "stage4d_report.md").write_text(
        "# Stage 4d Sequential Engine Floor-Search Report\n\n"
        f"{table}\n\n"
        f"**Predeclared early-stop condition: {'MET' if met else 'NOT MET'}.** {explanation}\n\n"
        "`base-mechanism reference` is the already-established conservative-engine transition "
        "at this N (Stage 1h/1i, D-009-D-011), independent of composition strategy -- reported "
        "for context, not used as a gate input.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and `indirect_tpr_vs_n.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
