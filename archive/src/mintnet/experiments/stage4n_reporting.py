"""Evidence rendering for the Stage 4n cascading-error stress test
(overlap). See docs/stage4n_charter.md. Descriptive only -- no gate;
reports the predeclared sub-questions plainly, pooling wrong-pruning
across overlap's 6 true direct edges (none is a single designated weak
edge, mirroring Stage 4m's own pooling rationale), plus the new Q4
opposite-triangle-node check unique to this charter.

Optionally builds a three-way comparison against Stage 4c's (triangle)
and Stage 4m's (chain/fork/hub) own raw evidence, when their paths are
supplied.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage1l import TRUE_EDGES
from mintnet.experiments.stage4n import OPPOSITE_NODES, Stage4nConfig, _pair_label

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _cell(raw: pd.DataFrame, n: int, alpha: float, noise_count: int) -> pd.DataFrame:
    return raw.loc[(raw["n"] == n) & (raw["alpha"] == alpha) & (raw["noise_count"] == noise_count) & (raw["status"] == "ok")]


def _pooled_bool(subset: pd.DataFrame, column_prefix: str) -> pd.Series | None:
    """Stack a per-edge boolean column across all 6 direct edges into one
    flat series -- the pooling this charter's own structural-symmetry
    design requires (no single designated weak edge among overlap's
    direct edges)."""
    if subset.empty:
        return None
    parts = [subset[f"{column_prefix}_{_pair_label(i, j)}"].astype(bool) for i, j in TRUE_EDGES]
    return pd.concat(parts, ignore_index=True)


@dataclass(frozen=True)
class CellSummary:
    n: int
    alpha: float
    noise_count: int
    sequential_wrong_prune_rate: float | None
    conservative_wrong_prune_rate: float | None
    conservative_clique_intact_rate: float | None


def summarize_cell(raw: pd.DataFrame, n: int, alpha: float, noise_count: int) -> CellSummary:
    subset = _cell(raw, n, alpha, noise_count)
    if subset.empty:
        return CellSummary(n, alpha, noise_count, None, None, None)
    seq_retained = _pooled_bool(subset, "sequential_retained")
    cons_retained = _pooled_bool(subset, "conservative_retained")
    clique_intact = _pooled_bool(subset, "conservative_component_is_validated_clique")
    seq_wrong = float((~seq_retained).mean()) if seq_retained is not None else None
    cons_wrong = float((~cons_retained).mean()) if cons_retained is not None else None
    clique_rate = float(clique_intact.mean()) if clique_intact is not None else None
    return CellSummary(n, alpha, noise_count, seq_wrong, cons_wrong, clique_rate)


def summarize_all(raw: pd.DataFrame, config: Stage4nConfig) -> list[CellSummary]:
    return [
        summarize_cell(raw, n, alpha, noise_count)
        for n in config.sample_sizes
        for alpha in config.alphas
        for noise_count in config.noise_counts
    ]


def _wrongly_pruned_flag_rate(raw: pd.DataFrame, n: int, alpha: float, noise_count: int, flag_prefix: str) -> float | None:
    subset = _cell(raw, n, alpha, noise_count)
    if subset.empty:
        return None
    wrong_parts = []
    flag_parts = []
    for i, j in TRUE_EDGES:
        label = _pair_label(i, j)
        retained = subset[f"sequential_retained_{label}"].astype(bool)
        wrong_parts.append(~retained)
        flag_parts.append(subset[f"{flag_prefix}_{label}"].astype(bool))
    wrong_mask = pd.concat(wrong_parts, ignore_index=True)
    flag = pd.concat(flag_parts, ignore_index=True)
    wrong_flag = flag.loc[wrong_mask]
    if wrong_flag.empty:
        return None
    return float(wrong_flag.mean())


def q3_noise_implication_rate(raw: pd.DataFrame, n: int, alpha: float, noise_count: int) -> float | None:
    """Among wrongly-pruned direct-edge instances (pooled across all 6),
    the fraction where a noise column was among the tested neighbors."""
    if noise_count == 0:
        return None
    return _wrongly_pruned_flag_rate(raw, n, alpha, noise_count, "sequential_noise_neighbor_used")


def q4_opposite_branch_implication_rate(raw: pd.DataFrame, n: int, alpha: float, noise_count: int) -> float | None:
    """Among wrongly-pruned direct-edge instances (pooled across all 6),
    the fraction where a node from the *opposite* triangle was among the
    tested neighbors -- a cascading pathway independent of noise, unique
    to overlap's own shared-node structure. Computed at every
    noise_count, including 0, since this pathway does not require noise
    to exist."""
    return _wrongly_pruned_flag_rate(raw, n, alpha, noise_count, "sequential_opposite_neighbor_used")


def _plot_wrong_prune_rates(summaries: list[CellSummary], path: Path) -> None:
    figure, axis = plt.subplots()
    for noise_count, marker in ((0, "o"), (5, "s")):
        cells = sorted(
            (s for s in summaries if s.noise_count == noise_count and s.sequential_wrong_prune_rate is not None),
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
    axis.set_xlabel("N")
    axis.set_ylabel("Sequential engine: overlap direct-edge wrong-prune rate")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _load_json(path: Path | None) -> list[dict[str, object]] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _three_way_comparison_table(
    summaries: list[CellSummary], stage4c_summary: list[dict[str, object]] | None,
    stage4m_summary: list[dict[str, object]] | None,
) -> str | None:
    """Direct comparison against Stage 4c's (triangle) and Stage 4m's
    (chain/fork/hub, per motif) own summary.json entries at matching
    N/alpha/noise_count -- required evidence per docs/stage4n_charter.md.
    """
    if stage4c_summary is None and stage4m_summary is None:
        return None

    def fmt(value: object) -> str:
        return "None" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)

    motifs = sorted({row["motif"] for row in stage4m_summary}) if stage4m_summary else []
    header = (
        "| N | alpha | noise_count | overlap (this charter) | triangle (Stage 4c) | "
        + " | ".join(f"{m} (Stage 4m)" for m in motifs) + " |"
    )
    separator = "|" + "---|" * (3 + 2 + len(motifs))
    rows = [header, separator]
    for s in summaries:
        c4_rate = None
        if stage4c_summary is not None:
            match = next((r for r in stage4c_summary if r["n"] == s.n and r["alpha"] == s.alpha and r["noise_count"] == s.noise_count), None)
            c4_rate = match["sequential_wrong_prune_rate"] if match else None
        motif_rates = []
        for motif in motifs:
            match = next(
                (r for r in (stage4m_summary or []) if r["motif"] == motif and r["n"] == s.n and r["alpha"] == s.alpha and r["noise_count"] == s.noise_count),
                None,
            )
            motif_rates.append(match["sequential_wrong_prune_rate"] if match else None)
        rows.append(
            f"| {s.n} | {s.alpha} | {s.noise_count} | {fmt(s.sequential_wrong_prune_rate)} | {fmt(c4_rate)} | "
            + " | ".join(fmt(r) for r in motif_rates) + " |"
        )
    return "\n".join(rows)


def write_stage4n_report(
    raw: pd.DataFrame, config: Stage4nConfig, output_dir: Path,
    stage4c_summary_path: Path | None = None, stage4m_summary_path: Path | None = None,
) -> list[CellSummary]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = summarize_all(raw, config)
    (output_dir / "summary.json").write_text(json.dumps([asdict(s) for s in summaries], indent=2) + "\n", encoding="utf-8")
    _plot_wrong_prune_rates(summaries, output_dir / "wrong_prune_rate.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | alpha | noise_count | sequential wrong-prune rate | conservative wrong-prune rate | "
        "conservative clique-intact rate | Q3: noise implicated | Q4: opposite-branch implicated |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        q3 = q3_noise_implication_rate(raw, s.n, s.alpha, s.noise_count)
        q4 = q4_opposite_branch_implication_rate(raw, s.n, s.alpha, s.noise_count)
        rows.append(
            f"| {s.n} | {s.alpha} | {s.noise_count} | {fmt(s.sequential_wrong_prune_rate)} | "
            f"{fmt(s.conservative_wrong_prune_rate)} | {fmt(s.conservative_clique_intact_rate)} | {fmt(q3)} | {fmt(q4)} |"
        )
    table = "\n".join(rows)

    q1_q2_lines: list[str] = []
    for n in config.sample_sizes:
        for alpha in config.alphas:
            control = next((s for s in summaries if s.n == n and s.alpha == alpha and s.noise_count == 0), None)
            treated = next((s for s in summaries if s.n == n and s.alpha == alpha and s.noise_count == 5), None)
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
    q1_q2_text = "\n".join(q1_q2_lines)

    stage4c_summary = _load_json(stage4c_summary_path)
    stage4m_summary = _load_json(stage4m_summary_path)
    comparison_table = _three_way_comparison_table(summaries, stage4c_summary, stage4m_summary)
    comparison_section = (
        "\n## Three-way comparison (overlap vs. Stage 4c's triangle vs. Stage 4m's chain/fork/hub)\n\n"
        f"{comparison_table}\n"
        if comparison_table is not None
        else "\n## Three-way comparison\n\nNo Stage 4c/4m summary paths were supplied -- comparison skipped.\n"
    )

    (output_dir / "stage4n_report.md").write_text(
        "# Stage 4n Cascading-Error Stress Test Report (Overlap)\n\n"
        f"{table}\n\n"
        "## Q1/Q2: does noise contamination increase the direct-edge wrong-prune rate?\n\n"
        f"{q1_q2_text}\n"
        f"{comparison_section}\n"
        "## Q3\n\n"
        "See the table's Q3 column: among wrongly-pruned direct-edge instances (pooled across all 6) "
        "under noise contamination (`noise_count=5`), the fraction where a noise column was specifically "
        "among the tested neighbors.\n\n"
        "## Q4 (new to this charter)\n\n"
        "See the table's Q4 column, reported at every `noise_count` including `0`: among wrongly-pruned "
        "direct-edge instances, the fraction where a node from the *opposite* triangle (not noise, "
        "overlap's own structure) was among the tested neighbors -- a cascading pathway with no analog "
        "in Stage 4c or Stage 4m.\n\n"
        "This charter is descriptive, per docs/stage4n_charter.md -- no established acceptable "
        "cascading-error rate exists to gate against; these numbers are reported for a future "
        "judgment call, not resolved here.\n\n"
        "See `raw_metrics.csv`, `summary.json`, and `wrong_prune_rate.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return summaries
