"""Evidence rendering for the Stage 4f diagnostic charter (candidacy-
accuracy anomaly). See docs/stage4f_charter.md. No gate -- descriptive
only, reporting the answers to the charter's two predeclared
sub-questions plainly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage4f import Stage4fConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class CellSummary:
    n: int
    alpha: float
    candidates: int
    q1_correlation: float | None
    q2_mean_abs_r_partial: float | None
    fraction_correctly_pruned: float | None


def summarize_cell(raw: pd.DataFrame, n: int, alpha: float) -> CellSummary:
    subset = raw.loc[(raw["n"] == n) & (raw["alpha"] == alpha) & (raw["status"] == "ok")]
    candidates = subset.loc[subset["candidate"] == True]  # noqa: E712
    if candidates.empty:
        return CellSummary(n, alpha, 0, None, None, None)

    abs_marginal = candidates["r_marginal"].abs()
    abs_partial = candidates["r_partial"].abs()
    q1 = float(np.corrcoef(abs_marginal, abs_partial)[0, 1]) if len(candidates) > 1 else None
    q2 = float(abs_partial.mean())
    fraction_correct = float(candidates["correctly_pruned"].mean())
    return CellSummary(n, alpha, len(candidates), q1, q2, fraction_correct)


def summarize_all(raw: pd.DataFrame, config: Stage4fConfig) -> list[CellSummary]:
    return [summarize_cell(raw, n, alpha) for n in config.sample_sizes for alpha in config.alphas]


def _plot_marginal_vs_partial(raw: pd.DataFrame, config: Stage4fConfig, path: Path) -> None:
    figure, axes = plt.subplots(1, len(config.alphas), figsize=(5 * len(config.alphas), 4), squeeze=False)
    colors = plt.cm.viridis(np.linspace(0, 1, len(config.sample_sizes)))
    for col, alpha in enumerate(config.alphas):
        axis = axes[0][col]
        for n, color in zip(config.sample_sizes, colors):
            subset = raw.loc[
                (raw["n"] == n) & (raw["alpha"] == alpha) & (raw["status"] == "ok") & (raw["candidate"] == True)  # noqa: E712
            ]
            axis.scatter(subset["r_marginal"].abs(), subset["r_partial"].abs(), s=6, alpha=0.3, color=color, label=f"N={n}")
        axis.set_title(f"alpha={alpha:g}")
        axis.set_xlabel("|r_marginal|")
        axis.set_ylabel("|r_partial|")
        axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4f_report(raw: pd.DataFrame, config: Stage4fConfig, output_dir: Path) -> list[CellSummary]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = summarize_all(raw, config)
    (output_dir / "summary.json").write_text(
        __import__("json").dumps([asdict(s) for s in summaries], indent=2) + "\n", encoding="utf-8"
    )
    _plot_marginal_vs_partial(raw, config, output_dir / "marginal_vs_partial.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | alpha | candidates | Q1: corr(|r_marginal|,|r_partial|) | Q2: mean |r_partial| | fraction correctly pruned |",
        "|---|---|---|---|---|---|",
    ]
    for s in summaries:
        rows.append(
            f"| {s.n} | {s.alpha} | {s.candidates} | {fmt(s.q1_correlation)} | "
            f"{fmt(s.q2_mean_abs_r_partial)} | {fmt(s.fraction_correctly_pruned)} |"
        )
    table = "\n".join(rows)

    # Descriptive read of the two predeclared sub-questions, per alpha, across N.
    reads: list[str] = []
    for alpha in config.alphas:
        cells = sorted((s for s in summaries if s.alpha == alpha and s.q2_mean_abs_r_partial is not None), key=lambda s: s.n)
        if len(cells) < 2:
            reads.append(f"alpha={alpha:g}: insufficient data across N to compare.")
            continue
        q1_values = [c.q1_correlation for c in cells if c.q1_correlation is not None]
        q1_read = (
            f"Q1 correlation ranges {min(q1_values):.3f} to {max(q1_values):.3f} across N"
            if q1_values
            else "Q1 undefined (too few candidates)"
        )
        q2_low, q2_high = cells[0].q2_mean_abs_r_partial, cells[-1].q2_mean_abs_r_partial
        q2_direction = "smaller" if q2_low < q2_high else ("larger" if q2_low > q2_high else "the same")
        reads.append(
            f"alpha={alpha:g}: {q1_read}. Mean |r_partial| among candidates is {q2_direction} at "
            f"N={cells[0].n} ({q2_low:.4f}) than at N={cells[-1].n} ({q2_high:.4f})."
        )
    reads_text = "\n".join(f"- {r}" for r in reads)

    (output_dir / "stage4f_report.md").write_text(
        "# Stage 4f Candidacy-Accuracy Anomaly Diagnostic Report\n\n"
        f"{table}\n\n"
        "## Predeclared sub-question readings\n\n"
        f"{reads_text}\n\n"
        "Q1: a weak, N-stable correlation supports D-033's \"marginal detection is a fluke unrelated "
        "to the conditional outcome\" framing; a strong correlation instead points to shared "
        "sample-noise driving both estimates together. Q2: similar mean |r_partial| across N supports "
        "the fluke framing; a systematically smaller value at low N means the low-N candidate pool is "
        "genuinely easier, not merely differently selected. See docs/stage4f_charter.md for the full "
        "predeclared interpretation of each reading -- this report states the numbers, not a verdict.\n\n"
        "See `raw_metrics.csv`, `summary.json`, and `marginal_vs_partial.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return summaries
