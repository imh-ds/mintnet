"""Gate evaluation and evidence rendering for the Stage 4p canonical
N-grid public benchmark. See docs/stage4p_charter.md.

Produces one side-by-side table per DGP: both engines' PROCEED/
REASSESS status and metrics visible in the same row per N, plus an
explicit cross-reference note to docs/stage4o_recommendation.md's own
N-threshold matrix wherever this benchmark's results are expected to
diverge from it (overlap under the sequential engine, N < 750, since
this charter deliberately reuses D-012's general formula rather than
overlap's own specialized one).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage4p import DGPS, ENGINES, Stage4pConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class CellDecision:
    dgp: str
    engine: str
    n: int
    status: str
    alpha: float | None
    chain_indirect_tpr: float | None
    fork_indirect_tpr: float | None
    third_indirect_tpr: float | None
    true_edge_prune_fpr: float | None
    screening_false_edge_rate: float | None
    final_false_edge_rate: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_cell: tuple[CellDecision, ...]


def evaluate_cell(raw: pd.DataFrame, dgp: str, engine: str, n: int, config: Stage4pConfig) -> CellDecision:
    cell_raw = raw.loc[(raw["dgp"] == dgp) & (raw["engine"] == engine) & (raw["n"] == n)]
    failures: list[str] = []
    if cell_raw.empty or not cell_raw["status"].eq("ok").all():
        alpha = float(cell_raw["alpha"].iloc[0]) if not cell_raw.empty else None
        failures.append("estimator or DGP errors")
        return CellDecision(dgp, engine, n, "REASSESS", alpha, None, None, None, None, None, None, tuple(failures))

    alpha = float(cell_raw["alpha"].iloc[0])
    validation = _partition(cell_raw, config.validation_replicates)

    chain_tpr = float(validation["chain_indirect_tpr"].mean())
    fork_tpr = float(validation["fork_indirect_tpr"].mean())
    third_tpr = float(validation["third_indirect_tpr"].mean())
    true_edge_fpr = float(validation["true_edge_prune_fpr"].mean())
    screening_rate = float(validation["screening_false_edge_rate"].mean())
    final_rate = float(validation["final_false_edge_rate"].mean())

    for label, tpr in (("chain", chain_tpr), ("fork", fork_tpr), ("third-shape", third_tpr)):
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
        dgp, engine, n, status, alpha, chain_tpr, fork_tpr, third_tpr, true_edge_fpr, screening_rate, final_rate,
        tuple(failures),
    )


def evaluate_stage4p_gate(raw: pd.DataFrame, config: Stage4pConfig) -> GateDecision:
    by_cell = tuple(
        evaluate_cell(raw, dgp, engine, n, config)
        for dgp in DGPS
        for n in config.sample_sizes
        for engine in ENGINES
    )
    return GateDecision(by_cell)


def _plot_side_by_side(decision: GateDecision, sample_sizes: tuple[int, ...], path: Path) -> None:
    figure, axes = plt.subplots(1, len(DGPS), figsize=(6 * len(DGPS), 4.5), sharey=True)
    if len(DGPS) == 1:
        axes = [axes]
    for axis, dgp in zip(axes, DGPS):
        for engine, marker in (("conservative", "o"), ("sequential", "s")):
            cells = sorted(
                (c for c in decision.by_cell if c.dgp == dgp and c.engine == engine), key=lambda c: c.n
            )
            axis.plot(
                [c.n for c in cells], [c.third_indirect_tpr for c in cells],
                marker=marker, label=f"{engine}",
            )
        axis.axhline(0.80, color="gray", linestyle=":", linewidth=0.8)
        axis.set_title(f"{dgp}-based p=15 network")
        axis.set_xlabel("N")
    axes[0].set_ylabel("Third-shape indirect-edge TPR (overlap composite / hub)")
    axes[-1].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4p_report(raw: pd.DataFrame, config: Stage4pConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4p_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_cell": [asdict(c) for c in decision.by_cell]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    _plot_side_by_side(decision, config.sample_sizes, output_dir / "tpr_by_n_side_by_side.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = ["# Stage 4p Canonical N-Grid Public Benchmark Report\n"]
    sections.append(
        "Both engines use the exact same D-012 general alpha(N) formula at every N -- deliberately not "
        "overlap's own specialized formula (Stage 4g/4i/4j). Divergences between the sequential engine's "
        "overlap-based results here and `docs/stage4o_recommendation.md`'s own specialized findings are "
        "expected below N=750 and demonstrate why that specialized calibration work was necessary, not a "
        "contradiction between two competing results.\n"
    )

    for dgp in DGPS:
        rows = [
            f"## {dgp}-based p=15 network\n",
            "| N | conservative status | conservative third-shape TPR | sequential status | "
            "sequential third-shape TPR | conservative true-edge FPR | sequential true-edge FPR |",
            "|---|---|---|---|---|---|---|",
        ]
        for n in config.sample_sizes:
            cons = next(c for c in decision.by_cell if c.dgp == dgp and c.engine == "conservative" and c.n == n)
            seq = next(c for c in decision.by_cell if c.dgp == dgp and c.engine == "sequential" and c.n == n)
            rows.append(
                f"| {n} | {cons.status} | {fmt(cons.third_indirect_tpr)} | {seq.status} | "
                f"{fmt(seq.third_indirect_tpr)} | {fmt(cons.true_edge_prune_fpr)} | {fmt(seq.true_edge_prune_fpr)} |"
            )
        failing = [c for c in decision.by_cell if c.dgp == dgp and c.status != "PROCEED"]
        if failing:
            detail = "\n".join(
                f"- {c.engine} @ N={c.n}: {', '.join(c.failures)}" for c in failing
            )
            rows.append(f"\n### Failures\n\n{detail}")
        sections.append("\n".join(rows) + "\n")

    sections.append(
        "See `docs/stage4o_recommendation.md` for the deeper, per-shape-specialized findings this "
        "benchmark deliberately does not replace. See `raw_metrics.csv`, `decision.json`, "
        "`resolved_config.yaml`, and `tpr_by_n_side_by_side.png` for complete evidence.\n"
    )
    (output_dir / "stage4p_report.md").write_text("\n".join(sections), encoding="utf-8")
    return decision
