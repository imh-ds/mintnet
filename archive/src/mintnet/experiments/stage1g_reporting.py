"""Frozen gate evaluation and evidence rendering for the Stage 1g conditional-independence experiment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from itertools import product

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage1g import Stage1gConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class GateDecision:
    """The immutable R2g decision derived from one run's raw evidence."""

    status: str
    selected_alpha_pair: tuple[float, float] | None
    metrics: dict[str, object]
    failures: tuple[str, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _target_sample_sizes(config: Stage1gConfig) -> tuple[int, ...]:
    """Use the frozen large-N gate cells that are present in this configuration.

    Per docs/stage1g_charter.md, the gate floor is N >= 750, raised from
    R2b's N >= 500 after R2b's strong-family triangle FPR failed only at
    N = 500 and improved monotonically with N. N = 500 evidence is still
    generated for continuity but is descriptive only here.
    """
    return tuple(n for n in config.sample_sizes if n >= 750)


def _has_complete_evidence(
    raw: pd.DataFrame,
    config: Stage1gConfig,
    bounds: tuple[int, int],
    alphas: tuple[float, ...],
) -> bool:
    """Require exactly one successful row for every frozen gate condition."""
    expected = pd.MultiIndex.from_tuples(
        list(
            product(
                ("chain", "fork", "triangle"),
                _target_sample_sizes(config),
                config.strengths,
                alphas,
                range(bounds[0], bounds[1] + 1),
            )
        ),
        names=["motif", "n", "strength", "alpha", "replicate"],
    )
    observed = _partition(raw, bounds)
    observed = observed.loc[
        observed["motif"].isin(("chain", "fork", "triangle"))
        & observed["n"].isin(_target_sample_sizes(config))
        & observed["strength"].isin(config.strengths)
        & observed["alpha"].isin(alphas),
        ["motif", "n", "strength", "alpha", "replicate"],
    ]
    observed_index = pd.MultiIndex.from_frame(observed)
    return not observed_index.has_duplicates and observed_index.sort_values().equals(expected.sort_values())


def aggregate_stage1g(raw: pd.DataFrame) -> pd.DataFrame:
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


def _development_alpha_margin(rows: pd.DataFrame, alpha: float, config: Stage1gConfig) -> float | None:
    """Return alpha's worst-case cell margin, or None if any cell is missing.

    Per docs/stage1g_charter.md: a chain/fork cell's margin is
    ``TPR - minimum_indirect_prune_tpr``; a triangle cell's margin is
    ``maximum_triangle_true_edge_prune_fpr - FPR``. An alpha's margin is the
    minimum across all its cells (its worst-case slack); it is eligible
    only if that minimum is non-negative. This replaces R2f's "first
    eligible pair wins" rule, which had no way to prefer a pair with real
    margin over one that barely, noisily cleared the bar (D-007).
    """
    target_n = _target_sample_sizes(config)
    margins: list[float] = []
    for n in target_n:
        for strength in config.strengths:
            chain_tpr = _validation_metric(rows, "chain", n, strength, alpha, "indirect_prune_tpr")
            fork_tpr = _validation_metric(rows, "fork", n, strength, alpha, "indirect_prune_tpr")
            triangle_fpr = _validation_metric(
                rows, "triangle", n, strength, alpha, "true_edge_prune_fpr"
            )
            if chain_tpr is None or fork_tpr is None or triangle_fpr is None:
                return None
            margins.append(chain_tpr - config.minimum_indirect_prune_tpr)
            margins.append(fork_tpr - config.minimum_indirect_prune_tpr)
            margins.append(config.maximum_triangle_true_edge_prune_fpr - triangle_fpr)
    return min(margins)


def select_alpha_pair(raw: pd.DataFrame, config: Stage1gConfig) -> tuple[float, float] | None:
    """Select the adjacent eligible pair with the largest worst-case margin.

    A small alpha requires strong evidence to retain an edge and therefore
    prunes aggressively (analogous to ``tau = 0``); a large alpha retains
    almost anything and prunes least (analogous to ``tau`` near its frozen
    maximum). Ascending numeric order of alpha therefore runs from most to
    least pruning, the same direction the R2 charter used for tau, so
    "adjacent" mirrors that charter's adjacent-tolerance-pair selection.
    Among adjacent pairs where both members are eligible (non-negative
    margin), the pair maximizing ``min(margin(left), margin(right))`` wins;
    ties fall back to the lexicographically lowest pair.
    """
    if raw.empty or not raw["status"].eq("ok").all():
        return None
    development = _partition(raw, config.development_replicates)
    if not _has_complete_evidence(
        development, config, config.development_replicates, tuple(config.alphas)
    ):
        return None
    ordered_alphas = tuple(sorted(config.alphas))
    margins = {alpha: _development_alpha_margin(development, alpha, config) for alpha in ordered_alphas}

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
    return best_pair


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


def evaluate_stage1g_gate(raw: pd.DataFrame, config: Stage1gConfig) -> GateDecision:
    """Apply fixed development selection and all-cell validation without retuning."""
    failures: list[str] = []
    if raw.empty or not raw["status"].eq("ok").all():
        failures.append("estimator, DGP, or Cholesky errors")

    development = _partition(raw, config.development_replicates)
    if not _has_complete_evidence(
        development, config, config.development_replicates, tuple(config.alphas)
    ):
        failures.append("missing development evidence")

    selected = select_alpha_pair(raw, config)
    if selected is None:
        failures.append("no eligible development alpha pair")
        return GateDecision("REASSESS", None, {}, tuple(failures))

    validation = _partition(raw.loc[raw["status"] == "ok"], config.validation_replicates)
    if not _has_complete_evidence(validation, config, config.validation_replicates, selected):
        failures.append("missing validation evidence")
        metrics: dict[str, object] = {"selected_alpha_pair": list(selected)}
        return GateDecision("REASSESS", selected, metrics, tuple(failures))

    target_n = _target_sample_sizes(config)
    cells: list[dict[str, object]] = []
    missing_cell = False
    chain_failed = False
    fork_failed = False
    triangle_failed = False
    for alpha in selected:
        for n in target_n:
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
                    cells.append(
                        {
                            "alpha": alpha,
                            "n": n,
                            "strength": strength,
                            "motif": motif,
                            "metric": metric,
                            "value": value,
                        }
                    )
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
    metrics: dict[str, object] = {
        "selected_alpha_pair": list(selected),
        "validation_cells": cells,
    }
    return GateDecision(
        "PROCEED" if not failures else "REASSESS", selected, metrics, tuple(failures)
    )


def _ground_truth_edges(motif: str) -> dict[str, bool]:
    if motif == "triangle":
        return {"01": True, "02": True, "12": True}
    return {"01": True, "02": False, "12": True}


def compute_calibration(raw: pd.DataFrame, config: Stage1gConfig) -> pd.DataFrame:
    """Exploratory, non-gating calibration of the confidence score against ground truth.

    For every edge decision at the selected-pair alphas (development
    replicates only, to avoid reusing validation evidence), compares the
    confidence score ``1 - p_value`` to whether the edge is actually a
    genuine edge of its motif. Reported per sample size and pooled; excluded
    from the PROCEED/REASSESS determination by charter.
    """
    ok = raw.loc[raw["status"] == "ok"]
    development = _partition(ok, config.development_replicates)
    records: list[dict[str, object]] = []
    for _, row in development.iterrows():
        truth = _ground_truth_edges(row["motif"])
        for pair in ("01", "02", "12"):
            confidence = row[f"confidence_{pair}"]
            if pd.isna(confidence):
                continue
            records.append(
                {
                    "n": row["n"],
                    "confidence": float(confidence),
                    "outcome": float(truth[pair]),
                }
            )
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


def _plot_runtime_vs_n(aggregate: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots()
    for (motif, alpha), values in aggregate.groupby(["motif", "alpha"]):
        by_n = values.groupby("n", as_index=False)["mean_runtime_seconds"].mean()
        axis.plot(by_n["n"], by_n["mean_runtime_seconds"], marker="o", label=f"{motif}, alpha={alpha:g}")
    axis.set_xlabel("N")
    axis.set_ylabel("Mean runtime (seconds)")
    axis.legend(fontsize="xx-small", ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage1g_report(raw: pd.DataFrame, config: Stage1gConfig, output_dir: Path) -> GateDecision:
    """Write all aggregate evidence and the frozen R2g decision for one run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage1g(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage1g_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps(asdict(decision), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    _plot_dpi_operating_curve(aggregate, output_dir / "dpi_operating_curve.png")
    _plot_performance_vs_alpha(aggregate, output_dir / "performance_vs_alpha.png")
    _plot_runtime_vs_n(aggregate, output_dir / "runtime_vs_n.png")

    calibration = compute_calibration(raw, config)
    calibration.to_csv(output_dir / "calibration_summary.csv", index=False)

    selected = "None" if decision.selected_alpha_pair is None else ", ".join(map(str, decision.selected_alpha_pair))
    failures = "None" if not decision.failures else ", ".join(decision.failures)
    (output_dir / "stage1g_report.md").write_text(
        "# Stage 1g Conditional-Independence Motif Validation Report\n\n"
        f"Decision: **{decision.status}**\n\n"
        f"Selected development alpha pair: `{selected}`\n\n"
        f"Failed criteria: {failures}\n\n"
        "Exploratory, non-gating confidence-score calibration is in "
        "`calibration_summary.csv` (Brier score of `1 - p_value` against "
        "ground truth, development replicates only).\n\n"
        "See `aggregate_metrics.csv`, `decision.json`, and the generated "
        "figures for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
