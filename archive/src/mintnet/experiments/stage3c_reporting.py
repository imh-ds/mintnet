"""Per-N gate evaluation and evidence rendering for the Stage 3c
bootstrap-stability-on-hub-network experiment. See docs/stage3c_charter.md.

Mirrors Stage 3's primary-DGP gate exactly (`mintnet.experiments.
stage3_reporting`'s `_stability_metrics`/`_evaluate_candidates`/
`evaluate_n` logic) -- re-implemented here rather than imported because
Stage3cConfig has its own field names and this DGP has only one
category set (no secondary diagnostic DGP), matching this project's
existing convention of one reporting module per stage even where the
gate logic overlaps (stage3_reporting vs. stage3b_reporting).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage3c import Stage3cConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_CATEGORIES = ("true_direct", "indirect", "null")


@dataclass(frozen=True)
class PiMinCandidate:
    pi_min: float
    stability_recall: float
    stability_fdr: float
    stability_final_false_edge_rate: float
    eligible: bool


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
    at threshold `pi_min` -- same pooled-count convention as Stage 3/D-013."""
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
    """Point-estimate final false-edge rate (D-016's own metric), pooled
    across the same replicate subset being evaluated."""
    null_rows = ok_rows.loc[ok_rows["category"] == "null"]
    if null_rows.empty:
        return float("nan")
    return float(null_rows["final_point"].astype(bool).sum()) / float(len(null_rows))


def _evaluate_candidates(subset: pd.DataFrame, config: Stage3cConfig) -> tuple[float, tuple[PiMinCandidate, ...]]:
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


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage3cConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    dpi_alpha = float(n_raw["dpi_alpha"].iloc[0]) if not n_raw.empty else float("nan")
    failures: list[str] = []

    development = _partition(n_raw, config.development_replicates)
    if development.empty or _replicate_has_error(development):
        failures.append("estimator or DGP errors on development replicates")
        return NDecision(n, "REASSESS", dpi_alpha, None, None, None, None, None, (), tuple(failures))

    dev_baseline, dev_candidates = _evaluate_candidates(development, config)
    eligible = [c for c in dev_candidates if c.eligible]
    if not eligible:
        failures.append("no eligible pi_min on development replicates")
        return NDecision(n, "REASSESS", dpi_alpha, None, None, None, None, dev_baseline, dev_candidates, tuple(failures))

    selected_pi_min = min(c.pi_min for c in eligible)

    validation = _partition(n_raw, config.validation_replicates)
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


def evaluate_stage3c_gate(raw: pd.DataFrame, config: Stage3cConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _plot_stability_by_category(raw: pd.DataFrame, config: Stage3cConfig, path: Path) -> None:
    ok_rows = raw.loc[raw["status"] == "ok"]
    figure, axes = plt.subplots(1, len(config.sample_sizes), figsize=(5 * len(config.sample_sizes), 4), squeeze=False)
    for column, n in enumerate(config.sample_sizes):
        axis = axes[0][column]
        subset = _partition(ok_rows.loc[ok_rows["n"] == n], config.validation_replicates)
        data = [subset.loc[subset["category"] == category, "pi_final"].to_numpy() for category in _CATEGORIES]
        axis.boxplot(data, tick_labels=_CATEGORIES, showfliers=False)
        axis.set_title(f"hub DGP, N={n} (validation)")
        axis.set_ylabel("pi_final (final-edge bootstrap stability)")
        axis.set_ylim(-0.05, 1.05)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage3c_report(raw: pd.DataFrame, config: Stage3cConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage3c_gate(raw, config)

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

    (output_dir / "stage3c_report.md").write_text(
        "# Stage 3c Bootstrap Stability on the Hub Network Report\n\n"
        f"{table}\n\n"
        "This re-runs Stage 3's exact primary-DGP gate on Stage 2c's "
        "chain/fork/hub composed network, closing the gap flagged in "
        "D-019/D-020: the general stability-selection gate had only been "
        "checked on the disjoint-triad network before this charter.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and "
        "`stability_by_category.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
