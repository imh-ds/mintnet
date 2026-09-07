"""Evidence rendering for the Stage 4m cascading-error stress test
(chain/fork/hub). See docs/stage4m_charter.md. Descriptive only -- no
gate; reports the predeclared sub-questions plainly, per motif, and a
cross-motif comparison, mirroring Stage 4c's own report structure
generalized from one asymmetric triangle (a single weak edge) to three
structurally-symmetric motifs (both direct edges pooled per motif).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage4m import MOTIFS, Stage4mConfig, _DIRECT_EDGES, _pair_label

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _cell(raw: pd.DataFrame, motif: str, n: int, alpha: float, noise_count: int) -> pd.DataFrame:
    return raw.loc[
        (raw["motif"] == motif) & (raw["n"] == n) & (raw["alpha"] == alpha)
        & (raw["noise_count"] == noise_count) & (raw["status"] == "ok")
    ]


def _pooled_bool(subset: pd.DataFrame, motif: str, column_prefix: str) -> np.ndarray | None:
    """Stack a per-edge boolean column across both of the motif's direct
    edges into one flat array -- the pooling this charter's own
    structural-symmetry design requires (no single designated weak edge,
    unlike Stage 4c's asymmetric triangle)."""
    if subset.empty:
        return None
    arrays = []
    for i, j in _DIRECT_EDGES[motif]:
        label = _pair_label(i, j)
        arrays.append(subset[f"{column_prefix}_{label}"].astype(bool).to_numpy())
    return np.concatenate(arrays)


@dataclass(frozen=True)
class CellSummary:
    motif: str
    n: int
    alpha: float
    noise_count: int
    sequential_wrong_prune_rate: float | None
    conservative_wrong_prune_rate: float | None
    conservative_clique_intact_rate: float | None


def summarize_cell(raw: pd.DataFrame, motif: str, n: int, alpha: float, noise_count: int) -> CellSummary:
    subset = _cell(raw, motif, n, alpha, noise_count)
    if subset.empty:
        return CellSummary(motif, n, alpha, noise_count, None, None, None)
    seq_retained = _pooled_bool(subset, motif, "sequential_retained")
    cons_retained = _pooled_bool(subset, motif, "conservative_retained")
    clique_intact = _pooled_bool(subset, motif, "conservative_component_is_validated_clique")
    seq_wrong = float((~seq_retained).mean()) if seq_retained is not None else None
    cons_wrong = float((~cons_retained).mean()) if cons_retained is not None else None
    clique_rate = float(clique_intact.mean()) if clique_intact is not None else None
    return CellSummary(motif, n, alpha, noise_count, seq_wrong, cons_wrong, clique_rate)


def summarize_all(raw: pd.DataFrame, config: Stage4mConfig) -> list[CellSummary]:
    return [
        summarize_cell(raw, motif, n, alpha, noise_count)
        for motif in MOTIFS
        for n in config.sample_sizes
        for alpha in config.alphas
        for noise_count in config.noise_counts
    ]


def q3_noise_implication_rate(raw: pd.DataFrame, motif: str, n: int, alpha: float, noise_count: int) -> float | None:
    """Among replicate-edge instances (pooled across the motif's two
    direct edges) where the sequential engine wrongly pruned a true
    direct edge under noise contamination, the fraction where a noise
    column (index >= 3) was among the tested neighbors."""
    if noise_count == 0:
        return None
    subset = _cell(raw, motif, n, alpha, noise_count)
    if subset.empty:
        return None
    wrong_mask_parts = []
    noise_used_parts = []
    for i, j in _DIRECT_EDGES[motif]:
        label = _pair_label(i, j)
        retained = subset[f"sequential_retained_{label}"].astype(bool)
        wrong_mask_parts.append(~retained)
        noise_used_parts.append(subset[f"sequential_noise_neighbor_used_{label}"].astype(bool))
    wrong_mask = pd.concat(wrong_mask_parts, ignore_index=True)
    noise_used = pd.concat(noise_used_parts, ignore_index=True)
    wrong_noise_used = noise_used.loc[wrong_mask]
    if wrong_noise_used.empty:
        return None
    return float(wrong_noise_used.mean())


def _plot_wrong_prune_rates(summaries: list[CellSummary], path: Path) -> None:
    figure, axes = plt.subplots(1, len(MOTIFS), figsize=(5 * len(MOTIFS), 4), sharey=True)
    for axis, motif in zip(axes, MOTIFS):
        for noise_count, marker in ((0, "o"), (5, "s")):
            cells = sorted(
                (s for s in summaries if s.motif == motif and s.noise_count == noise_count
                 and s.sequential_wrong_prune_rate is not None),
                key=lambda s: (s.alpha, s.n),
            )
            by_alpha: dict[float, list[CellSummary]] = {}
            for c in cells:
                by_alpha.setdefault(c.alpha, []).append(c)
            for alpha, group in by_alpha.items():
                axis.plot(
                    [c.n for c in group], [c.sequential_wrong_prune_rate for c in group],
                    marker=marker, label=f"noise={noise_count}, alpha={alpha:g}",
                )
        axis.set_title(motif)
        axis.set_xlabel("N")
        axis.legend(fontsize="x-small")
    axes[0].set_ylabel("Sequential engine: direct-edge wrong-prune rate")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4m_report(raw: pd.DataFrame, config: Stage4mConfig, output_dir: Path) -> list[CellSummary]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = summarize_all(raw, config)
    (output_dir / "summary.json").write_text(json.dumps([asdict(s) for s in summaries], indent=2) + "\n", encoding="utf-8")
    _plot_wrong_prune_rates(summaries, output_dir / "wrong_prune_rate_by_motif.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = ["# Stage 4m Cascading-Error Stress Test Report (Chain/Fork/Hub)\n"]

    for motif in MOTIFS:
        rows = [
            f"## Motif: {motif}\n",
            "| N | alpha | noise_count | sequential wrong-prune rate | conservative wrong-prune rate | "
            "conservative clique-intact rate | Q3: noise implicated (when seq. wrong) |",
            "|---|---|---|---|---|---|---|",
        ]
        for s in summaries:
            if s.motif != motif:
                continue
            q3 = q3_noise_implication_rate(raw, s.motif, s.n, s.alpha, s.noise_count)
            rows.append(
                f"| {s.n} | {s.alpha} | {s.noise_count} | {fmt(s.sequential_wrong_prune_rate)} | "
                f"{fmt(s.conservative_wrong_prune_rate)} | {fmt(s.conservative_clique_intact_rate)} | {fmt(q3)} |"
            )
        q1_q2_lines: list[str] = []
        for n in config.sample_sizes:
            for alpha in config.alphas:
                control = next((s for s in summaries if s.motif == motif and s.n == n and s.alpha == alpha and s.noise_count == 0), None)
                treated = next((s for s in summaries if s.motif == motif and s.n == n and s.alpha == alpha and s.noise_count == 5), None)
                if control is None or treated is None:
                    continue
                seq_delta = (
                    treated.sequential_wrong_prune_rate - control.sequential_wrong_prune_rate
                    if control.sequential_wrong_prune_rate is not None and treated.sequential_wrong_prune_rate is not None
                    else None
                )
                cons_delta = (
                    treated.conservative_wrong_prune_rate - control.conservative_wrong_prune_rate
                    if control.conservative_wrong_prune_rate is not None and treated.conservative_wrong_prune_rate is not None
                    else None
                )
                q1_q2_lines.append(
                    f"- N={n}, alpha={alpha:g}: sequential delta (noise=5 minus noise=0) = {fmt(seq_delta)}; "
                    f"conservative delta = {fmt(cons_delta)}."
                )
        sections.append("\n".join(rows) + "\n\n### Q1/Q2 (delta, noise=5 minus noise=0)\n\n" + "\n".join(q1_q2_lines) + "\n")

    # Cross-motif comparison: pooled sequential delta per motif, across all N/alpha.
    cross_motif_lines = ["## Cross-motif comparison\n"]
    for motif in MOTIFS:
        deltas = []
        for n in config.sample_sizes:
            for alpha in config.alphas:
                control = next((s for s in summaries if s.motif == motif and s.n == n and s.alpha == alpha and s.noise_count == 0), None)
                treated = next((s for s in summaries if s.motif == motif and s.n == n and s.alpha == alpha and s.noise_count == 5), None)
                if control is None or treated is None:
                    continue
                if control.sequential_wrong_prune_rate is not None and treated.sequential_wrong_prune_rate is not None:
                    deltas.append(treated.sequential_wrong_prune_rate - control.sequential_wrong_prune_rate)
        mean_delta = sum(deltas) / len(deltas) if deltas else None
        cross_motif_lines.append(f"- {motif}: mean sequential wrong-prune delta across all N/alpha cells = {fmt(mean_delta)}")
    sections.append("\n".join(cross_motif_lines) + "\n")

    sections.append(
        "This charter is descriptive, per docs/stage4m_charter.md -- no established acceptable "
        "cascading-error rate exists to gate against; these numbers are reported for a future "
        "judgment call, not resolved here.\n\n"
        "See `raw_metrics.csv`, `summary.json`, and `wrong_prune_rate_by_motif.png` for complete evidence.\n"
    )
    (output_dir / "stage4m_report.md").write_text("\n".join(sections), encoding="utf-8")
    return summaries
