"""Gate evaluation and evidence rendering for the Stage 4e candidacy-
conditional overlap metric experiment. See docs/stage4e_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage1l import INDIRECT_EDGES as OVERLAP_INDIRECT_EDGES
from mintnet.experiments.stage4e import Stage4eConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_PAIR_LABELS = tuple(f"{i}{j}" for i, j in OVERLAP_INDIRECT_EDGES)


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _pooled_metrics(rows: pd.DataFrame, n: int, alpha: float) -> tuple[float, float | None, float] | None:
    """Pooled candidacy rate, conditional accuracy (None if no candidates at
    all), and true-edge FPR -- pooled as sums, not a mean of per-replicate
    ratios, matching D-013's own pooled-fraction convention (necessary here
    since some replicates may have zero cross-branch candidates)."""
    subset = rows.loc[(rows["n"] == n) & (rows["alpha"] == alpha)]
    if subset.empty or not np.isfinite(subset["true_edge_prune_fpr"]).all():
        return None
    total_candidates = 0
    total_correct = 0
    for label in _PAIR_LABELS:
        candidate_column = subset[f"candidate_{label}"]
        correct_column = subset[f"correctly_pruned_{label}"]
        if candidate_column.isna().any():
            return None
        total_candidates += int(candidate_column.sum())
        total_correct += int(correct_column.fillna(False).astype(bool).sum())
    candidacy_rate = total_candidates / (len(_PAIR_LABELS) * len(subset))
    conditional_accuracy = (total_correct / total_candidates) if total_candidates > 0 else None
    true_edge_fpr = float(subset["true_edge_prune_fpr"].mean())
    return candidacy_rate, conditional_accuracy, true_edge_fpr


def select_alpha(raw: pd.DataFrame, n: int, config: Stage4eConfig) -> float | None:
    """Largest development-eligible alpha, matching Stage 4b/4d's own tiebreak."""
    if raw.empty or not raw["status"].eq("ok").all():
        return None
    development = _partition(raw, config.development_replicates)
    eligible: list[float] = []
    for alpha in config.alphas:
        metrics = _pooled_metrics(development, n, alpha)
        if metrics is None:
            continue
        _candidacy, accuracy, fpr = metrics
        if accuracy is None:
            continue
        accuracy_margin = accuracy - config.minimum_conditional_accuracy
        fpr_margin = config.maximum_true_edge_prune_fpr - fpr
        if accuracy_margin >= config.required_margin and fpr_margin >= config.required_margin:
            eligible.append(alpha)
    return max(eligible) if eligible else None


@dataclass(frozen=True)
class NDecision:
    n: int
    status: str
    selected_alpha: float | None
    candidacy_rate: float | None
    conditional_accuracy: float | None
    true_edge_prune_fpr: float | None
    margin: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage4eConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        return NDecision(n, "REASSESS", None, None, None, None, None, tuple(failures))

    selected = select_alpha(raw, n, config)
    if selected is None:
        failures.append("no eligible development alpha")
        return NDecision(n, "REASSESS", None, None, None, None, None, tuple(failures))

    validation = _partition(n_raw, config.validation_replicates)
    metrics = _pooled_metrics(validation, n, selected)
    if metrics is None:
        failures.append("missing validation evidence")
        return NDecision(n, "REASSESS", selected, None, None, None, None, tuple(failures))

    candidacy_rate, accuracy, fpr = metrics
    if accuracy is None:
        failures.append("no cross-branch candidates on validation")
        return NDecision(n, "REASSESS", selected, candidacy_rate, None, fpr, None, tuple(failures))

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
    return NDecision(n, status, selected, candidacy_rate, accuracy, fpr, margin, tuple(failures))


def evaluate_stage4e_gate(raw: pd.DataFrame, config: Stage4eConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _plot_metrics_vs_n(decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    cells = sorted(decision.by_n, key=lambda d: d.n)
    ns = [d.n for d in cells]
    axis.plot(ns, [d.conditional_accuracy for d in cells], marker="o", label="conditional accuracy (corrected)")
    axis.plot(ns, [d.candidacy_rate for d in cells], marker="s", linestyle="--", label="candidacy rate (descriptive)")
    axis.axhline(0.80, color="gray", linestyle=":", linewidth=0.8, label="accuracy gate (.80)")
    axis.set_xlabel("N")
    axis.set_ylabel("Rate")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4e_report(raw: pd.DataFrame, config: Stage4eConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4e_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    _plot_metrics_vs_n(decision, output_dir / "candidacy_vs_accuracy_by_n.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | status | alpha | candidacy rate | conditional accuracy | true-edge FPR | margin | failures |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in sorted(decision.by_n, key=lambda c: c.n):
        alpha = "None" if d.selected_alpha is None else f"{d.selected_alpha:.4f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {alpha} | {fmt(d.candidacy_rate)} | {fmt(d.conditional_accuracy)} | "
            f"{fmt(d.true_edge_prune_fpr)} | {fmt(d.margin)} | {failures} |"
        )
    table = "\n".join(rows)

    accuracy_direction = sorted(decision.by_n, key=lambda d: d.n)
    increasing = all(
        a.conditional_accuracy is None
        or b.conditional_accuracy is None
        or a.conditional_accuracy <= b.conditional_accuracy + 1e-9
        for a, b in zip(accuracy_direction, accuracy_direction[1:])
    )
    prediction_note = (
        "Predeclared expectation HELD: conditional accuracy is non-decreasing in N "
        "(the normal direction), consistent with D-032's diagnosis that Stage 4d's "
        "apparent low-N improvement was a non-detection artifact."
        if increasing
        else "Predeclared expectation DID NOT HOLD: conditional accuracy still rises as N falls "
        "even after removing the non-detection confound -- the D-032 artifact explanation was "
        "incomplete and needs further diagnosis."
    )

    (output_dir / "stage4e_report.md").write_text(
        "# Stage 4e Candidacy-Conditional Overlap Metric Report\n\n"
        f"{table}\n\n"
        f"{prediction_note}\n\n"
        "`candidacy rate` (descriptive, not gated) is the fraction of the 4 cross-branch pairs "
        "that even cleared initial screening. `conditional accuracy` (gated) is pruning accuracy "
        "measured only among candidate pairs -- report both together; `conditional accuracy` "
        "alone would understate how often the mechanism never gets a chance to run at low N.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and `candidacy_vs_accuracy_by_n.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
