"""Per-N gate evaluation and evidence rendering for the Stage 1h experiment.

Unlike every prior Stage 1 charter, R2h selects and validates an alpha pair
independently for each sample size rather than requiring one pair to pass
across a pooled range of N (docs/stage1h_charter.md).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from itertools import product

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage1h import Stage1hConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class NDecision:
    """The immutable R2h decision for a single sample size."""

    n: int
    status: str
    selected_alpha_pair: tuple[float, float] | None
    margin: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    """The immutable R2h decision: one status per sample size, not a single global one."""

    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _has_complete_evidence_for_n(
    raw: pd.DataFrame,
    n: int,
    config: Stage1hConfig,
    bounds: tuple[int, int],
    alphas: tuple[float, ...],
) -> bool:
    """Require exactly one successful row for every frozen gate condition at this N."""
    expected = pd.MultiIndex.from_tuples(
        list(product(("chain", "fork", "triangle"), config.strengths, alphas, range(bounds[0], bounds[1] + 1))),
        names=["motif", "strength", "alpha", "replicate"],
    )
    observed = raw.loc[
        (raw["n"] == n)
        & raw["motif"].isin(("chain", "fork", "triangle"))
        & raw["strength"].isin(config.strengths)
        & raw["alpha"].isin(alphas),
        ["motif", "strength", "alpha", "replicate"],
    ]
    observed_index = pd.MultiIndex.from_frame(observed)
    return not observed_index.has_duplicates and observed_index.sort_values().equals(expected.sort_values())


def aggregate_stage1h(raw: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw replicate evidence without discarding recorded failures."""
    grouped = raw.groupby(["motif", "family", "strength", "n", "alpha"], as_index=False)
    return (
        grouped.agg(
            replicates=("replicate", "size"),
            successful_replicates=("status", lambda values: int(values.eq("ok").sum())),
            indirect_prune_tpr=("indirect_prune_tpr", "mean"),
            true_edge_prune_fpr=("true_edge_prune_fpr", "mean"),
            perfect_recovery=("perfect_recovery", "mean"),
            mean_runtime_seconds=("elapsed_seconds", "mean"),
        )
        .sort_values(["motif", "n", "strength", "alpha"])
        .reset_index(drop=True)
    )


def _validation_metric(
    rows: pd.DataFrame, motif: str, n: int, strength: float, alpha: float, metric: str
) -> float | None:
    values = rows.loc[
        (rows["motif"] == motif)
        & (rows["n"] == n)
        & (rows["strength"] == strength)
        & (rows["alpha"] == alpha),
        metric,
    ]
    if values.empty or not np.isfinite(values).all():
        return None
    return float(values.mean())


def _alpha_margin_at_n(rows: pd.DataFrame, n: int, alpha: float, config: Stage1hConfig) -> float | None:
    """Worst-case margin for one alpha at one N, across all strengths, or None if incomplete."""
    margins: list[float] = []
    for strength in config.strengths:
        chain_tpr = _validation_metric(rows, "chain", n, strength, alpha, "indirect_prune_tpr")
        fork_tpr = _validation_metric(rows, "fork", n, strength, alpha, "indirect_prune_tpr")
        triangle_fpr = _validation_metric(rows, "triangle", n, strength, alpha, "true_edge_prune_fpr")
        if chain_tpr is None or fork_tpr is None or triangle_fpr is None:
            return None
        margins.append(chain_tpr - config.minimum_indirect_prune_tpr)
        margins.append(fork_tpr - config.minimum_indirect_prune_tpr)
        margins.append(config.maximum_triangle_true_edge_prune_fpr - triangle_fpr)
    return min(margins)


