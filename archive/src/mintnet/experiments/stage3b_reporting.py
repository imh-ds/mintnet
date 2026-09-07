"""Per-N gate evaluation and evidence rendering for the Stage 3b
stability-filtering experiment. See docs/stage3b_charter.md.

The filtered final graph is `final_point AND (pi_final >= pi_min)`
computed per candidate `pi_min`, purely from Stage 3b's raw per-pair
evidence -- no resampling happens in this module, only threshold
arithmetic. Chain/fork indirect-edge TPR and the null false-edge rate
are safe-by-construction under filtering (filtering only removes
edges, so an already-correct decision cannot become wrong) -- reported
for completeness, not because they are expected to fail. Overlap
indirect-edge TPR and true-edge FPR are the charter's genuine open
questions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage3b import Stage3bConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_INDIRECT_CATEGORIES = ("indirect_chain", "indirect_fork", "indirect_overlap")


@dataclass(frozen=True)
class PiMinCandidate:
    pi_min: float
    overlap_indirect_tpr: float
    true_edge_fpr: float
    chain_indirect_tpr: float
    fork_indirect_tpr: float
    final_false_edge_rate: float
    eligible: bool


@dataclass(frozen=True)
class NDecision:
    n: int
    status: str
    dpi_alpha: float
    baseline_overlap_indirect_tpr: float | None
    baseline_true_edge_fpr: float | None
    baseline_chain_indirect_tpr: float | None
    baseline_fork_indirect_tpr: float | None
    baseline_final_false_edge_rate: float | None
    selected_pi_min: float | None
    validation_overlap_indirect_tpr: float | None
    validation_true_edge_fpr: float | None
    validation_chain_indirect_tpr: float | None
    validation_fork_indirect_tpr: float | None
    validation_final_false_edge_rate: float | None
    development_candidates: tuple[PiMinCandidate, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _replicate_has_error(subset: pd.DataFrame) -> bool:
    return bool((subset["status"] == "error").any())


def _indirect_tpr(ok_rows: pd.DataFrame, category: str, present: pd.Series) -> float:
    rows = ok_rows.loc[ok_rows["category"] == category]
    if rows.empty:
        return float("nan")
    pruned = (~present.loc[rows.index]).sum()
    return float(pruned) / float(len(rows))


def _true_edge_fpr(ok_rows: pd.DataFrame, present: pd.Series) -> float:
    rows = ok_rows.loc[ok_rows["category"] == "true_direct"]
    if rows.empty:
        return float("nan")
    wrongly_removed = (~present.loc[rows.index]).sum()
    return float(wrongly_removed) / float(len(rows))


def _final_false_edge_rate(ok_rows: pd.DataFrame, present: pd.Series) -> float:
    rows = ok_rows.loc[ok_rows["category"] == "null"]
    if rows.empty:
        return float("nan")
    present_count = present.loc[rows.index].sum()
    return float(present_count) / float(len(rows))


def _metrics_for_present(ok_rows: pd.DataFrame, present: pd.Series) -> dict[str, float]:
    return {
        "overlap_indirect_tpr": _indirect_tpr(ok_rows, "indirect_overlap", present),
        "true_edge_fpr": _true_edge_fpr(ok_rows, present),
        "chain_indirect_tpr": _indirect_tpr(ok_rows, "indirect_chain", present),
        "fork_indirect_tpr": _indirect_tpr(ok_rows, "indirect_fork", present),
        "final_false_edge_rate": _final_false_edge_rate(ok_rows, present),
    }


def _baseline_metrics(ok_rows: pd.DataFrame) -> dict[str, float]:
    """Point-estimate metrics (no stability filter applied)."""
    present = ok_rows["final_point"].astype(bool)
    return _metrics_for_present(ok_rows, present)


def _filtered_metrics(ok_rows: pd.DataFrame, pi_min: float) -> dict[str, float]:
    present = ok_rows["final_point"].astype(bool) & (ok_rows["pi_final"] >= pi_min)
    return _metrics_for_present(ok_rows, present)


def _is_eligible(metrics: dict[str, float], baseline: dict[str, float], config: Stage3bConfig) -> bool:
    return (
        np.isfinite(metrics["overlap_indirect_tpr"])
        and metrics["overlap_indirect_tpr"] >= config.minimum_overlap_indirect_tpr
        and np.isfinite(metrics["true_edge_fpr"])
        and metrics["true_edge_fpr"] <= config.maximum_true_edge_fpr
        and metrics["chain_indirect_tpr"] >= baseline["chain_indirect_tpr"]
        and metrics["fork_indirect_tpr"] >= baseline["fork_indirect_tpr"]
        and metrics["final_false_edge_rate"] <= baseline["final_false_edge_rate"] + config.false_edge_rate_tolerance
    )


def _evaluate_candidates(
    ok_rows: pd.DataFrame, baseline: dict[str, float], config: Stage3bConfig
) -> tuple[PiMinCandidate, ...]:
    candidates: list[PiMinCandidate] = []
    for pi_min in config.pi_min_candidates:
        metrics = _filtered_metrics(ok_rows, pi_min)
        eligible = _is_eligible(metrics, baseline, config)
        candidates.append(
            PiMinCandidate(
                pi_min,
                metrics["overlap_indirect_tpr"],
                metrics["true_edge_fpr"],
                metrics["chain_indirect_tpr"],
                metrics["fork_indirect_tpr"],
                metrics["final_false_edge_rate"],
                eligible,
            )
        )
    return tuple(candidates)


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage3bConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    dpi_alpha = float(n_raw["dpi_alpha"].iloc[0]) if not n_raw.empty else float("nan")
    failures: list[str] = []

    development = _partition(n_raw, config.development_replicates)
    if development.empty or _replicate_has_error(development):
        failures.append("estimator or DGP errors on development replicates")
        return NDecision(
            n, "REASSESS", dpi_alpha, None, None, None, None, None, None, None, None, None, None, (), tuple(failures)
        )

    dev_ok = development.loc[development["status"] == "ok"]
    dev_baseline = _baseline_metrics(dev_ok)
    dev_candidates = _evaluate_candidates(dev_ok, dev_baseline, config)
    eligible = [c for c in dev_candidates if c.eligible]
    if not eligible:
        failures.append("no eligible pi_min on development replicates")
        return NDecision(
            n,
            "REASSESS",
            dpi_alpha,
            dev_baseline["overlap_indirect_tpr"],
            dev_baseline["true_edge_fpr"],
            dev_baseline["chain_indirect_tpr"],
            dev_baseline["fork_indirect_tpr"],
            dev_baseline["final_false_edge_rate"],
            None,
            None,
            None,
            None,
            None,
            None,
            dev_candidates,
            tuple(failures),
        )

    selected_pi_min = min(c.pi_min for c in eligible)

    validation = _partition(n_raw, config.validation_replicates)
    if validation.empty or _replicate_has_error(validation):
        failures.append("estimator or DGP errors on validation replicates")
        return NDecision(
            n,
            "REASSESS",
            dpi_alpha,
            dev_baseline["overlap_indirect_tpr"],
            dev_baseline["true_edge_fpr"],
            dev_baseline["chain_indirect_tpr"],
            dev_baseline["fork_indirect_tpr"],
            dev_baseline["final_false_edge_rate"],
            selected_pi_min,
            None,
            None,
            None,
            None,
            None,
            dev_candidates,
            tuple(failures),
        )

    val_ok = validation.loc[validation["status"] == "ok"]
    val_baseline = _baseline_metrics(val_ok)
    val_metrics = _filtered_metrics(val_ok, selected_pi_min)

    if not (np.isfinite(val_metrics["overlap_indirect_tpr"]) and val_metrics["overlap_indirect_tpr"] >= config.minimum_overlap_indirect_tpr):
        failures.append(
            f"validation overlap indirect TPR {val_metrics['overlap_indirect_tpr']:.4f} below required "
            f"{config.minimum_overlap_indirect_tpr:.4f}"
        )
    if not (np.isfinite(val_metrics["true_edge_fpr"]) and val_metrics["true_edge_fpr"] <= config.maximum_true_edge_fpr):
        failures.append(
            f"validation true-edge FPR {val_metrics['true_edge_fpr']:.4f} above allowed {config.maximum_true_edge_fpr:.4f}"
        )
    if val_metrics["chain_indirect_tpr"] < val_baseline["chain_indirect_tpr"]:
        failures.append(
            f"validation chain indirect TPR {val_metrics['chain_indirect_tpr']:.4f} decreased below baseline "
            f"{val_baseline['chain_indirect_tpr']:.4f} -- should be impossible by construction"
        )
    if val_metrics["fork_indirect_tpr"] < val_baseline["fork_indirect_tpr"]:
        failures.append(
            f"validation fork indirect TPR {val_metrics['fork_indirect_tpr']:.4f} decreased below baseline "
            f"{val_baseline['fork_indirect_tpr']:.4f} -- should be impossible by construction"
        )
    if val_metrics["final_false_edge_rate"] > val_baseline["final_false_edge_rate"] + config.false_edge_rate_tolerance:
        failures.append(
            f"validation final false-edge rate {val_metrics['final_false_edge_rate']:.4f} exceeds baseline "
            f"{val_baseline['final_false_edge_rate']:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
        )

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(
        n,
        status,
        dpi_alpha,
        dev_baseline["overlap_indirect_tpr"],
        dev_baseline["true_edge_fpr"],
        dev_baseline["chain_indirect_tpr"],
        dev_baseline["fork_indirect_tpr"],
        dev_baseline["final_false_edge_rate"],
        selected_pi_min,
        val_metrics["overlap_indirect_tpr"],
        val_metrics["true_edge_fpr"],
        val_metrics["chain_indirect_tpr"],
        val_metrics["fork_indirect_tpr"],
        val_metrics["final_false_edge_rate"],
        dev_candidates,
        tuple(failures),
    )


def evaluate_stage3b_gate(raw: pd.DataFrame, config: Stage3bConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _plot_overlap_tpr_vs_pi_min(decision: GateDecision, config: Stage3bConfig, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(6, 4))
    for d in decision.by_n:
        pi_mins = [c.pi_min for c in d.development_candidates]
        tprs = [c.overlap_indirect_tpr for c in d.development_candidates]
        axis.plot(pi_mins, tprs, marker="o", label=f"N={d.n} (development)")
    axis.axhline(config.minimum_overlap_indirect_tpr, color="grey", linestyle="--", label="gate (.80)")
    axis.set_xlabel("pi_min")
    axis.set_ylabel("overlap indirect-edge TPR (filtered)")
    axis.set_ylim(-0.05, 1.05)
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_before_after(decision: GateDecision, path: Path) -> None:
    labels = ["overlap TPR", "true-edge FPR", "chain TPR", "fork TPR", "false-edge rate"]
    figure, axes = plt.subplots(1, len(decision.by_n), figsize=(5 * len(decision.by_n), 4), squeeze=False)
    for column, d in enumerate(decision.by_n):
        axis = axes[0][column]
        before = [
            d.baseline_overlap_indirect_tpr,
            d.baseline_true_edge_fpr,
            d.baseline_chain_indirect_tpr,
            d.baseline_fork_indirect_tpr,
            d.baseline_final_false_edge_rate,
        ]
        after = [
            d.validation_overlap_indirect_tpr,
            d.validation_true_edge_fpr,
            d.validation_chain_indirect_tpr,
            d.validation_fork_indirect_tpr,
            d.validation_final_false_edge_rate,
        ]
        x = np.arange(len(labels))
        width = 0.35
        axis.bar(x - width / 2, [v if v is not None else 0.0 for v in before], width, label="point estimate")
        axis.bar(x + width / 2, [v if v is not None else 0.0 for v in after], width, label="stability-filtered")
        axis.set_xticks(x)
        axis.set_xticklabels(labels, rotation=30, ha="right")
        axis.set_title(f"N={d.n} ({d.status})")
        axis.legend(fontsize="x-small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage3b_report(raw: pd.DataFrame, config: Stage3bConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage3b_gate(raw, config)

    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )

    _plot_overlap_tpr_vs_pi_min(decision, config, output_dir / "overlap_tpr_vs_pi_min.png")
    _plot_before_after(decision, output_dir / "before_after_filtering.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None or not np.isfinite(value) else f"{value:.4f}"

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

    (output_dir / "stage3b_report.md").write_text(
        "# Stage 3b Stability-Filtering Report\n\n"
        f"{table}\n\n"
        "`baseline` columns are the unmodified point-estimate pipeline (no "
        "filtering); `filtered` columns apply the selected `pi_min` "
        "threshold, evaluated on validation replicates. Chain and fork "
        "indirect TPR and the null false-edge rate are omitted from this "
        "table (reported in `decision.json`) since they are safe by "
        "construction under filtering -- the open questions this charter "
        "tests are the overlap TPR and true-edge FPR columns above.\n\n"
        "See `raw_metrics.csv`, `decision.json`, `overlap_tpr_vs_pi_min.png`, "
        "and `before_after_filtering.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
