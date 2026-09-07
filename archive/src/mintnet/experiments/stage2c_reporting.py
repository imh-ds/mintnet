"""Per-N gate evaluation and evidence rendering for the Stage 2b composition experiment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage2c import Stage2cConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class NDecision:
    n: int
    status: str
    dpi_alpha: float
    indirect_prune_tpr: float | None
    true_edge_prune_fpr: float | None
    screening_false_edge_rate: float | None
    final_false_edge_rate: float | None
    triad_rate: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage2cConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        dpi_alpha = float(n_raw["dpi_alpha"].iloc[0]) if not n_raw.empty else float("nan")
        return NDecision(n, "REASSESS", dpi_alpha, None, None, None, None, None, tuple(failures))

    dpi_alpha = float(n_raw["dpi_alpha"].iloc[0])
    validation = _partition(n_raw, config.validation_replicates)
    indirect_tpr = float(validation["indirect_prune_tpr"].mean())
    true_edge_fpr = float(validation["true_edge_prune_fpr"].mean())
    screening_rate = float(validation["screening_false_edge_rate"].mean())
    final_rate = float(validation["final_false_edge_rate"].mean())
    triad_rate = float(
        validation[["chain_is_triad", "fork_is_triad", "hub_is_validated"]].mean().mean()
    )

    if indirect_tpr < config.minimum_indirect_prune_tpr:
        failures.append(f"indirect TPR {indirect_tpr:.4f} below required {config.minimum_indirect_prune_tpr:.4f}")
    if true_edge_fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {true_edge_fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if final_rate > screening_rate + config.false_edge_rate_tolerance:
        failures.append(
            f"final false-edge rate {final_rate:.4f} exceeds screening baseline "
            f"{screening_rate:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
        )

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(
        n, status, dpi_alpha, indirect_tpr, true_edge_fpr, screening_rate, final_rate, triad_rate, tuple(failures)
    )


def evaluate_stage2c_gate(raw: pd.DataFrame, config: Stage2cConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _plot_false_edge_comparison(decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    ns = [d.n for d in decision.by_n]
    screening = [d.screening_false_edge_rate for d in decision.by_n]
    final = [d.final_false_edge_rate for d in decision.by_n]
    axis.plot(ns, screening, marker="o", label="screening-only false-edge rate")
    axis.plot(ns, final, marker="s", label="final (composed) false-edge rate")
    axis.set_xlabel("N")
    axis.set_ylabel("False-edge rate")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage2c_report(raw: pd.DataFrame, config: Stage2cConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage2c_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_false_edge_comparison(decision, output_dir / "false_edge_rate_comparison.png")

    rows = [
        "| N | status | dpi_alpha | indirect TPR | true-edge FPR | screening FER | final FER | triad rate | failures |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        def fmt(value: float | None) -> str:
            return "None" if value is None else f"{value:.4f}"

        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.status} | {d.dpi_alpha:.4f} | {fmt(d.indirect_prune_tpr)} | "
            f"{fmt(d.true_edge_prune_fpr)} | {fmt(d.screening_false_edge_rate)} | "
            f"{fmt(d.final_false_edge_rate)} | {fmt(d.triad_rate)} | {failures} |"
        )
    table = "\n".join(rows)
    (output_dir / "stage2c_report.md").write_text(
        "# Stage 2b Screening + DPI Composition Report\n\n"
        f"{table}\n\n"
        "`triad rate`: fraction of the three true motif components that formed a clean "
        "3-node candidate triad (and so had DPI applied) rather than some other shape.\n\n"
        "See `raw_metrics.csv`, `decision.json`, and `false_edge_rate_comparison.png` "
        "for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
