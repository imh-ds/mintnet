"""Per-N gate evaluation and evidence rendering for the Stage 3d
general-stability-gate-on-overlap experiment. See docs/stage3d_charter.md.

The gate itself is Stage 3's exact three criteria (recall over
`true_direct`, pooled FDR over `null`, no-regression on the `null`-only
final false-edge rate) -- it never inspects the `indirect_chain`/
`indirect_fork`/`indirect_overlap` categories, by design (see the
charter's Non-goals section). This module additionally computes a
descriptive-only summary of those indirect categories at the selected
`pi_min`, specifically so a PROCEED here is never reported without the
context that it says nothing about D-018's indirect-edge finding.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage3d import Stage3dConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_ALL_CATEGORIES = ("true_direct", "indirect_chain", "indirect_fork", "indirect_overlap", "null")
_INDIRECT_CATEGORIES = ("indirect_chain", "indirect_fork", "indirect_overlap")


@dataclass(frozen=True)
class PiMinCandidate:
    pi_min: float
    stability_recall: float
    stability_fdr: float
    stability_final_false_edge_rate: float
    eligible: bool


@dataclass(frozen=True)
class IndirectSummary:
    """Descriptive-only: how the categories the gate never inspects behave
    at the selected pi_min. Not part of PROCEED/REASSESS."""

    category_pi_final_mean: dict[str, float]
    category_pi_final_median: dict[str, float]
    category_fraction_retained_at_selected_pi_min: dict[str, float | None]


@dataclass(frozen=True)
class NDecision:
    n: int
    status: str
    dpi_alpha: float
    selected_pi_min: float | None
    validation_stability_recall: float | None
    validation_stability_fdr: float | None
    validation_stability_final_false_edge_rate: float | None
    validation_baseline_final_false_edge_rate: float | None
    development_candidates: tuple[PiMinCandidate, ...]
    indirect_summary: IndirectSummary
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _replicate_has_error(subset: pd.DataFrame) -> bool:
    return bool((subset["status"] == "error").any())


def _stability_metrics(ok_rows: pd.DataFrame, pi_min: float) -> tuple[float, float, float]:
    """Pooled (sum-of-counts) stability recall, FDR, and final false-edge rate
    at threshold `pi_min` -- Stage 3's exact convention, unmodified. Only
    `true_direct` and `null` rows feed the numerators/recall denominator;
    indirect rows contribute to the FDR denominator (total retained) like
    any non-null retained pair, per Stage 2's original pooled-FDR definition,
    but never to its numerator, since they are not null pairs."""
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
    null_rows = ok_rows.loc[ok_rows["category"] == "null"]
    if null_rows.empty:
        return float("nan")
    return float(null_rows["final_point"].astype(bool).sum()) / float(len(null_rows))


def _evaluate_candidates(subset: pd.DataFrame, config: Stage3dConfig) -> tuple[float, tuple[PiMinCandidate, ...]]:
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


def _indirect_summary(ok_rows: pd.DataFrame, selected_pi_min: float | None) -> IndirectSummary:
    means: dict[str, float] = {}
    medians: dict[str, float] = {}
    retained_fraction: dict[str, float | None] = {}
    for category in _INDIRECT_CATEGORIES:
        values = ok_rows.loc[ok_rows["category"] == category, "pi_final"]
        means[category] = float(values.mean()) if len(values) > 0 else float("nan")
        medians[category] = float(values.median()) if len(values) > 0 else float("nan")
        if selected_pi_min is None or len(values) == 0:
            retained_fraction[category] = None
        else:
            retained_fraction[category] = float((values >= selected_pi_min).mean())
    return IndirectSummary(means, medians, retained_fraction)


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage3dConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    dpi_alpha = float(n_raw["dpi_alpha"].iloc[0]) if not n_raw.empty else float("nan")
    failures: list[str] = []

    development = _partition(n_raw, config.development_replicates)
    if development.empty or _replicate_has_error(development):
        failures.append("estimator or DGP errors on development replicates")
        empty_summary = _indirect_summary(pd.DataFrame(columns=n_raw.columns), None)
        return NDecision(n, "REASSESS", dpi_alpha, None, None, None, None, None, (), empty_summary, tuple(failures))

    dev_ok = development.loc[development["status"] == "ok"]
    dev_baseline, dev_candidates = _evaluate_candidates(development, config)
    eligible = [c for c in dev_candidates if c.eligible]
    if not eligible:
        failures.append("no eligible pi_min on development replicates")
        summary = _indirect_summary(dev_ok, None)
        return NDecision(
            n, "REASSESS", dpi_alpha, None, None, None, None, dev_baseline, dev_candidates, summary, tuple(failures)
        )

    selected_pi_min = min(c.pi_min for c in eligible)

    validation = _partition(n_raw, config.validation_replicates)
    if validation.empty or _replicate_has_error(validation):
        failures.append("estimator or DGP errors on validation replicates")
        summary = _indirect_summary(dev_ok, selected_pi_min)
        return NDecision(
            n,
            "REASSESS",
            dpi_alpha,
            selected_pi_min,
            None,
            None,
            None,
            dev_baseline,
            dev_candidates,
            summary,
            tuple(failures),
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
    summary = _indirect_summary(val_ok, selected_pi_min)
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
        summary,
        tuple(failures),
    )


def evaluate_stage3d_gate(raw: pd.DataFrame, config: Stage3dConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _plot_stability_by_category(raw: pd.DataFrame, config: Stage3dConfig, path: Path) -> None:
    ok_rows = raw.loc[raw["status"] == "ok"]
    figure, axes = plt.subplots(1, len(config.sample_sizes), figsize=(6 * len(config.sample_sizes), 4), squeeze=False)
    for column, n in enumerate(config.sample_sizes):
        axis = axes[0][column]
        subset = _partition(ok_rows.loc[ok_rows["n"] == n], config.validation_replicates)
        data = [subset.loc[subset["category"] == category, "pi_final"].to_numpy() for category in _ALL_CATEGORIES]
        axis.boxplot(data, tick_labels=_ALL_CATEGORIES, showfliers=False)
        axis.set_title(f"overlap DGP, N={n} (validation)")
        axis.set_ylabel("pi_final (final-edge bootstrap stability)")
        axis.set_ylim(-0.05, 1.05)
        plt.setp(axis.get_xticklabels(), rotation=20, ha="right")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage3d_report(raw: pd.DataFrame, config: Stage3dConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage3d_gate(raw, config)

    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )

    _plot_stability_by_category(raw, config, output_dir / "stability_by_category.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None or not np.isfinite(value) else f"{value:.4f}"

    rows = [
        "| N | status | dpi_alpha | selected pi_min | validation recall | validation FDR | "
        "validation final rate | baseline final rate | failures |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        pi_min = "None" if d.selected_pi_min is None else f"{d.selected_pi_min:.2f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {d.dpi_alpha:.4f} | {pi_min} | {fmt(d.validation_stability_recall)} | "
            f"{fmt(d.validation_stability_fdr)} | {fmt(d.validation_stability_final_false_edge_rate)} | "
            f"{fmt(d.validation_baseline_final_false_edge_rate)} | {failures} |"
        )
    table = "\n".join(rows)

    indirect_rows = [
        "| N | category | mean pi_final | median pi_final | fraction retained at selected pi_min |",
        "|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        for category in _INDIRECT_CATEGORIES:
            retained = d.indirect_summary.category_fraction_retained_at_selected_pi_min[category]
            retained_str = "N/A (no pi_min selected)" if retained is None else f"{retained:.4f}"
            indirect_rows.append(
                f"| {d.n} | {category} | {fmt(d.indirect_summary.category_pi_final_mean[category])} | "
                f"{fmt(d.indirect_summary.category_pi_final_median[category])} | {retained_str} |"
            )
    indirect_table = "\n".join(indirect_rows)

    (output_dir / "stage3d_report.md").write_text(
        "# Stage 3d General Stability Gate on the Overlap Network Report\n\n"
        f"{table}\n\n"
        "**A PROCEED above, including at N=750, does not mean D-018's "
        "indirect-edge pruning failure is resolved or reassessed.** This "
        "gate's three criteria (recall over `true_direct`, pooled FDR over "
        "`null`, no-regression on the `null`-only final false-edge rate) "
        "never inspect the indirect-edge categories below -- it cannot "
        "detect that failure by construction. See `docs/stage3d_charter.md`'s "
        "Non-goals section.\n\n"
        "## Indirect-edge categories (descriptive only, not gated)\n\n"
        f"{indirect_table}\n\n"
        "`fraction retained at selected pi_min` is the fraction of that "
        "category's instances that would survive a stability filter at "
        "this charter's own selected `pi_min` -- included for context "
        "against Stage 3b's separate, DGP-specific filtering charter, not "
        "as a claim this charter tests filtering.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and "
        "`stability_by_category.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
