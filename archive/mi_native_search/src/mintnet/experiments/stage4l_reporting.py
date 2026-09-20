"""Gate evaluation and evidence rendering for the Stage 4l composed-
pipeline-with-noise experiment for chain/fork/hub (sequential engine,
p=15). See docs/stage4l_charter.md.

Full-grid reporting requirement (mirrors Stage 4j/4k's own
requirement): every one of the 6 (strength, N) cells is reported
individually regardless of the overall outcome. If any cell fails, an
isolated-vs-composed comparison against that same cell's own Stage 4k
result (D-040) is additionally computed, per motif, so a REASSESS here
can be attributed to screening pressure specifically rather than
conflated with a conditioning-mechanism regression Stage 4k already
ruled out.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage4l import HUB_INDIRECT, Stage4lConfig, _pair_label

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_MOTIF_PAIR_LABEL = {
    "chain": _pair_label(0, 2),
    "fork": _pair_label(3, 5),
    "hub": _pair_label(*HUB_INDIRECT[0]),
}


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _motif_decomposition(rows: pd.DataFrame, motif: str) -> tuple[float | None, float | None]:
    """Pooled candidacy rate and conditional accuracy for one motif's
    single indirect pair -- Stage 4e's own corrected metric, generalized
    from overlap's 4-pair case to this charter's 1-pair-per-motif case."""
    label = _MOTIF_PAIR_LABEL[motif]
    candidate_column = rows[f"candidate_{label}"]
    if candidate_column.isna().any():
        return None, None
    correct_column = rows[f"correctly_pruned_{label}"]
    total_candidates = int(candidate_column.astype(bool).sum())
    total_correct = int(correct_column.fillna(False).astype(bool).sum())
    candidacy_rate = total_candidates / len(rows)
    conditional_accuracy = (total_correct / total_candidates) if total_candidates > 0 else None
    return candidacy_rate, conditional_accuracy


def _isolated_decomposition(stage4k_raw_path: Path, motif: str, strength: float, n: int) -> tuple[float | None, float | None]:
    """Stage 4k's own isolated candidacy rate and conditional accuracy at
    the matching (motif, strength, N) cell, for the required composed-
    vs-isolated comparison."""
    if not stage4k_raw_path.is_file():
        return None, None
    from mintnet.experiments.stage4k_reporting import _pooled_metrics

    raw = pd.read_csv(stage4k_raw_path)
    cell = raw.loc[(raw["motif"] == motif) & (raw["strength"] == strength) & (raw["n"] == n)]
    if cell.empty or not cell["status"].eq("ok").all():
        return None, None
    validation = cell.loc[cell["replicate"].between(500, 999)]
    metrics = _pooled_metrics(validation)
    if metrics is None:
        return None, None
    candidacy_rate, accuracy, _fpr = metrics
    return candidacy_rate, accuracy


@dataclass(frozen=True)
class CellDecision:
    strength: float
    n: int
    status: str
    alpha: float | None
    chain_indirect_tpr: float | None
    fork_indirect_tpr: float | None
    hub_indirect_tpr: float | None
    true_edge_prune_fpr: float | None
    screening_false_edge_rate: float | None
    final_false_edge_rate: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    overall_status: str
    by_cell: tuple[CellDecision, ...]


def evaluate_cell(raw: pd.DataFrame, strength: float, n: int, config: Stage4lConfig) -> CellDecision:
    cell_raw = raw.loc[(raw["strength"] == strength) & (raw["n"] == n)]
    failures: list[str] = []
    if cell_raw.empty or not cell_raw["status"].eq("ok").all():
        alpha = float(cell_raw["alpha"].iloc[0]) if not cell_raw.empty else None
        failures.append("estimator or DGP errors")
        return CellDecision(strength, n, "REASSESS", alpha, None, None, None, None, None, None, tuple(failures))

    alpha = float(cell_raw["alpha"].iloc[0])
    validation = _partition(cell_raw, config.validation_replicates)

    chain_tpr = float(validation["chain_indirect_tpr"].mean())
    fork_tpr = float(validation["fork_indirect_tpr"].mean())
    hub_tpr = float(validation["hub_indirect_tpr"].mean())
    true_edge_fpr = float(validation["true_edge_prune_fpr"].mean())
    screening_rate = float(validation["screening_false_edge_rate"].mean())
    final_rate = float(validation["final_false_edge_rate"].mean())

    for label, tpr in (("chain", chain_tpr), ("fork", fork_tpr), ("hub", hub_tpr)):
        if tpr < config.minimum_indirect_prune_tpr:
            failures.append(f"{label} indirect TPR {tpr:.4f} below required {config.minimum_indirect_prune_tpr:.4f}")
    if true_edge_fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {true_edge_fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if final_rate > screening_rate + config.false_edge_rate_tolerance:
        failures.append(
            f"final false-edge rate {final_rate:.4f} exceeds screening baseline "
            f"{screening_rate:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
        )

    status = "PROCEED" if not failures else "REASSESS"
    return CellDecision(
        strength, n, status, alpha, chain_tpr, fork_tpr, hub_tpr, true_edge_fpr, screening_rate, final_rate,
        tuple(failures),
    )


def evaluate_stage4l_gate(raw: pd.DataFrame, config: Stage4lConfig) -> GateDecision:
    by_cell = tuple(
        evaluate_cell(raw, strength, n, config) for strength in config.strengths for n in config.sample_sizes
    )
    overall_status = "PROCEED" if all(c.status == "PROCEED" for c in by_cell) else "REASSESS"
    return GateDecision(overall_status, by_cell)


def _plot_tpr(decision: GateDecision, config: Stage4lConfig, path: Path) -> None:
    figure, axes = plt.subplots(1, len(config.strengths), figsize=(5 * len(config.strengths), 4), sharey=True)
    if len(config.strengths) == 1:
        axes = [axes]
    for axis, strength in zip(axes, config.strengths):
        cells = sorted((c for c in decision.by_cell if c.strength == strength), key=lambda c: c.n)
        ns = [c.n for c in cells]
        axis.plot(ns, [c.chain_indirect_tpr for c in cells], marker="o", label="chain")
        axis.plot(ns, [c.fork_indirect_tpr for c in cells], marker="s", label="fork")
        axis.plot(ns, [c.hub_indirect_tpr for c in cells], marker="^", label="hub")
        axis.axhline(0.80, color="gray", linestyle=":", linewidth=0.8)
        axis.set_title(f"strength={strength:g}")
        axis.set_xlabel("N")
    axes[0].set_ylabel("indirect-edge TPR")
    axes[-1].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4l_report(
    raw: pd.DataFrame, config: Stage4lConfig, output_dir: Path, stage4k_raw_path: Path | None = None
) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4l_gate(raw, config)

    comparisons: list[dict[str, object]] = []
    if stage4k_raw_path is not None:
        for cell in decision.by_cell:
            if cell.status == "PROCEED":
                continue
            cell_raw = raw.loc[(raw["strength"] == cell.strength) & (raw["n"] == cell.n)]
            validation = _partition(cell_raw, config.validation_replicates)
            for motif in ("chain", "fork", "hub"):
                composed_candidacy, composed_accuracy = _motif_decomposition(validation, motif)
                isolated_candidacy, isolated_accuracy = _isolated_decomposition(
                    stage4k_raw_path, motif, cell.strength, cell.n
                )
                comparisons.append(
                    {
                        "strength": cell.strength,
                        "n": cell.n,
                        "motif": motif,
                        "composed_candidacy_rate": composed_candidacy,
                        "composed_conditional_accuracy": composed_accuracy,
                        "isolated_candidacy_rate": isolated_candidacy,
                        "isolated_conditional_accuracy": isolated_accuracy,
                    }
                )

    (output_dir / "decision.json").write_text(
        json.dumps(
            {
                "overall_status": decision.overall_status,
                "by_cell": [asdict(c) for c in decision.by_cell],
                "isolated_vs_composed_comparison": comparisons,
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_tpr(decision, config, output_dir / "indirect_tpr_by_strength_n.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| strength | N | status | alpha | chain TPR | fork TPR | hub TPR | true-edge FPR | "
        "screening FER | final FER | failures |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in sorted(decision.by_cell, key=lambda c: (c.strength, c.n)):
        failures = "None" if not c.failures else ", ".join(c.failures)
        alpha = "None" if c.alpha is None else f"{c.alpha:.4f}"
        rows.append(
            f"| {c.strength:g} | {c.n} | {c.status} | {alpha} | {fmt(c.chain_indirect_tpr)} | "
            f"{fmt(c.fork_indirect_tpr)} | {fmt(c.hub_indirect_tpr)} | {fmt(c.true_edge_prune_fpr)} | "
            f"{fmt(c.screening_false_edge_rate)} | {fmt(c.final_false_edge_rate)} | {failures} |"
        )
    table = "\n".join(rows)

    comparison_section = ""
    if comparisons:
        comp_rows = [
            "| strength | N | motif | composed candidacy | composed accuracy | isolated candidacy "
            "(Stage 4k) | isolated accuracy (Stage 4k) |",
            "|---|---|---|---|---|---|---|",
        ]
        for c in comparisons:
            comp_rows.append(
                f"| {c['strength']:g} | {c['n']} | {c['motif']} | {fmt(c['composed_candidacy_rate'])} | "
                f"{fmt(c['composed_conditional_accuracy'])} | {fmt(c['isolated_candidacy_rate'])} | "
                f"{fmt(c['isolated_conditional_accuracy'])} |"
            )
        comparison_section = (
            "\n## Isolated-vs-composed comparison (failing cells only, per docs/stage4l_charter.md)\n\n"
            + "\n".join(comp_rows) + "\n"
        )
    elif any(c.status != "PROCEED" for c in decision.by_cell):
        comparison_section = (
            "\n## Isolated-vs-composed comparison\n\nSome cells failed but no Stage 4k raw evidence path "
            "was supplied -- comparison skipped.\n"
        )

    (output_dir / "stage4l_report.md").write_text(
        "# Stage 4l Composed Pipeline with Noise Report, Chain/Fork/Hub (Sequential Engine, p=15)\n\n"
        f"Overall gate: **{decision.overall_status}**\n\n"
        f"{table}\n"
        f"{comparison_section}\n"
        "See `raw_metrics.csv`, `decision.json`, `resolved_config.yaml`, and "
        "`indirect_tpr_by_strength_n.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
