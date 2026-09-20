"""Gate evaluation and evidence rendering for the Stage 4k shape/signal-
strength sweep (sequential engine). See docs/stage4k_charter.md.

Full-grid reporting requirement (mirrors Stage 4j's own partial-success
requirement): every cell's individual status is reported regardless of
the overall outcome, organized per motif so any pattern -- failures
concentrated by strength, by N, or by motif -- is visible directly.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage4k import MOTIFS, Stage4kConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class CellDecision:
    motif: str
    strength: float
    n: int
    alpha: float
    status: str
    candidacy_rate: float | None
    conditional_accuracy: float | None
    true_edge_prune_fpr: float | None
    margin: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    overall_status: str
    by_cell: tuple[CellDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _pooled_metrics(rows: pd.DataFrame) -> tuple[float, float | None, float] | None:
    """Pooled candidacy rate, conditional accuracy (None if zero
    candidates), and true-edge FPR -- pooled as sums, matching D-013's
    own pooled-fraction convention."""
    if rows.empty or not np.isfinite(rows["true_edge_prune_fpr"]).all():
        return None
    candidates = rows["candidate"].astype(bool)
    total_candidates = int(candidates.sum())
    total_correct = int(rows["correctly_pruned"].fillna(False).astype(bool).sum())
    candidacy_rate = total_candidates / len(rows)
    conditional_accuracy = (total_correct / total_candidates) if total_candidates > 0 else None
    true_edge_fpr = float(rows["true_edge_prune_fpr"].mean())
    return candidacy_rate, conditional_accuracy, true_edge_fpr


def evaluate_cell(raw: pd.DataFrame, motif: str, strength: float, n: int, config: Stage4kConfig) -> CellDecision:
    cell_raw = raw.loc[(raw["motif"] == motif) & (raw["strength"] == strength) & (raw["n"] == n)]
    failures: list[str] = []
    if cell_raw.empty:
        return CellDecision(motif, strength, n, float("nan"), "REASSESS", None, None, None, None, ("no evidence for this cell",))

    alpha = float(cell_raw["alpha"].iloc[0])
    if not cell_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        return CellDecision(motif, strength, n, alpha, "REASSESS", None, None, None, None, tuple(failures))

    validation = _partition(cell_raw, config.validation_replicates)
    metrics = _pooled_metrics(validation)
    if metrics is None:
        failures.append("missing validation evidence")
        return CellDecision(motif, strength, n, alpha, "REASSESS", None, None, None, None, tuple(failures))

    candidacy_rate, accuracy, fpr = metrics
    if accuracy is None:
        failures.append("no candidates on validation")
        return CellDecision(motif, strength, n, alpha, "REASSESS", candidacy_rate, None, fpr, None, tuple(failures))

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
    return CellDecision(motif, strength, n, alpha, status, candidacy_rate, accuracy, fpr, margin, tuple(failures))


def evaluate_stage4k_gate(raw: pd.DataFrame, config: Stage4kConfig) -> GateDecision:
    by_cell = tuple(
        evaluate_cell(raw, motif, strength, n, config)
        for motif in MOTIFS
        for strength in config.strengths
        for n in config.sample_sizes
    )
    overall_status = "PROCEED" if all(cell.status == "PROCEED" for cell in by_cell) else "REASSESS"
    return GateDecision(overall_status, by_cell)


def _plot_strength_curves(decision: GateDecision, sample_sizes: tuple[int, ...], path: Path) -> None:
    figure, axes = plt.subplots(1, len(MOTIFS), figsize=(5 * len(MOTIFS), 4), sharey=True)
    if len(MOTIFS) == 1:
        axes = [axes]
    for axis, motif in zip(axes, MOTIFS):
        for n in sample_sizes:
            cells = sorted(
                (c for c in decision.by_cell if c.motif == motif and c.n == n), key=lambda c: c.strength
            )
            strengths = [c.strength for c in cells]
            accuracy = [c.conditional_accuracy if c.conditional_accuracy is not None else np.nan for c in cells]
            axis.plot(strengths, accuracy, marker="o", label=f"N={n} accuracy")
            candidacy = [c.candidacy_rate if c.candidacy_rate is not None else np.nan for c in cells]
            axis.plot(strengths, candidacy, marker="x", linestyle="--", label=f"N={n} candidacy")
        axis.axhline(0.80, color="black", linewidth=0.75, linestyle=":")
        axis.set_title(motif)
        axis.set_xlabel("strength")
    axes[0].set_ylabel("rate")
    axes[-1].legend(fontsize="small", loc="lower right")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4k_report(raw: pd.DataFrame, config: Stage4kConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4k_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps(
            {"overall_status": decision.overall_status, "by_cell": [asdict(c) for c in decision.by_cell]},
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_strength_curves(decision, config.sample_sizes, output_dir / "strength_sweep.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = [f"# Stage 4k Shape/Signal-Strength Sweep Report (Sequential Engine)\n",
                f"Overall gate: **{decision.overall_status}**\n"]
    failing = [c for c in decision.by_cell if c.status != "PROCEED"]
    if failing:
        by_strength: dict[float, int] = {}
        by_n: dict[int, int] = {}
        by_motif: dict[str, int] = {}
        for c in failing:
            by_strength[c.strength] = by_strength.get(c.strength, 0) + 1
            by_n[c.n] = by_n.get(c.n, 0) + 1
            by_motif[c.motif] = by_motif.get(c.motif, 0) + 1
        sections.append(
            f"**{len(failing)} of {len(decision.by_cell)} cells failed.** By strength: "
            f"{dict(sorted(by_strength.items()))}. By N: {dict(sorted(by_n.items()))}. "
            f"By motif: {by_motif}.\n"
        )
    else:
        sections.append(f"All {len(decision.by_cell)} cells PROCEED.\n")

    for motif in MOTIFS:
        rows = [
            "| strength | N | alpha | status | candidacy rate | conditional accuracy | true-edge FPR | margin | failures |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        cells = sorted(
            (c for c in decision.by_cell if c.motif == motif), key=lambda c: (c.strength, c.n)
        )
        for c in cells:
            failures = "None" if not c.failures else ", ".join(c.failures)
            rows.append(
                f"| {c.strength:g} | {c.n} | {c.alpha:.4f} | {c.status} | {fmt(c.candidacy_rate)} | "
                f"{fmt(c.conditional_accuracy)} | {fmt(c.true_edge_prune_fpr)} | {fmt(c.margin)} | {failures} |"
            )
        sections.append(f"## Motif: {motif}\n\n" + "\n".join(rows) + "\n")

    sections.append(
        "See `raw_metrics.csv`, `decision.json`, `d012_formula.json`, `resolved_config.yaml`, "
        "and `strength_sweep.png` for complete evidence.\n"
    )
    (output_dir / "stage4k_report.md").write_text("\n".join(sections), encoding="utf-8")
    return decision
