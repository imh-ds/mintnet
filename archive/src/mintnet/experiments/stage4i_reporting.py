"""Held-out gate evaluation and evidence rendering for the Stage 4i
experiment (alpha(N) repair, sequential engine, overlap shape). See
docs/stage4i_charter.md.

Reuses Stage 4e's pooled-metric computation
(`mintnet.experiments.stage4e_reporting._pooled_metrics`) unmodified,
adding one gated criterion Stage 4g's own gate lacked: the predicted
`alpha_hat` itself must be a valid probability at every held-out N,
including N=750 -- the specific check D-037 found missing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage1j_fit import FittedForm
from mintnet.experiments.stage4e_reporting import _pooled_metrics
from mintnet.experiments.stage4i import Stage4iConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class NDecision:
    n: int
    alpha_hat: float
    status: str
    candidacy_rate: float | None
    conditional_accuracy: float | None
    true_edge_prune_fpr: float | None
    margin: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    selected_form: str
    form_r_squared: float
    fitting_points: tuple[tuple[float, float], ...]
    fitting_point_self_check: tuple[dict[str, object], ...]
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage4iConfig) -> NDecision:
    """Test the single refit-predicted alpha at one held-out N against
    validation replicates. An invalid (out-of-(0,1)) alpha_hat is an
    automatic, explicitly-reported failure rather than a silent error --
    the exact repair this charter exists to make over Stage 4g's gate."""
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty:
        return NDecision(n, float("nan"), "REASSESS", None, None, None, None, ("no evidence for this N",))

    alpha_hat = float(n_raw["alpha"].iloc[0])
    if not (0.0 < alpha_hat < 1.0):
        failures.append(f"alpha_hat {alpha_hat:.6f} is not a valid probability in (0, 1)")
        return NDecision(n, alpha_hat, "REASSESS", None, None, None, None, tuple(failures))

    if not n_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        return NDecision(n, alpha_hat, "REASSESS", None, None, None, None, tuple(failures))

    validation = _partition(n_raw, config.validation_replicates)
    metrics = _pooled_metrics(validation, n, alpha_hat)
    if metrics is None:
        failures.append("missing validation evidence")
        return NDecision(n, alpha_hat, "REASSESS", None, None, None, None, tuple(failures))

    candidacy_rate, accuracy, fpr = metrics
    if accuracy is None:
        failures.append("no cross-branch candidates on validation")
        return NDecision(n, alpha_hat, "REASSESS", candidacy_rate, None, fpr, None, tuple(failures))

    accuracy_margin = accuracy - config.minimum_conditional_accuracy
    fpr_margin = config.maximum_true_edge_prune_fpr - fpr
    margin = min(accuracy_margin, fpr_margin)

    if accuracy < config.minimum_conditional_accuracy:
        failures.append(f"conditional accuracy {accuracy:.4f} below required {config.minimum_conditional_accuracy:.4f}")
    if fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if margin < config.required_margin:
        failures.append(f"margin {margin:.4f} below required {config.required_margin:.4f}")

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(n, alpha_hat, status, candidacy_rate, accuracy, fpr, margin, tuple(failures))


def evaluate_stage4i_gate(
    raw: pd.DataFrame,
    config: Stage4iConfig,
    fitting_points: tuple[tuple[float, float], ...],
    self_check: tuple[dict[str, object], ...],
    selected: FittedForm,
) -> GateDecision:
    by_n = tuple(evaluate_n(raw, n, config) for n in config.sample_sizes)
    return GateDecision(selected.name, selected.r_squared, fitting_points, self_check, by_n)


def _plot_fit(
    fitting_points: tuple[tuple[float, float], ...], selected: FittedForm, decision: GateDecision, path: Path
) -> None:
    figure, axis = plt.subplots()
    fit_n = [p[0] for p in fitting_points]
    fit_alpha = [p[1] for p in fitting_points]
    axis.scatter(fit_n, fit_alpha, color="tab:blue", label="fitting points (Stage 4e, 750 excluded)", zorder=3)

    curve_n = np.linspace(min(fit_n) * 0.9, max(fit_n) * 1.1, 200)
    curve_alpha = [selected.predict(float(n)) for n in curve_n]
    axis.plot(curve_n, curve_alpha, color="tab:gray", linestyle="--", label=f"{selected.name} refit")
    axis.axhline(0.0, color="black", linewidth=0.75, linestyle=":")

    held_out_n = [d.n for d in decision.by_n]
    held_out_alpha = [d.alpha_hat for d in decision.by_n]
    colors = ["tab:green" if d.status == "PROCEED" else "tab:red" for d in decision.by_n]
    axis.scatter(held_out_n, held_out_alpha, c=colors, marker="x", s=80, label="held-out incl. N=750 (color = outcome)", zorder=4)

    axis.set_xlabel("N")
    axis.set_ylabel("alpha")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4i_report(
    raw: pd.DataFrame,
    config: Stage4iConfig,
    fitting_points: tuple[tuple[float, float], ...],
    self_check: tuple[dict[str, object], ...],
    selected: FittedForm,
    output_dir: Path,
) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4i_gate(raw, config, fitting_points, self_check, selected)
    (output_dir / "decision.json").write_text(
        json.dumps(
            {
                "selected_form": decision.selected_form,
                "form_r_squared": decision.form_r_squared,
                "fitting_points": [{"n": n, "alpha_star": a} for n, a in decision.fitting_points],
                "fitting_point_self_check": list(decision.fitting_point_self_check),
                "by_n": [asdict(d) for d in decision.by_n],
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_fit(fitting_points, selected, decision, output_dir / "alpha_n_fit.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    self_check_rows = "\n".join(
        f"| {c['n']:g} | {c['alpha_star']:g} | {c['alpha_hat']:.4f} | {'pass' if c['valid'] else 'FAIL'} |"
        for c in self_check
    )
    self_check_failed = any(not c["valid"] for c in self_check)

    rows = [
        "| N | alpha_hat | status | candidacy rate | conditional accuracy | true-edge FPR | margin | failures |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.alpha_hat:.4f} | {d.status} | {fmt(d.candidacy_rate)} | "
            f"{fmt(d.conditional_accuracy)} | {fmt(d.true_edge_prune_fpr)} | {fmt(d.margin)} | {failures} |"
        )
    table = "\n".join(rows)
    overall = "PROCEED" if (not self_check_failed and all(d.status == "PROCEED" for d in decision.by_n)) else "REASSESS"
    (output_dir / "stage4i_report.md").write_text(
        "# Stage 4i alpha(N) Repair Report (Sequential Engine, Overlap, N=750 Boundary Fix)\n\n"
        f"Overall gate: **{overall}**\n\n"
        f"Selected form: **{decision.selected_form}** (R^2 = {decision.form_r_squared:.4f}), "
        "fit on five points with N=750 removed from the fitting set.\n\n"
        "## Fitting-point self-check (new in this charter)\n\n"
        "Confirms the refit formula returns a valid probability at every one of its own "
        "fitting N -- the exact check D-037 found missing from Stage 4g, which let a negative "
        "alpha at N=750 (a fitting point) go unnoticed.\n\n"
        "| N | alpha_star (fit target) | alpha_hat (refit prediction) | self-check |\n|---|---|---|---|\n"
        f"{self_check_rows}\n\n"
        "## Held-out validation (all six N freshly simulated under the refit formula)\n\n"
        f"{table}\n\n"
        "See `raw_metrics.csv`, `decision.json`, `fitting_points.json`, `resolved_config.yaml`, "
        "and `alpha_n_fit.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
