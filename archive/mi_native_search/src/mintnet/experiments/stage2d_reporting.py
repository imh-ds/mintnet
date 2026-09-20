"""Per-N gate evaluation and evidence rendering for the Stage 2d overlap-wiring experiment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage2d import Stage2dConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class NDecision:
    n: int
    status: str
    dpi_alpha: float
    chain_indirect_tpr: float | None
    fork_indirect_tpr: float | None
    overlap_indirect_tpr: float | None
    true_edge_prune_fpr: float | None
    screening_false_edge_rate: float | None
    final_false_edge_rate: float | None
    overlap_clean_clique_rate: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage2dConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        dpi_alpha = float(n_raw["dpi_alpha"].iloc[0]) if not n_raw.empty else float("nan")
        return NDecision(n, "REASSESS", dpi_alpha, None, None, None, None, None, None, None, tuple(failures))

    dpi_alpha = float(n_raw["dpi_alpha"].iloc[0])
    validation = _partition(n_raw, config.validation_replicates)

    chain_tpr = float(validation["chain_indirect_tpr"].mean())
    fork_tpr = float(validation["fork_indirect_tpr"].mean())
    overlap_tpr = float(validation["overlap_indirect_tpr"].mean())
    true_edge_fpr = float(validation["true_edge_prune_fpr"].mean())
    screening_rate = float(validation["screening_false_edge_rate"].mean())
    final_rate = float(validation["final_false_edge_rate"].mean())
    overlap_clean_rate = float(validation["overlap_clean_clique"].mean())

    for label, tpr in (("chain", chain_tpr), ("fork", fork_tpr), ("overlap", overlap_tpr)):
        if tpr < config.minimum_indirect_prune_tpr:
            failures.append(f"{label} indirect TPR {tpr:.4f} below required {config.minimum_indirect_prune_tpr:.4f}")
    if true_edge_fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {true_edge_fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if final_rate > screening_rate + config.false_edge_rate_tolerance:
        failures.append(
            f"final false-edge rate {final_rate:.4f} exceeds screening baseline "
            f"{screening_rate:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
        )

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(
        n, status, dpi_alpha, chain_tpr, fork_tpr, overlap_tpr, true_edge_fpr,
        screening_rate, final_rate, overlap_clean_rate, tuple(failures),
    )


def evaluate_stage2d_gate(raw: pd.DataFrame, config: Stage2dConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _plot_overlap_clean_clique_vs_tpr(decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    ns = [d.n for d in decision.by_n]
    clean_rate = [d.overlap_clean_clique_rate for d in decision.by_n]
    tpr = [d.overlap_indirect_tpr for d in decision.by_n]
    axis.plot(ns, clean_rate, marker="o", label="overlap clean-clique rate")
    axis.plot(ns, tpr, marker="s", label="overlap indirect-edge TPR")
    axis.axhline(0.80, color="gray", linestyle="--", linewidth=0.8, label="TPR gate (.80)")
    axis.set_xlabel("N")
    axis.set_ylabel("Rate")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage2d_report(raw: pd.DataFrame, config: Stage2dConfig, output_dir: Path) -> GateDecision:
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
            return "None" if value is None else f"{value:.4f}"

        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {d.dpi_alpha:.4f} | {fmt(d.chain_indirect_tpr)} | "
            f"{fmt(d.fork_indirect_tpr)} | {fmt(d.overlap_indirect_tpr)} | {fmt(d.true_edge_prune_fpr)} | "
            f"{fmt(d.screening_false_edge_rate)} | {fmt(d.final_false_edge_rate)} | "
            f"{fmt(d.overlap_clean_clique_rate)} | {failures} |"
        )
    table = "\n".join(rows)
    (output_dir / "stage2d_report.md").write_text(
        "# Stage 2d Overlap-Wiring Report\n\n"
        f"{table}\n\n"
        "`overlap clean rate`: fraction of replicates where screening flagged all 10 "
        "pairs within the overlap motif's 5 nodes, forming a clean candidate clique DPI "
        "could act on. TPR/FPR reported separately per motif, not pooled, since pooling "
        "with the (expected-clean) chain/fork motifs would risk masking an overlap-specific "
        "problem.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and `overlap_clean_clique_vs_tpr.png` "
        "for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
