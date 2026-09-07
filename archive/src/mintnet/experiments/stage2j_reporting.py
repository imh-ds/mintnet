"""Screening-alpha selection and per-(p, N) gate evaluation for the
Stage 2j p=5/p=10 floor-check experiment. See docs/stage2j_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage2j import P5, P10, Stage2jConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


# --- Phase 1: p=10 screening-alpha selection (D-013/D-023 methodology) ---


@dataclass(frozen=True)
class SelectionDecision:
    n: int
    selected_alpha: float | None
    development_recall: float | None
    development_fdr: float | None
    validation_recall: float | None
    validation_fdr: float | None
    failures: tuple[str, ...]


def _pooled_recall_fdr(rows: pd.DataFrame, n: int, alpha: float) -> tuple[float, float] | None:
    """Pooled (sum-of-counts) recall/FDR, matching Stage 2/2e's own definition."""
    subset = rows.loc[(rows["n"] == n) & (rows["alpha"] == alpha)]
    count_columns = ["true_positives", "false_positives", "total_flagged", "true_pair_count"]
    if subset.empty or not np.isfinite(subset[count_columns]).all().all():
        return None
    true_positives = float(subset["true_positives"].sum())
    false_positives = float(subset["false_positives"].sum())
    total_flagged = float(subset["total_flagged"].sum())
    true_pair_count = float(subset["true_pair_count"].sum())
    recall = true_positives / true_pair_count
    fdr = (false_positives / total_flagged) if total_flagged > 0 else 0.0
    return recall, fdr


def select_alpha_p10(selection_raw: pd.DataFrame, n: int, config: Stage2jConfig) -> float | None:
    """Smallest development-eligible alpha, per Stage 2/2e's own tiebreak."""
    development = _partition(selection_raw, config.development_replicates)
    eligible: list[float] = []
    for alpha in sorted(config.screening_alpha_grid):
        metrics = _pooled_recall_fdr(development, n, alpha)
        if metrics is None:
            continue
        recall, fdr = metrics
        if recall >= config.minimum_recall and fdr <= config.maximum_fdr:
            eligible.append(alpha)
    return min(eligible) if eligible else None


