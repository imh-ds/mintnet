"""Per-N gate evaluation and evidence rendering for the Stage 3 bootstrap-
reproducibility experiment. See docs/stage3_charter.md.

The gate applies only to the primary (disjoint-triad) DGP. The secondary
(overlap-diagnostic) DGP is reported descriptively only -- it answers the
outline's Section 17.5 key failure test and carries no PROCEED/REASSESS
status of its own.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage3 import Stage3Config

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_PRIMARY_CATEGORIES = ("true_direct", "indirect", "null")
_SECONDARY_CATEGORIES = ("true_direct", "indirect_chain", "indirect_fork", "indirect_overlap", "null")


@dataclass(frozen=True)
class PiMinCandidate:
    pi_min: float
    stability_recall: float
    stability_fdr: float
    stability_final_false_edge_rate: float
    eligible: bool


@dataclass(frozen=True)
class NDecision:
    """The Stage 3 primary-DGP decision for a single sample size."""

    n: int
    status: str
    dpi_alpha: float
    selected_pi_min: float | None
    validation_stability_recall: float | None
    validation_stability_fdr: float | None
    validation_stability_final_false_edge_rate: float | None
    validation_baseline_final_false_edge_rate: float | None
    development_candidates: tuple[PiMinCandidate, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


@dataclass(frozen=True)
class SecondaryDiagnostic:
    """Descriptive-only stability summary for the overlap DGP, per category."""

    n: int
    replicates_ok: int
    replicates_error: int
    category_pi_final_mean: dict[str, float]
    category_pi_final_median: dict[str, float]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _replicate_has_error(subset: pd.DataFrame) -> bool:
    return bool((subset["status"] == "error").any())


def _stability_metrics(ok_rows: pd.DataFrame, pi_min: float) -> tuple[float, float, float]:
    """Pooled (sum-of-counts) stability recall, FDR, and final false-edge rate
    at threshold `pi_min`, mirroring D-013's corrected pooled-FDR convention
    (docs/decision_log.md D-013 correction) rather than a mean of per-replicate
    ratios -- the retained-edge count varies by replicate here, so the two
    differ in general."""
    true_direct = ok_rows.loc[ok_rows["category"] == "true_direct"]
    null_rows = ok_rows.loc[ok_rows["category"] == "null"]
    retained = ok_rows.loc[ok_rows["pi_final"] >= pi_min]
    null_retained = retained.loc[retained["category"] == "null"]

    stability_recall = (
        float((true_direct["pi_final"] >= pi_min).sum()) / float(len(true_direct)) if len(true_direct) > 0 else np.nan
    )
    stability_fdr = float(len(null_retained)) / float(len(retained)) if len(retained) > 0 else 0.0
    stability_final_false_edge_rate = (
        float((null_rows["pi_final"] >= pi_min).sum()) / float(len(null_rows)) if len(null_rows) > 0 else np.nan
    )
    return stability_recall, stability_fdr, stability_final_false_edge_rate


def _baseline_final_false_edge_rate(ok_rows: pd.DataFrame) -> float:
    """Point-estimate final false-edge rate (D-014's own metric), pooled
    across the same replicate subset being evaluated -- the null-pair count
    is constant per replicate (96), so pooled and mean-of-ratios coincide."""
    null_rows = ok_rows.loc[ok_rows["category"] == "null"]
    if null_rows.empty:
        return float("nan")
    return float(null_rows["final_point"].astype(bool).sum()) / float(len(null_rows))


def _evaluate_candidates(
    subset: pd.DataFrame, config: Stage3Config
) -> tuple[float, tuple[PiMinCandidate, ...]] | None:
    ok_rows = subset.loc[subset["status"] == "ok"]
    baseline = _baseline_final_false_edge_rate(ok_rows)
    candidates: list[PiMinCandidate] = []
    for pi_min in config.pi_min_candidates:
        recall, fdr, final_rate = _stability_metrics(ok_rows, pi_min)
        eligible = (
            np.isfinite(recall)
            and recall >= config.minimum_stability_recall
            and fdr <= config.maximum_stability_fdr
            and np.isfinite(final_rate)
            and final_rate <= baseline + config.false_edge_rate_tolerance
        )
        candidates.append(PiMinCandidate(pi_min, recall, fdr, final_rate, eligible))
    return baseline, tuple(candidates)


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage3Config) -> NDecision:
    n_raw = raw.loc[(raw["dgp"] == "primary") & (raw["n"] == n)]
    dpi_alpha = float(n_raw["dpi_alpha"].iloc[0]) if not n_raw.empty else float("nan")
    failures: list[str] = []

    development = _partition(n_raw, config.primary_development_replicates)
    if development.empty or _replicate_has_error(development):
        failures.append("estimator or DGP errors on development replicates")
        return NDecision(n, "REASSESS", dpi_alpha, None, None, None, None, None, (), tuple(failures))

    dev_baseline, dev_candidates = _evaluate_candidates(development, config)
    eligible = [c for c in dev_candidates if c.eligible]
    if not eligible:
        failures.append("no eligible pi_min on development replicates")
        return NDecision(n, "REASSESS", dpi_alpha, None, None, None, None, dev_baseline, dev_candidates, tuple(failures))

    selected_pi_min = min(c.pi_min for c in eligible)

    validation = _partition(n_raw, config.primary_validation_replicates)
    if validation.empty or _replicate_has_error(validation):
        failures.append("estimator or DGP errors on validation replicates")
        return NDecision(
            n, "REASSESS", dpi_alpha, selected_pi_min, None, None, None, dev_baseline, dev_candidates, tuple(failures)
        )

    val_ok = validation.loc[validation["status"] == "ok"]
    val_baseline = _baseline_final_false_edge_rate(val_ok)
    val_recall, val_fdr, val_final_rate = _stability_metrics(val_ok, selected_pi_min)

    if not (np.isfinite(val_recall) and val_recall >= config.minimum_stability_recall):
        failures.append(f"validation stability recall {val_recall:.4f} below required {config.minimum_stability_recall:.4f}")
    if val_fdr > config.maximum_stability_fdr:
        failures.append(f"validation stability FDR {val_fdr:.4f} above allowed {config.maximum_stability_fdr:.4f}")
    if not (np.isfinite(val_final_rate) and val_final_rate <= val_baseline + config.false_edge_rate_tolerance):
        failures.append(
            f"validation stability-filtered final false-edge rate {val_final_rate:.4f} exceeds baseline "
            f"{val_baseline:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
        )

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(
        n,
        status,
        dpi_alpha,
        selected_pi_min,
        val_recall,
        val_fdr,
        val_final_rate,
        val_baseline,
        dev_candidates,
        tuple(failures),
    )


def evaluate_stage3_gate(raw: pd.DataFrame, config: Stage3Config) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.primary_sample_sizes))


def evaluate_secondary_diagnostic(raw: pd.DataFrame, config: Stage3Config) -> SecondaryDiagnostic:
    subset = raw.loc[raw["dgp"] == "secondary_overlap_diagnostic"]
    ok_rows = subset.loc[subset["status"] == "ok"]
    replicates_error = int(subset.loc[subset["status"] == "error", "replicate"].nunique())
    replicates_ok = int(ok_rows["replicate"].nunique()) if not ok_rows.empty else 0

    means: dict[str, float] = {}
    medians: dict[str, float] = {}
    for category in _SECONDARY_CATEGORIES:
        values = ok_rows.loc[ok_rows["category"] == category, "pi_final"]
        means[category] = float(values.mean()) if len(values) > 0 else float("nan")
        medians[category] = float(values.median()) if len(values) > 0 else float("nan")

    return SecondaryDiagnostic(
        n=config.secondary_sample_size,
        replicates_ok=replicates_ok,
        replicates_error=replicates_error,
        category_pi_final_mean=means,
        category_pi_final_median=medians,
    )


def _plot_stability_by_category(raw: pd.DataFrame, config: Stage3Config, path: Path) -> None:
    primary_ok = raw.loc[(raw["dgp"] == "primary") & (raw["status"] == "ok")]
    figure, axes = plt.subplots(1, len(config.primary_sample_sizes), figsize=(5 * len(config.primary_sample_sizes), 4), squeeze=False)
    for column, n in enumerate(config.primary_sample_sizes):
        axis = axes[0][column]
        subset = _partition(primary_ok.loc[primary_ok["n"] == n], config.primary_validation_replicates)
        data = [subset.loc[subset["category"] == category, "pi_final"].to_numpy() for category in _PRIMARY_CATEGORIES]
        axis.boxplot(data, tick_labels=_PRIMARY_CATEGORIES, showfliers=False)
        axis.set_title(f"primary DGP, N={n} (validation)")
        axis.set_ylabel("pi_final (final-edge bootstrap stability)")
        axis.set_ylim(-0.05, 1.05)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_secondary_diagnostic(raw: pd.DataFrame, config: Stage3Config, path: Path) -> None:
    subset = raw.loc[(raw["dgp"] == "secondary_overlap_diagnostic") & (raw["status"] == "ok")]
    figure, axis = plt.subplots(figsize=(6, 4))
    data = [subset.loc[subset["category"] == category, "pi_final"].to_numpy() for category in _SECONDARY_CATEGORIES]
    axis.boxplot(data, tick_labels=_SECONDARY_CATEGORIES, showfliers=False)
    axis.set_title(f"secondary (overlap) DGP, N={config.secondary_sample_size} -- diagnostic only")
    axis.set_ylabel("pi_final (final-edge bootstrap stability)")
    axis.set_ylim(-0.05, 1.05)
    plt.setp(axis.get_xticklabels(), rotation=20, ha="right")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage3_report(raw: pd.DataFrame, config: Stage3Config, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage3_gate(raw, config)
    secondary = evaluate_secondary_diagnostic(raw, config)

    (output_dir / "decision.json").write_text(
        json.dumps(
            {
                "by_n": [asdict(d) for d in decision.by_n],
                "secondary_overlap_diagnostic": asdict(secondary),
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )

    _plot_stability_by_category(raw, config, output_dir / "stability_by_category.png")
    _plot_secondary_diagnostic(raw, config, output_dir / "secondary_overlap_diagnostic.png")

    rows = [
        "| N | status | dpi_alpha | selected pi_min | validation recall | validation FDR | "
        "validation final rate | baseline final rate | failures |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        def fmt(value: float | None) -> str:
            return "None" if value is None or not np.isfinite(value) else f"{value:.4f}"

        pi_min = "None" if d.selected_pi_min is None else f"{d.selected_pi_min:.2f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {d.dpi_alpha:.4f} | {pi_min} | {fmt(d.validation_stability_recall)} | "
            f"{fmt(d.validation_stability_fdr)} | {fmt(d.validation_stability_final_false_edge_rate)} | "
            f"{fmt(d.validation_baseline_final_false_edge_rate)} | {failures} |"
        )
    table = "\n".join(rows)

    secondary_rows = [
        "| category | mean pi_final | median pi_final |",
        "|---|---|---|",
    ]
    for category in _SECONDARY_CATEGORIES:
        secondary_rows.append(
            f"| {category} | {secondary.category_pi_final_mean[category]:.4f} | "
            f"{secondary.category_pi_final_median[category]:.4f} |"
        )
    secondary_table = "\n".join(secondary_rows)

    (output_dir / "stage3_report.md").write_text(
        "# Stage 3 Bootstrap Reproducibility Report\n\n"
        "## Primary DGP (gated): disjoint chain/fork/triangle network\n\n"
        f"{table}\n\n"
        "## Secondary DGP (diagnostic only, not gated): shared-node-overlap "
        f"network at N={secondary.n}\n\n"
        f"Replicates: {secondary.replicates_ok} ok, {secondary.replicates_error} error.\n\n"
        f"{secondary_table}\n\n"
        "`indirect_overlap` is the category D-018 found the pipeline "
        "systematically fails to prune (~41% of the time) at this N. This "
        "table exists to answer the outline's Section 17.5 key failure "
        "test: elevated stability here, comparable to `true_direct`, would "
        "confirm bootstrap stability does not automatically protect "
        "against a known, quantified pruning failure mode.\n\n"
        "See `raw_metrics.csv`, `decision.json`, `stability_by_category.png`, "
        "and `secondary_overlap_diagnostic.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
