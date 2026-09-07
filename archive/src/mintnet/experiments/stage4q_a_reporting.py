"""Gate evaluation and evidence rendering for Stage 4q Part A. See
docs/stage4q_charter.md. Reports the margin above the .80 gate
explicitly at every N, and whether it is comparable to D-011's own
comfortable N=750 general-floor margin (.032) rather than D-018's thin
N=1500 margin (.017).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage4q_a import Stage4qAConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

# D-018's own N=1500 margin, reused as the comparison baseline this
# part exists to beat.
_D018_N1500_MARGIN = 0.017


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class NDecision:
    n: int
    status: str
    alpha: float | None
    overlap_indirect_tpr: float | None
    chain_indirect_tpr: float | None
    fork_indirect_tpr: float | None
    true_edge_prune_fpr: float | None
    margin: float | None
    comfortable: bool | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage4qAConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        alpha = float(n_raw["alpha"].iloc[0]) if not n_raw.empty else None
        failures.append("estimator or DGP errors")
        return NDecision(n, "REASSESS", alpha, None, None, None, None, None, None, tuple(failures))

    alpha = float(n_raw["alpha"].iloc[0])
    validation = _partition(n_raw, config.validation_replicates)

    overlap_tpr = float(validation["overlap_indirect_tpr"].mean())
    chain_tpr = float(validation["chain_indirect_tpr"].mean())
    fork_tpr = float(validation["fork_indirect_tpr"].mean())
    true_edge_fpr = float(validation["true_edge_prune_fpr"].mean())
    screening_rate = float(validation["screening_false_edge_rate"].mean())
    final_rate = float(validation["final_false_edge_rate"].mean())

    for label, tpr in (("chain", chain_tpr), ("fork", fork_tpr), ("overlap", overlap_tpr)):
        if tpr < config.minimum_indirect_prune_tpr:
            failures.append(f"{label} indirect TPR {tpr:.4f} below required {config.minimum_indirect_prune_tpr:.4f}")
    if true_edge_fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {true_edge_fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if final_rate > screening_rate + config.false_edge_rate_tolerance:
        failures.append(
            f"final false-edge rate {final_rate:.4f} exceeds screening baseline "
            f"{screening_rate:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
        )

    margin = overlap_tpr - config.minimum_indirect_prune_tpr
    comfortable = margin >= config.required_margin
    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(
        n, status, alpha, overlap_tpr, chain_tpr, fork_tpr, true_edge_fpr, margin, comfortable, tuple(failures)
    )


def evaluate_stage4q_a_gate(raw: pd.DataFrame, config: Stage4qAConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _plot_margin(decision: GateDecision, config: Stage4qAConfig, path: Path) -> None:
    figure, axis = plt.subplots()
    cells = sorted(decision.by_n, key=lambda d: d.n)
    ns = [d.n for d in cells]
    axis.plot(ns, [d.overlap_indirect_tpr for d in cells], marker="o", label="overlap indirect TPR")
    axis.axhline(0.80, color="gray", linestyle=":", linewidth=0.8, label="gate (.80)")
    axis.axhline(
        0.80 + config.required_margin, color="tab:green", linestyle="--", linewidth=0.8,
        label=f"comfortable margin (.80 + {config.required_margin:g})",
    )
    axis.axhline(0.817, color="tab:orange", linestyle="-.", linewidth=0.8, label="D-018 N=1500 (.817)")
    axis.set_xlabel("N")
    axis.set_ylabel("Overlap indirect-edge TPR (conservative engine)")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4q_a_report(raw: pd.DataFrame, config: Stage4qAConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4q_a_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    _plot_margin(decision, config, output_dir / "margin_by_n.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | status | alpha | overlap TPR | margin above .80 | comfortable (>= D-011-scale margin)? | "
        "chain TPR | fork TPR | true-edge FPR | failures |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    comfortable_ns = []
    for d in decision.by_n:
        failures = "None" if not d.failures else ", ".join(d.failures)
        comfortable = "None" if d.comfortable is None else ("yes" if d.comfortable else "no")
        if d.comfortable:
            comfortable_ns.append(d.n)
        rows.append(
            f"| {d.n} | {d.status} | {fmt(d.alpha)} | {fmt(d.overlap_indirect_tpr)} | {fmt(d.margin)} | "
            f"{comfortable} | {fmt(d.chain_indirect_tpr)} | {fmt(d.fork_indirect_tpr)} | "
            f"{fmt(d.true_edge_prune_fpr)} | {failures} |"
        )
    table = "\n".join(rows)

    verdict = (
        f"N in {comfortable_ns} clear with a comfortable margin (>= {config.required_margin:g}, "
        f"D-011-scale confidence)." if comfortable_ns else
        "No tested N clears with a comfortable margin -- even the higher N remain close to the gate."
    )

    (output_dir / "stage4q_a_report.md").write_text(
        "# Stage 4q Part A: Higher-N Conservative Floor for Overlap (p=15)\n\n"
        f"{table}\n\n"
        f"**Verdict**: {verdict}\n\n"
        f"D-018's own N=1500 margin was `.017`; D-045 found an independent draw at the same N landing "
        f"just under the gate entirely. This part's own required margin for 'comfortable' is "
        f"`{config.required_margin:g}` (matching D-011's own N=750 general-floor margin scale).\n\n"
        "See `raw_metrics.csv`, `decision.json`, `resolved_config.yaml`, and `margin_by_n.png` "
        "for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
