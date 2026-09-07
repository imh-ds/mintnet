"""Frozen gate evaluation and evidence rendering for the Stage 4a
sequential/greedy conditioning engine experiment. See
docs/stage4a_charter.md.

Reuses Stage 1b's own gate-evaluation, alpha-selection, aggregation, and
plotting logic unmodified (`mintnet.experiments.stage1b_reporting.
evaluate_stage1b_gate`, `aggregate_stage1b`, `_plot_dpi_operating_curve`,
`_plot_performance_vs_alpha`, `_plot_runtime_vs_n` -- all generic over
the config's thresholds and the raw evidence's motif/alpha columns,
agnostic to which pruning mechanism produced them). Only the report file
name/title and the cross-engine comparison against Stage 1b's own
on-disk evidence are new.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1b import Stage1bConfig
from mintnet.experiments.stage1b_reporting import (
    GateDecision,
    _plot_dpi_operating_curve,
    _plot_performance_vs_alpha,
    _plot_runtime_vs_n,
    aggregate_stage1b,
    evaluate_stage1b_gate,
)


def _repository_root(config: Stage1bConfig) -> Path:
    if config.source_path is not None:
        return config.source_path.parent.parent
    return Path(__file__).resolve().parents[3]


def _compare_to_stage1b(aggregate: pd.DataFrame, config: Stage1bConfig) -> pd.DataFrame:
    """Descriptive, non-gating comparison against Stage 1b's own on-disk
    evidence at matching (motif, n, strength, alpha) cells.

    Note: docs/stage4a_charter.md's "Consequences" section cites this
    comparison as against "D-008 evidence" -- that citation is imprecise.
    D-008 is Stage 1g's later, differently-scoped refinement (a narrower
    N grid restricted to [750, 1000, 1500, 2000] and a margin-robust
    selection rule, not the lexicographically-first rule this charter
    reuses). The correct apples-to-apples baseline for this charter's own
    N grid and selection rule is Stage 1b's own original evidence, used
    here instead.
    """
    baseline_path = _repository_root(config) / "results/generated/stage1b_dpi/aggregate_metrics.csv"
    if not baseline_path.is_file():
        return pd.DataFrame(
            columns=[
                "motif", "n", "strength", "alpha",
                "indirect_prune_tpr_sequential", "indirect_prune_tpr_stage1b", "indirect_prune_tpr_delta",
                "true_edge_prune_fpr_sequential", "true_edge_prune_fpr_stage1b", "true_edge_prune_fpr_delta",
            ]
        )
    baseline = pd.read_csv(baseline_path)
    keys = ["motif", "n", "strength", "alpha"]
    merged = aggregate.merge(
        baseline[[*keys, "indirect_prune_tpr", "true_edge_prune_fpr"]],
        on=keys,
        how="inner",
        suffixes=("_sequential", "_stage1b"),
    )
    merged["indirect_prune_tpr_delta"] = (
        merged["indirect_prune_tpr_sequential"] - merged["indirect_prune_tpr_stage1b"]
    )
    merged["true_edge_prune_fpr_delta"] = (
        merged["true_edge_prune_fpr_sequential"] - merged["true_edge_prune_fpr_stage1b"]
    )
    return merged


def write_stage4a_report(raw: pd.DataFrame, config: Stage1bConfig, output_dir: Path) -> GateDecision:
    """Write all aggregate evidence and the Stage 4a decision for one run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage1b(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage1b_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps(asdict(decision), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    _plot_dpi_operating_curve(aggregate, output_dir / "dpi_operating_curve.png")
    _plot_performance_vs_alpha(aggregate, output_dir / "performance_vs_alpha.png")
    _plot_runtime_vs_n(aggregate, output_dir / "runtime_vs_n.png")

    comparison = _compare_to_stage1b(aggregate, config)
    comparison.to_csv(output_dir / "stage1b_comparison.csv", index=False)

    selected = "None" if decision.selected_alpha_pair is None else ", ".join(map(str, decision.selected_alpha_pair))
    failures = "None" if not decision.failures else ", ".join(decision.failures)
    comparison_note = (
        f"Compared against Stage 1b's own on-disk evidence at {len(comparison)} matching cells "
        "-- see `stage1b_comparison.csv` for per-cell deltas."
        if not comparison.empty
        else "Stage 1b's own on-disk evidence "
        "(`results/generated/stage1b_dpi/aggregate_metrics.csv`) was not found; comparison skipped."
    )
    (output_dir / "stage4a_report.md").write_text(
        "# Stage 4a Sequential/Greedy Conditioning Engine — Motif Validation Report\n\n"
        f"Decision: **{decision.status}**\n\n"
        f"Selected development alpha pair: `{selected}`\n\n"
        f"Failed criteria: {failures}\n\n"
        f"{comparison_note} Note: `docs/stage4a_charter.md` cites this comparison as against "
        "\"D-008 evidence\", which is imprecise -- D-008 is Stage 1g's later, differently-scoped "
        "refinement (narrower N grid, margin-robust selection). The comparison actually used here "
        "is against Stage 1b's own original evidence, the correct apples-to-apples baseline for "
        "this charter's reused N grid and selection rule.\n\n"
        "See `aggregate_metrics.csv`, `decision.json`, `stage1b_comparison.csv`, and the "
        "generated figures for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
