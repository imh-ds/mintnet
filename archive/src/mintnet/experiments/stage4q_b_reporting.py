"""Evidence rendering for Stage 4q Part B. See docs/stage4q_charter.md.
Reports Stage 4p's own composite overlap TPR alongside the proper
candidacy/conditional-accuracy decomposition (reusing Stage 4h's own
`_overlap_decomposition` unmodified) at every N, so the gap between the
two metrics is visible directly.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage4h_reporting import _overlap_decomposition
from mintnet.experiments.stage4q_b import Stage4qBConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class NComparison:
    n: int
    alpha: float | None
    composite_overlap_tpr: float | None
    candidacy_rate: float | None
    conditional_accuracy: float | None
    gap: float | None  # composite TPR minus conditional_accuracy, when both exist
    status: str


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage4qBConfig) -> NComparison:
    n_raw = raw.loc[raw["n"] == n]
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        alpha = float(n_raw["alpha"].iloc[0]) if not n_raw.empty else None
        return NComparison(n, alpha, None, None, None, None, "error")

    alpha = float(n_raw["alpha"].iloc[0])
    validation = _partition(n_raw, config.validation_replicates)

    composite_tpr = float(validation["overlap_indirect_tpr"].mean())
    candidacy_rate, conditional_accuracy = _overlap_decomposition(validation)
    gap = (composite_tpr - conditional_accuracy) if conditional_accuracy is not None else None

    if conditional_accuracy is None:
        status = "no candidates"
    elif conditional_accuracy >= config.minimum_conditional_accuracy:
        status = "decomposed-metric PROCEED"
    else:
        status = "decomposed-metric REASSESS"

    return NComparison(n, alpha, composite_tpr, candidacy_rate, conditional_accuracy, gap, status)


def evaluate_all(raw: pd.DataFrame, config: Stage4qBConfig) -> list[NComparison]:
    return [evaluate_n(raw, n, config) for n in config.sample_sizes]


def _plot_comparison(comparisons: list[NComparison], path: Path) -> None:
    figure, axis = plt.subplots()
    ns = [c.n for c in comparisons]
    axis.plot(ns, [c.composite_overlap_tpr for c in comparisons], marker="o", label="composite TPR (Stage 4p's own metric)")
    axis.plot(ns, [c.conditional_accuracy for c in comparisons], marker="s", label="conditional accuracy (decomposed)")
    axis.plot(ns, [c.candidacy_rate for c in comparisons], marker="^", linestyle="--", label="candidacy rate (descriptive)")
    axis.axhline(0.80, color="gray", linestyle=":", linewidth=0.8)
    axis.set_xlabel("N")
    axis.set_ylabel("Rate")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4q_b_report(raw: pd.DataFrame, config: Stage4qBConfig, output_dir: Path) -> list[NComparison]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparisons = evaluate_all(raw, config)
    (output_dir / "comparison.json").write_text(
        json.dumps([asdict(c) for c in comparisons], indent=2, allow_nan=True) + "\n", encoding="utf-8"
    )
    _plot_comparison(comparisons, output_dir / "composite_vs_decomposed.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | alpha | composite TPR (Stage 4p) | candidacy rate | conditional accuracy (proper) | "
        "gap (composite - accuracy) | decomposed-metric read |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in comparisons:
        rows.append(
            f"| {c.n} | {fmt(c.alpha)} | {fmt(c.composite_overlap_tpr)} | {fmt(c.candidacy_rate)} | "
            f"{fmt(c.conditional_accuracy)} | {fmt(c.gap)} | {c.status} |"
        )
    table = "\n".join(rows)

    (output_dir / "stage4q_b_report.md").write_text(
        "# Stage 4q Part B: Decomposed Metric for the Sequential Engine on Overlap\n\n"
        "Reproduces Stage 4p's own sequential-engine-on-overlap draws bit-for-bit (same seeds, same "
        "D-012 general alpha), re-scored with Stage 4e's own candidacy/conditional-accuracy "
        "decomposition alongside the original composite TPR, so the non-detection-inflation gap D-032 "
        "warned about is visible directly rather than asserted.\n\n"
        f"{table}\n\n"
        "`composite TPR` is Stage 4p's own reported metric (a pair that never becomes a candidate "
        "defaults to 'pruned'). `candidacy rate` is the fraction of the 4 overlap cross-branch pairs "
        "that actually clear screening. `conditional accuracy` is correctness among candidates only -- "
        "the proper metric. A positive `gap` means the composite metric was overstating performance "
        "relative to the decomposed one.\n\n"
        "See `raw_metrics.csv`, `comparison.json`, `resolved_config.yaml`, and "
        "`composite_vs_decomposed.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return comparisons