def select_alpha_pair_for_n(
    raw: pd.DataFrame, n: int, config: Stage1hConfig
) -> tuple[tuple[float, float] | None, float | None]:
    """Margin-robust selection (R2g's rule) scoped to a single sample size."""
    if raw.empty or not raw["status"].eq("ok").all():
        return None, None
    development = _partition(raw, config.development_replicates)
    if not _has_complete_evidence_for_n(
        development, n, config, config.development_replicates, tuple(config.alphas)
    ):
        return None, None
    ordered_alphas = tuple(sorted(config.alphas))
    margins = {alpha: _alpha_margin_at_n(development, n, alpha, config) for alpha in ordered_alphas}

    best_pair: tuple[float, float] | None = None
    best_score = -float("inf")
    for left, right in zip(ordered_alphas, ordered_alphas[1:]):
        left_margin, right_margin = margins[left], margins[right]
        if left_margin is None or right_margin is None:
            continue
        if left_margin < 0.0 or right_margin < 0.0:
            continue
        score = min(left_margin, right_margin)
        if score > best_score:
            best_score = score
            best_pair = (left, right)
    return best_pair, (best_score if best_pair is not None else None)


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage1hConfig) -> NDecision:
    """Apply independent development selection and all-cell validation for one N."""
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator, DGP, or Cholesky errors")

    development = _partition(n_raw, config.development_replicates)
    if not _has_complete_evidence_for_n(
        development, n, config, config.development_replicates, tuple(config.alphas)
    ):
        failures.append("missing development evidence")

    pair, margin = select_alpha_pair_for_n(n_raw, n, config)
    if pair is None:
        failures.append("no eligible development alpha pair")
        return NDecision(n, "REASSESS", None, None, tuple(failures))

    validation = _partition(n_raw.loc[n_raw["status"] == "ok"], config.validation_replicates)
    if not _has_complete_evidence_for_n(validation, n, config, config.validation_replicates, pair):
        failures.append("missing validation evidence")
        return NDecision(n, "REASSESS", pair, margin, tuple(failures))

    missing_cell = False
    chain_failed = fork_failed = triangle_failed = False
    for alpha in pair:
        for strength in config.strengths:
            for motif, metric, threshold, comparison in (
                ("chain", "indirect_prune_tpr", config.minimum_indirect_prune_tpr, "minimum"),
                ("fork", "indirect_prune_tpr", config.minimum_indirect_prune_tpr, "minimum"),
                (
                    "triangle",
                    "true_edge_prune_fpr",
                    config.maximum_triangle_true_edge_prune_fpr,
                    "maximum",
                ),
            ):
                value = _validation_metric(validation, motif, n, strength, alpha, metric)
                if value is None:
                    missing_cell = True
                elif comparison == "minimum" and value < threshold:
                    chain_failed |= motif == "chain"
                    fork_failed |= motif == "fork"
                elif comparison == "maximum" and value > threshold:
                    triangle_failed = True

    if missing_cell:
        failures.append("missing validation cell")
    if chain_failed:
        failures.append("chain indirect-edge TPR")
    if fork_failed:
        failures.append("fork indirect-edge TPR")
    if triangle_failed:
        failures.append("triangle genuine-edge pruning FPR")
    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(n, status, pair, margin, tuple(failures))


def evaluate_stage1h_gate(raw: pd.DataFrame, config: Stage1hConfig) -> GateDecision:
    """Evaluate every sample size independently, producing a per-N table."""
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _ground_truth_edges(motif: str) -> dict[str, bool]:
    if motif == "triangle":
        return {"01": True, "02": True, "12": True}
    return {"01": True, "02": False, "12": True}


