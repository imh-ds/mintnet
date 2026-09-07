"""Frozen gate evaluation and evidence rendering for the Stage 1 DPI experiment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from itertools import product

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage1 import Stage1Config

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class GateDecision:
    """The immutable R2 decision derived from one run's raw evidence."""

    status: str
    selected_tau_pair: tuple[float, float] | None
    metrics: dict[str, object]
    failures: tuple[str, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _target_sample_sizes(config: Stage1Config) -> tuple[int, ...]:
    """Use the frozen large-N gate cells that are present in this configuration."""
    return tuple(n for n in config.sample_sizes if n >= 500)


def _has_complete_evidence(
    raw: pd.DataFrame,
    config: Stage1Config,
    bounds: tuple[int, int],
    taus: tuple[float, ...],
) -> bool:
    """Require exactly one successful row for every frozen gate condition."""
    expected = pd.MultiIndex.from_tuples(
        list(
            product(
                ("chain", "fork", "triangle"),
                _target_sample_sizes(config),
                config.strengths,
                taus,
                range(bounds[0], bounds[1] + 1),
            )
        ),
        names=["motif", "n", "strength", "tau", "replicate"],
    )
    observed = _partition(raw, bounds)
    observed = observed.loc[
        observed["motif"].isin(("chain", "fork", "triangle"))
        & observed["n"].isin(_target_sample_sizes(config))
        & observed["strength"].isin(config.strengths)
        & observed["tau"].isin(taus),
        ["motif", "n", "strength", "tau", "replicate"],
    ]
    observed_index = pd.MultiIndex.from_frame(observed)
    return not observed_index.has_duplicates and observed_index.sort_values().equals(expected.sort_values())


def aggregate_stage1(raw: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw replicate evidence without discarding recorded failures."""
    grouped = raw.groupby(["motif", "family", "strength", "n", "tau"], as_index=False)
    return (
        grouped.agg(
            replicates=("replicate", "size"),
            successful_replicates=("status", lambda values: int(values.eq("ok").sum())),
            indirect_prune_tpr=("indirect_prune_tpr", "mean"),
            true_edge_prune_fpr=("true_edge_prune_fpr", "mean"),
            perfect_recovery=("perfect_recovery", "mean"),
            mean_runtime_seconds=("elapsed_seconds", "mean"),
        )
        .sort_values(["motif", "n", "strength", "tau"])
        .reset_index(drop=True)
    )


def _pooled_metric(rows: pd.DataFrame, motif: str, tau: float, metric: str) -> float | None:
    values = rows.loc[(rows["motif"] == motif) & (rows["tau"] == tau), metric]
    if values.empty or not np.isfinite(values).all():
        return None
    return float(values.mean())


def _development_tau_passes(rows: pd.DataFrame, tau: float, config: Stage1Config) -> bool:
    chain_tpr = _pooled_metric(rows, "chain", tau, "indirect_prune_tpr")
    fork_tpr = _pooled_metric(rows, "fork", tau, "indirect_prune_tpr")
    triangle_fpr = _pooled_metric(rows, "triangle", tau, "true_edge_prune_fpr")
    return (
        chain_tpr is not None
        and fork_tpr is not None
        and triangle_fpr is not None
        and chain_tpr >= config.minimum_indirect_prune_tpr
        and fork_tpr >= config.minimum_indirect_prune_tpr
        and triangle_fpr <= config.maximum_triangle_true_edge_prune_fpr
    )


def select_tau_pair(raw: pd.DataFrame, config: Stage1Config) -> tuple[float, float] | None:
    """Select the first adjacent development pair meeting the pooled frozen gate."""
    if raw.empty or not raw["status"].eq("ok").all():
        return None
    target_n = _target_sample_sizes(config)
    development = _partition(raw, config.development_replicates)
    if not _has_complete_evidence(
        development, config, config.development_replicates, tuple(config.taus)
    ):
        return None
    development = development.loc[development["n"].isin(target_n)]
    ordered_taus = tuple(sorted(config.taus))
    for left, right in zip(ordered_taus, ordered_taus[1:]):
        if _development_tau_passes(development, left, config) and _development_tau_passes(
            development, right, config
        ):
            return (left, right)
    return None


def _validation_metric(
    rows: pd.DataFrame, motif: str, n: int, strength: float, tau: float, metric: str
) -> float | None:
    values = rows.loc[
        (rows["motif"] == motif)
        & (rows["n"] == n)
        & (rows["strength"] == strength)
        & (rows["tau"] == tau),
        metric,
    ]
    if values.empty or not np.isfinite(values).all():
        return None
    return float(values.mean())


def evaluate_stage1_gate(raw: pd.DataFrame, config: Stage1Config) -> GateDecision:
    """Apply fixed development selection and all-cell validation without retuning."""
    failures: list[str] = []
    if raw.empty or not raw["status"].eq("ok").all():
        failures.append("estimator, DGP, or Cholesky errors")

    development = _partition(raw, config.development_replicates)
    if not _has_complete_evidence(
        development, config, config.development_replicates, tuple(config.taus)
    ):
        failures.append("missing development evidence")

    selected = select_tau_pair(raw, config)
    if selected is None:
        failures.append("no eligible development tau pair")
        return GateDecision("REASSESS", None, {}, tuple(failures))

    validation = _partition(raw.loc[raw["status"] == "ok"], config.validation_replicates)
    if not _has_complete_evidence(validation, config, config.validation_replicates, selected):
        failures.append("missing validation evidence")
        metrics: dict[str, object] = {"selected_tau_pair": list(selected)}
        return GateDecision("REASSESS", selected, metrics, tuple(failures))

    target_n = _target_sample_sizes(config)
    cells: list[dict[str, object]] = []
    missing_cell = False
    chain_failed = False
    fork_failed = False
    triangle_failed = False
    for tau in selected:
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
                    value = _validation_metric(validation, motif, n, strength, tau, metric)
                    cells.append(
                        {
                            "tau": tau,
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
        "selected_tau_pair": list(selected),
        "validation_cells": cells,
    }
    return GateDecision(
        "PROCEED" if not failures else "REASSESS", selected, metrics, tuple(failures)
    )


def _plot_dpi_operating_curve(aggregate: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots()
    for motif, metric, label in (
        ("chain", "indirect_prune_tpr", "chain indirect TPR"),
        ("fork", "indirect_prune_tpr", "fork indirect TPR"),
        ("triangle", "true_edge_prune_fpr", "triangle true-edge FPR"),
    ):
        values = aggregate.loc[aggregate["motif"] == motif].groupby("tau", as_index=False)[metric].mean()
        if not values.empty:
            axis.plot(values["tau"], values[metric], marker="o", label=label)
    axis.set_xlabel("Tolerance (tau)")
    axis.set_ylabel("Pruning rate")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_performance_vs_tau(aggregate: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots()
    for (motif, n, strength), values in aggregate.groupby(["motif", "n", "strength"]):
        axis.plot(
            values["tau"], values["perfect_recovery"], marker="o", label=f"{motif}, N={n}, a={strength:g}"
        )
    axis.set_xlabel("Tolerance (tau)")
    axis.set_ylabel("Perfect recovery rate")
    axis.legend(fontsize="xx-small", ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _plot_runtime_vs_n(aggregate: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots()
    for (motif, tau), values in aggregate.groupby(["motif", "tau"]):
        by_n = values.groupby("n", as_index=False)["mean_runtime_seconds"].mean()
        axis.plot(by_n["n"], by_n["mean_runtime_seconds"], marker="o", label=f"{motif}, tau={tau:g}")
    axis.set_xlabel("N")
    axis.set_ylabel("Mean runtime (seconds)")
    axis.legend(fontsize="xx-small", ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage1_report(raw: pd.DataFrame, config: Stage1Config, output_dir: Path) -> GateDecision:
    """Write all aggregate evidence and the frozen R2 decision for one run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage1(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage1_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps(asdict(decision), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    _plot_dpi_operating_curve(aggregate, output_dir / "dpi_operating_curve.png")
    _plot_performance_vs_tau(aggregate, output_dir / "performance_vs_tau.png")
    _plot_runtime_vs_n(aggregate, output_dir / "runtime_vs_n.png")
    selected = "None" if decision.selected_tau_pair is None else ", ".join(map(str, decision.selected_tau_pair))
    failures = "None" if not decision.failures else ", ".join(decision.failures)
    (output_dir / "stage1_report.md").write_text(
        "# Stage 1 DPI Motif Validation Report\n\n"
        f"Decision: **{decision.status}**\n\n"
        f"Selected development tau pair: `{selected}`\n\n"
        f"Failed criteria: {failures}\n\n"
        "See `aggregate_metrics.csv`, `decision.json`, and the generated figures for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
