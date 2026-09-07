"""Evidence rendering for the Stage 4c cascading-error stress test. See
docs/stage4c_charter.md. Descriptive only -- no gate; reports the three
predeclared sub-questions plainly.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage4c import Stage4cConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class CellSummary:
    n: int
    alpha: float
    noise_count: int
    sequential_wrong_prune_rate: float | None
    conservative_wrong_prune_rate: float | None
    conservative_clique_intact_rate: float | None


def summarize_cell(raw: pd.DataFrame, n: int, alpha: float, noise_count: int) -> CellSummary:
    subset = raw.loc[
        (raw["n"] == n) & (raw["alpha"] == alpha) & (raw["noise_count"] == noise_count) & (raw["status"] == "ok")
    ]
    if subset.empty:
        return CellSummary(n, alpha, noise_count, None, None, None)
    seq_wrong = float((~subset["sequential_retained"].astype(bool)).mean())
    cons_wrong = float((~subset["conservative_retained"].astype(bool)).mean())
    clique_intact = float(subset["conservative_component_is_validated_clique"].astype(bool).mean())
    return CellSummary(n, alpha, noise_count, seq_wrong, cons_wrong, clique_intact)


def summarize_all(raw: pd.DataFrame, config: Stage4cConfig) -> list[CellSummary]:
    return [
        summarize_cell(raw, n, alpha, noise_count)
        for n in config.sample_sizes
        for alpha in config.alphas
        for noise_count in config.noise_counts
    ]


def q3_noise_implication_rate(raw: pd.DataFrame, n: int, alpha: float, noise_count: int) -> float | None:
    """Among replicates where the sequential engine wrongly prunes the weak
    edge under noise contamination, the fraction where a noise column
    (index >= 3) was among the tested neighbors -- the direct mechanistic
    check for the cascading pathway."""
    if noise_count == 0:
        return None
    subset = raw.loc[
        (raw["n"] == n) & (raw["alpha"] == alpha) & (raw["noise_count"] == noise_count) & (raw["status"] == "ok")
    ]
    wrong = subset.loc[~subset["sequential_retained"].astype(bool)]
    if wrong.empty:
        return None
    return float(wrong["sequential_noise_neighbor_used"].astype(bool).mean())


def _plot_wrong_prune_rates(summaries: list[CellSummary], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for axis, engine_key, title in (
        (axes[0], "sequential_wrong_prune_rate", "Sequential engine"),
        (axes[1], "conservative_wrong_prune_rate", "Conservative engine"),
    ):
        for noise_count, marker in ((0, "o"), (5, "s")):
            cells = sorted(
                (s for s in summaries if s.noise_count == noise_count and getattr(s, engine_key) is not None),
                key=lambda s: (s.alpha, s.n),
            )
            by_alpha: dict[float, list[CellSummary]] = {}
            for c in cells:
                by_alpha.setdefault(c.alpha, []).append(c)
            for alpha, group in by_alpha.items():
                axis.plot(
                    [c.n for c in group], [getattr(c, engine_key) for c in group],
                    marker=marker, label=f"noise={noise_count}, alpha={alpha:g}",
                )
        axis.set_title(title)
        axis.set_xlabel("N")
        axis.legend(fontsize="x-small")
    axes[0].set_ylabel("Weak-edge (1,2) wrong-prune rate")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4c_report(raw: pd.DataFrame, config: Stage4cConfig, output_dir: Path) -> list[CellSummary]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = summarize_all(raw, config)
    (output_dir / "summary.json").write_text(json.dumps([asdict(s) for s in summaries], indent=2) + "\n", encoding="utf-8")
    _plot_wrong_prune_rates(summaries, output_dir / "wrong_prune_rate_by_engine.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | alpha | noise_count | sequential wrong-prune rate | conservative wrong-prune rate | "
        "conservative clique-intact rate | Q3: noise implicated (when seq. wrong) |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        q3 = q3_noise_implication_rate(raw, s.n, s.alpha, s.noise_count)
        rows.append(
            f"| {s.n} | {s.alpha} | {s.noise_count} | {fmt(s.sequential_wrong_prune_rate)} | "
            f"{fmt(s.conservative_wrong_prune_rate)} | {fmt(s.conservative_clique_intact_rate)} | {fmt(q3)} |"
        )
    table = "\n".join(rows)

    # Q1/Q2 readings: paired delta (noise=5 minus noise=0) per (N, alpha).
    q1_q2_lines: list[str] = []
    for n in config.sample_sizes:
        for alpha in config.alphas:
            control = next((s for s in summaries if s.n == n and s.alpha == alpha and s.noise_count == 0), None)
            treated = next((s for s in summaries if s.n == n and s.alpha == alpha and s.noise_count == 5), None)
            if control is None or treated is None:
                continue
            if control.sequential_wrong_prune_rate is not None and treated.sequential_wrong_prune_rate is not None:
                seq_delta = treated.sequential_wrong_prune_rate - control.sequential_wrong_prune_rate
            else:
                seq_delta = None
            if control.conservative_wrong_prune_rate is not None and treated.conservative_wrong_prune_rate is not None:
                cons_delta = treated.conservative_wrong_prune_rate - control.conservative_wrong_prune_rate
            else:
                cons_delta = None
            q1_q2_lines.append(
                f"- N={n}, alpha={alpha:g}: sequential delta (noise=5 minus noise=0) = {fmt(seq_delta)}; "
                f"conservative delta = {fmt(cons_delta)}."
            )
    q1_q2_text = "\n".join(q1_q2_lines)

    (output_dir / "stage4c_report.md").write_text(
        "# Stage 4c Cascading-Error Stress Test Report\n\n"
        f"{table}\n\n"
        "## Q1/Q2: does noise contamination increase the weak-edge wrong-prune rate?\n\n"
        f"{q1_q2_text}\n\n"
        "## Q3\n\n"
        "See the table's last column: among replicates where the sequential engine wrongly pruned the "
        "weak edge under noise contamination (`noise_count=5`), the fraction where a noise column was "
        "specifically among the tested neighbors -- the direct mechanistic check for the cascading "
        "pathway this charter exists to test.\n\n"
        "This charter is descriptive, per docs/stage4c_charter.md -- no established acceptable "
        "cascading-error rate exists to gate against; these numbers are reported for a future "
        "judgment call, not resolved here.\n\n"
        "See `raw_metrics.csv`, `summary.json`, and `wrong_prune_rate_by_engine.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return summaries