def compute_calibration(raw: pd.DataFrame, config: Stage1hConfig) -> pd.DataFrame:
    """Exploratory, non-gating calibration of the confidence score against ground truth."""
    ok = raw.loc[raw["status"] == "ok"]
    development = _partition(ok, config.development_replicates)
    records: list[dict[str, object]] = []
    for _, row in development.iterrows():
        truth = _ground_truth_edges(row["motif"])
        for pair in ("01", "02", "12"):
            confidence = row[f"confidence_{pair}"]
            if pd.isna(confidence):
                continue
            records.append({"n": row["n"], "confidence": float(confidence), "outcome": float(truth[pair])})
    table = pd.DataFrame(records)
    if table.empty:
        return pd.DataFrame(columns=["n", "brier_score", "count"])

    def _brier(group: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "brier_score": float(np.mean((group["confidence"] - group["outcome"]) ** 2)),
                "count": int(len(group)),
            }
        )

    per_n = table.groupby("n").apply(_brier, include_groups=False).reset_index()
    pooled = _brier(table)
    pooled_row = pd.DataFrame([{"n": "pooled", **pooled.to_dict()}])
    return pd.concat([per_n, pooled_row], ignore_index=True)


def _plot_dpi_operating_curve(aggregate: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots()
    for motif, metric, label in (
        ("chain", "indirect_prune_tpr", "chain indirect TPR"),
        ("fork", "indirect_prune_tpr", "fork indirect TPR"),
        ("triangle", "true_edge_prune_fpr", "triangle true-edge FPR"),
    ):
        values = aggregate.loc[aggregate["motif"] == motif].groupby("alpha", as_index=False)[metric].mean()
        if not values.empty:
            axis.plot(values["alpha"], values[metric], marker="o", label=label)
    axis.set_xlabel("Significance level (alpha)")
    axis.set_ylabel("Pruning rate")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_performance_vs_alpha(aggregate: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots()
    for (motif, n, strength), values in aggregate.groupby(["motif", "n", "strength"]):
        axis.plot(
            values["alpha"], values["perfect_recovery"], marker="o", label=f"{motif}, N={n}, a={strength:g}"
        )
    axis.set_xlabel("Significance level (alpha)")
    axis.set_ylabel("Perfect recovery rate")
    axis.legend(fontsize="xx-small", ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_margin_vs_n(decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    ns = [d.n for d in decision.by_n]
    margins = [d.margin if d.margin is not None else float("nan") for d in decision.by_n]
    colors = ["tab:green" if d.status == "PROCEED" else "tab:red" for d in decision.by_n]
    axis.scatter(ns, margins, c=colors)
    axis.axhline(0.0, color="black", linewidth=0.5)
    axis.set_xlabel("N")
    axis.set_ylabel("Selected pair worst-case margin")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage1h_report(raw: pd.DataFrame, config: Stage1hConfig, output_dir: Path) -> GateDecision:
    """Write all aggregate evidence and the frozen R2h per-N decision table."""
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage1h(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage1h_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_dpi_operating_curve(aggregate, output_dir / "dpi_operating_curve.png")
    _plot_performance_vs_alpha(aggregate, output_dir / "performance_vs_alpha.png")
    _plot_margin_vs_n(decision, output_dir / "margin_vs_n.png")

    calibration = compute_calibration(raw, config)
    calibration.to_csv(output_dir / "calibration_summary.csv", index=False)

    rows = ["| N | status | selected alpha pair | margin | failures |", "|---|---|---|---|---|"]
    for d in decision.by_n:
        pair = "None" if d.selected_alpha_pair is None else ", ".join(map(str, d.selected_alpha_pair))
        margin = "None" if d.margin is None else f"{d.margin:.4f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(f"| {d.n} | {d.status} | `{pair}` | {margin} | {failures} |")
    table = "\n".join(rows)
    (output_dir / "stage1h_report.md").write_text(
        "# Stage 1h Per-N Alpha Selection Report\n\n"
        "Each sample size is selected and validated independently; there is "
        "no single global status for this charter.\n\n"
        f"{table}\n\n"
        "Exploratory, non-gating confidence-score calibration is in "
        "`calibration_summary.csv` (Brier score of `1 - p_value` against "
        "ground truth, development replicates only).\n\n"
        "See `aggregate_metrics.csv`, `decision.json`, and the generated "
        "figures for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
