"""Held-out gate evaluation and evidence rendering for the Stage 1j experiment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage1j import Stage1jConfig
from mintnet.experiments.stage1j_fit import FITTING_POINTS, FittedForm

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class NDecision:
    """The immutable R2j decision for a single held-out sample size."""

    n: int
    alpha_hat: float
    status: str
    margin: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    """The immutable R2j decision: one status per held-out sample size."""

    selected_form: str
    form_r_squared: float
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _metric(rows: pd.DataFrame, motif: str, n: int, strength: float, metric: str) -> float | None:
    values = rows.loc[(rows["motif"] == motif) & (rows["n"] == n) & (rows["strength"] == strength), metric]
    if values.empty or not np.isfinite(values).all():
        return None
    return float(values.mean())


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage1jConfig) -> NDecision:
    """Test the single formula-predicted alpha at one held-out N against validation replicates."""
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator, DGP, or Cholesky errors")
        return NDecision(n, float(n_raw["alpha"].iloc[0]) if not n_raw.empty else float("nan"), "REASSESS", None, tuple(failures))

    alpha_hat = float(n_raw["alpha"].iloc[0])
    validation = _partition(n_raw, config.validation_replicates)

    margins: list[float] = []
    missing_cell = False
    for strength in config.strengths:
        chain_tpr = _metric(validation, "chain", n, strength, "indirect_prune_tpr")
        fork_tpr = _metric(validation, "fork", n, strength, "indirect_prune_tpr")
        triangle_fpr = _metric(validation, "triangle", n, strength, "true_edge_prune_fpr")
        if chain_tpr is None or fork_tpr is None or triangle_fpr is None:
            missing_cell = True
            continue
        margins.append(chain_tpr - config.minimum_indirect_prune_tpr)
        margins.append(fork_tpr - config.minimum_indirect_prune_tpr)
        margins.append(config.maximum_triangle_true_edge_prune_fpr - triangle_fpr)

    if missing_cell:
        failures.append("missing validation cell")
        return NDecision(n, alpha_hat, "REASSESS", None, tuple(failures))

    margin = min(margins)
    if margin < config.required_margin:
        failures.append(
            f"margin {margin:.4f} below required {config.required_margin:.4f}"
        )
    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(n, alpha_hat, status, margin, tuple(failures))


def evaluate_stage1j_gate(raw: pd.DataFrame, config: Stage1jConfig, selected: FittedForm) -> GateDecision:
    """Evaluate every held-out sample size independently against the required margin."""
    by_n = tuple(evaluate_n(raw, n, config) for n in config.sample_sizes)
    return GateDecision(selected.name, selected.r_squared, by_n)


def _plot_fit(selected: FittedForm, decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    fit_n = [p[0] for p in FITTING_POINTS]
    fit_alpha = [p[1] for p in FITTING_POINTS]
    axis.scatter(fit_n, fit_alpha, color="tab:blue", label="fitting points", zorder=3)

    curve_n = np.linspace(min(fit_n) * 0.9, max(fit_n) * 1.05, 200)
    curve_alpha = [selected.predict(float(n)) for n in curve_n]
    axis.plot(curve_n, curve_alpha, color="tab:gray", linestyle="--", label=f"{selected.name} fit")

    held_out_n = [d.n for d in decision.by_n]
    held_out_alpha = [d.alpha_hat for d in decision.by_n]
    colors = ["tab:green" if d.status == "PROCEED" else "tab:red" for d in decision.by_n]
    axis.scatter(held_out_n, held_out_alpha, c=colors, marker="x", s=80, label="held-out (color = outcome)", zorder=4)

    axis.set_xlabel("N")
    axis.set_ylabel("alpha")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage1j_report(
    raw: pd.DataFrame, config: Stage1jConfig, selected: FittedForm, output_dir: Path
) -> GateDecision:
    """Write all aggregate evidence and the frozen R2j held-out decision table."""
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage1j_gate(raw, config, selected)
    (output_dir / "decision.json").write_text(
        json.dumps(
            {
                "selected_form": decision.selected_form,
                "form_r_squared": decision.form_r_squared,
                "by_n": [asdict(d) for d in decision.by_n],
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_fit(selected, decision, output_dir / "alpha_n_fit.png")

    rows = ["| N | alpha_hat | status | margin | failures |", "|---|---|---|---|---|"]
    for d in decision.by_n:
        margin = "None" if d.margin is None else f"{d.margin:.4f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(f"| {d.n} | {d.alpha_hat:.4f} | {d.status} | {margin} | {failures} |")
    table = "\n".join(rows)
    (output_dir / "stage1j_report.md").write_text(
        "# Stage 1j alpha(N) Fitting and Held-Out Validation Report\n\n"
        f"Selected form: **{decision.selected_form}** (R^2 = {decision.form_r_squared:.4f})\n\n"
        f"{table}\n\n"
        "See `raw_metrics.csv`, `decision.json`, `resolved_config.yaml`, "
        "and `alpha_n_fit.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
