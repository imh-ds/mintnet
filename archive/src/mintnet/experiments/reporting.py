"""Aggregation, predeclared gate evaluation, and evidence rendering for Stage 0."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from mintnet.experiments.stage0 import Stage0Config

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class GateDecision:
    status: str
    selected_k: int | None
    metrics: dict[str, object]
    failures: tuple[str, ...]


def aggregate_stage0(raw: pd.DataFrame) -> pd.DataFrame:
    """Summarize estimator behavior per Gaussian condition."""
    successful = raw.loc[raw["status"] == "ok"].copy()
    successful["error"] = successful["estimated_mi"] - successful["true_mi"]
    return (
        successful.groupby(["n", "rho", "k"], as_index=False)
        .agg(
            true_mi=("true_mi", "first"),
            mean_mi=("estimated_mi", "mean"),
            bias=("error", "mean"),
            absolute_bias=("error", lambda values: abs(values.mean())),
            rmse=("error", lambda values: float(np.sqrt(np.mean(np.square(values))))),
            standard_deviation=("estimated_mi", "std"),
            q95=("estimated_mi", lambda values: values.quantile(0.95)),
            negative_estimate_frequency=("estimated_mi", lambda values: (values < 0).mean()),
            mean_runtime_seconds=("elapsed_seconds", "mean"),
        )
        .sort_values(["n", "rho", "k"])
    )


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def evaluate_stage0_gate(raw: pd.DataFrame, config: Stage0Config) -> GateDecision:
    """Apply the frozen development selection and validation-only decision gate."""
    failures: list[str] = []
    if not raw["status"].eq("ok").all():
        failures.append("estimator errors")

    development = _partition(raw.loc[raw["status"] == "ok"], config.development_replicates)
    development = development.loc[
        development["n"].isin(config.moderate_sample_sizes)
        & development["rho"].isin(config.moderate_rhos)
    ].copy()
    development["squared_error"] = np.square(development["estimated_mi"] - development["true_mi"])
    rmse_by_k = development.groupby("k")["squared_error"].mean().pow(0.5)
    selected_k = int(rmse_by_k.sort_values(kind="stable").index[0]) if not rmse_by_k.empty else None
    if selected_k is None:
        failures.append("no valid development estimates")
        return GateDecision("REASSESS", None, {}, tuple(failures))

    validation = _partition(raw.loc[(raw["status"] == "ok") & (raw["k"] == selected_k)], config.validation_replicates).copy()
    validation["error"] = validation["estimated_mi"] - validation["true_mi"]
    moderate = validation.loc[
        validation["n"].isin(config.moderate_sample_sizes)
        & validation["rho"].isin(config.moderate_rhos)
    ]
    moderate_metrics = moderate.groupby(["n", "rho"], as_index=False).agg(
        absolute_bias=("error", lambda values: abs(values.mean())),
        rmse=("error", lambda values: float(np.sqrt(np.mean(np.square(values))))),
    )
    if moderate_metrics.empty or (moderate_metrics["absolute_bias"] > config.max_absolute_bias).any():
        failures.append("moderate-signal absolute bias")
    if moderate_metrics.empty or (moderate_metrics["rmse"] > config.max_rmse).any():
        failures.append("moderate-signal RMSE")

    ranked = validation.groupby("rho", as_index=False).agg(
        true_mi=("true_mi", "first"), mean_mi=("estimated_mi", "mean")
    )
    rank_spearman = float(spearmanr(ranked["true_mi"], ranked["mean_mi"]).statistic)
    if not np.isfinite(rank_spearman) or rank_spearman < config.min_rank_spearman:
        failures.append("strength-ranking Spearman correlation")

    null_values = validation.loc[validation["rho"] == 0.0, "estimated_mi"]
    null_q95 = float(null_values.quantile(0.95)) if not null_values.empty else float("nan")
    if not np.isfinite(null_q95) or null_q95 > config.max_null_q95:
        failures.append("null 95th percentile")

    metrics: dict[str, object] = {
        "development_rmse_by_k": {str(k): float(value) for k, value in rmse_by_k.items()},
        "moderate_cells": moderate_metrics.to_dict(orient="records"),
        "rank_spearman": rank_spearman,
        "null_q95": null_q95,
    }
    return GateDecision("PROCEED" if not failures else "REASSESS", selected_k, metrics, tuple(failures))


def _plot_metric(aggregate: pd.DataFrame, metric: str, path: Path, ylabel: str) -> None:
    figure, axis = plt.subplots()
    for (rho, k), values in aggregate.groupby(["rho", "k"]):
        axis.plot(values["n"], values[metric], marker="o", label=f"rho={rho:g}, k={k}")
    axis.set_xlabel("N")
    axis.set_ylabel(ylabel)
    axis.legend(fontsize="x-small", ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage0_report(raw: pd.DataFrame, config: Stage0Config, output_dir: Path) -> GateDecision:
    """Write aggregate tables, figures, a machine-readable decision, and Markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage0(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage0_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps(asdict(decision), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    _plot_metric(aggregate, "bias", output_dir / "bias_vs_n.png", "Bias (nats)")
    _plot_metric(aggregate, "rmse", output_dir / "rmse_vs_n.png", "RMSE (nats)")
    _plot_metric(aggregate, "mean_runtime_seconds", output_dir / "runtime_vs_n.png", "Mean runtime (seconds)")
    failures = "None" if not decision.failures else ", ".join(decision.failures)
    report = (
        "# Stage 0.1 Gaussian MI Report\n\n"
        f"Decision: **{decision.status}**\n\n"
        f"Selected k: `{decision.selected_k}`\n\n"
        f"Failed criteria: {failures}\n\n"
        "See `aggregate_metrics.csv`, `decision.json`, and the generated figures for complete evidence.\n"
    )
    (output_dir / "stage0_report.md").write_text(report, encoding="utf-8")
    return decision