def evaluate_selection(selection_raw: pd.DataFrame, n: int, config: Stage2jConfig) -> SelectionDecision:
    n_raw = selection_raw.loc[selection_raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        return SelectionDecision(n, None, None, None, None, None, tuple(failures))

    development = _partition(n_raw, config.development_replicates)
    selected = select_alpha_p10(n_raw, n, config)
    if selected is None:
        failures.append("no eligible development alpha")
        return SelectionDecision(n, None, None, None, None, None, tuple(failures))

    dev_metrics = _pooled_recall_fdr(development, n, selected)
    dev_recall, dev_fdr = dev_metrics if dev_metrics is not None else (None, None)

    validation = _partition(n_raw, config.validation_replicates)
    val_metrics = _pooled_recall_fdr(validation, n, selected)
    if val_metrics is None:
        failures.append("missing validation evidence")
        return SelectionDecision(n, selected, dev_recall, dev_fdr, None, None, tuple(failures))

    val_recall, val_fdr = val_metrics
    if val_recall < config.minimum_recall:
        failures.append(f"validation recall {val_recall:.4f} below required {config.minimum_recall:.4f}")
    if val_fdr > config.maximum_fdr:
        failures.append(f"validation FDR {val_fdr:.4f} above allowed {config.maximum_fdr:.4f}")

    return SelectionDecision(n, selected, dev_recall, dev_fdr, val_recall, val_fdr, tuple(failures))


# --- Phase 2: composed-pipeline gate, per (p, N) ---


@dataclass(frozen=True)
class NDecision:
    p: int
    n: int
    status: str
    screening_alpha: float | None
    dpi_alpha: float | None
    chain_indirect_tpr: float | None
    overlap_indirect_tpr: float | None
    true_edge_prune_fpr: float | None
    screening_false_edge_rate: float | None
    final_false_edge_rate: float | None
    overlap_clean_clique_rate: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_cell: tuple[NDecision, ...]


def evaluate_cell(composition_raw: pd.DataFrame, p: int, n: int, config: Stage2jConfig) -> NDecision:
    cell_raw = composition_raw.loc[(composition_raw["p"] == p) & (composition_raw["n"] == n)]
    failures: list[str] = []
    if cell_raw.empty or not cell_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors, or no eligible development alpha")
        screening_alpha = None
        if not cell_raw.empty and cell_raw["screening_alpha"].notna().any():
            screening_alpha = float(cell_raw["screening_alpha"].dropna().iloc[0])
        return NDecision(p, n, "REASSESS", screening_alpha, None, None, None, None, None, None, None, tuple(failures))

    screening_alpha = float(cell_raw["screening_alpha"].iloc[0])
    dpi_alpha = float(cell_raw["dpi_alpha"].iloc[0])
    validation = _partition(cell_raw, config.validation_replicates)

    overlap_tpr = float(validation["overlap_indirect_tpr"].mean())
    true_edge_fpr = float(validation["true_edge_prune_fpr"].mean())
    overlap_clean_rate = float(validation["overlap_clean_clique"].mean())

    if overlap_tpr < config.minimum_indirect_tpr:
        failures.append(f"overlap indirect TPR {overlap_tpr:.4f} below required {config.minimum_indirect_tpr:.4f}")
    if true_edge_fpr > config.maximum_true_edge_fpr:
        failures.append(f"true-edge FPR {true_edge_fpr:.4f} above allowed {config.maximum_true_edge_fpr:.4f}")

    chain_tpr: float | None = None
    if p == P10:
        chain_tpr = float(validation["chain_indirect_tpr"].mean())
        if chain_tpr < config.minimum_indirect_tpr:
            failures.append(f"chain indirect TPR {chain_tpr:.4f} below required {config.minimum_indirect_tpr:.4f}")

    screening_rate: float | None = None
    final_rate: float | None = None
    if p == P10:
        # Undefined at p=5 (zero null pairs) -- skipped there, per the
        # charter's disclosed limitation, not silently passed.
        screening_rate = float(validation["screening_false_edge_rate"].mean())
        final_rate = float(validation["final_false_edge_rate"].mean())
        if final_rate > screening_rate + config.false_edge_rate_tolerance:
            failures.append(
                f"final false-edge rate {final_rate:.4f} exceeds screening baseline "
                f"{screening_rate:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
            )

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(
        p, n, status, screening_alpha, dpi_alpha, chain_tpr, overlap_tpr, true_edge_fpr,
        screening_rate, final_rate, overlap_clean_rate, tuple(failures),
    )


def evaluate_stage2j_gate(composition_raw: pd.DataFrame, config: Stage2jConfig) -> GateDecision:
    cells = [(p, n) for p in (P10, P5) for n in config.sample_sizes]
    return GateDecision(tuple(evaluate_cell(composition_raw, p, n, config) for p, n in cells))


def _plot_overlap_tpr_by_p(decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    for p, marker, label in ((P10, "o", "p=10"), (P5, "s", "p=5")):
        cells = [d for d in decision.by_cell if d.p == p]
        ns = [d.n for d in cells]
        tpr = [d.overlap_indirect_tpr for d in cells]
        axis.plot(ns, tpr, marker=marker, label=f"overlap indirect TPR ({label})")
    axis.axhline(0.80, color="gray", linestyle="--", linewidth=0.8, label="TPR gate (.80)")
    axis.set_xlabel("N")
    axis.set_ylabel("Overlap indirect-edge TPR")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage2j_report(
    selection_raw: pd.DataFrame, composition_raw: pd.DataFrame, config: Stage2jConfig, output_dir: Path
) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)

    selection_decisions = [evaluate_selection(selection_raw, n, config) for n in config.sample_sizes]
    decision = evaluate_stage2j_gate(composition_raw, config)

    (output_dir / "decision.json").write_text(
        json.dumps(
            {
                "selection": [asdict(d) for d in selection_decisions],
                "by_cell": [asdict(d) for d in decision.by_cell],
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_overlap_tpr_by_p(decision, output_dir / "overlap_tpr_by_p.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    selection_rows = [
        "| N | selected alpha | dev recall | dev FDR | val recall | val FDR | failures |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in selection_decisions:
        failures = "None" if not d.failures else ", ".join(d.failures)
        alpha = "None" if d.selected_alpha is None else f"{d.selected_alpha:.4f}"
        selection_rows.append(
            f"| {d.n} | {alpha} | {fmt(d.development_recall)} | {fmt(d.development_fdr)} | "
            f"{fmt(d.validation_recall)} | {fmt(d.validation_fdr)} | {failures} |"
        )
    selection_table = "\n".join(selection_rows)

    composition_rows = [
        "| p | N | status | alpha | dpi_alpha | chain TPR | overlap TPR | true-edge FPR | "
        "screening FER | final FER | overlap clean rate | failures |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_cell:
        alpha = "None" if d.screening_alpha is None else f"{d.screening_alpha:.4f}"
        dpi_alpha = "None" if d.dpi_alpha is None else f"{d.dpi_alpha:.4f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        composition_rows.append(
            f"| {d.p} | {d.n} | {d.status} | {alpha} | {dpi_alpha} | {fmt(d.chain_indirect_tpr)} | "
            f"{fmt(d.overlap_indirect_tpr)} | {fmt(d.true_edge_prune_fpr)} | {fmt(d.screening_false_edge_rate)} | "
            f"{fmt(d.final_false_edge_rate)} | {fmt(d.overlap_clean_clique_rate)} | {failures} |"
        )
    composition_table = "\n".join(composition_rows)

    (output_dir / "stage2j_report.md").write_text(
        "# Stage 2j p=5/p=10 Floor-Check Report\n\n"
        "## Screening-alpha selection (p=10 only; p=5 fixed at D-013's alpha=.001, not re-derived)\n\n"
        f"{selection_table}\n\n"
        "## Composed-pipeline gate\n\n"
        f"{composition_table}\n\n"
        "`chain TPR`, `screening FER`, and `final FER` are `None` at `p=5` "
        "by construction -- there is no chain motif and zero null pairs at "
        "that `p` (see `docs/stage2j_charter.md`'s disclosed limitation), "
        "not a missing-data problem.\n\n"
        "See `raw_metrics.csv`, `screening_selection_metrics.csv`, "
        "`decision.json`, and `overlap_tpr_by_p.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
