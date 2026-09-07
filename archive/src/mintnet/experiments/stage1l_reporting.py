"""Held-out gate evaluation and evidence rendering for the Stage 1L experiment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage1l import Stage1lConfig


@dataclass(frozen=True)
class NDecision:
    n: int
    alpha: float
    status: str
    indirect_prune_tpr: float | None
    true_edge_prune_fpr: float | None
    margin: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage1lConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        alpha = float(n_raw["alpha"].iloc[0]) if not n_raw.empty else float("nan")
        return NDecision(n, alpha, "REASSESS", None, None, None, tuple(failures))

    alpha = float(n_raw["alpha"].iloc[0])
    validation = _partition(n_raw, config.validation_replicates)
    if validation.empty or not np.isfinite(validation[["indirect_prune_tpr", "true_edge_prune_fpr"]]).all().all():
        failures.append("missing validation evidence")
        return NDecision(n, alpha, "REASSESS", None, None, None, tuple(failures))

    tpr = float(validation["indirect_prune_tpr"].mean())
    fpr = float(validation["true_edge_prune_fpr"].mean())
    tpr_margin = tpr - config.minimum_indirect_prune_tpr
    fpr_margin = config.maximum_true_edge_prune_fpr - fpr
    margin = min(tpr_margin, fpr_margin)

    if tpr < config.minimum_indirect_prune_tpr:
        failures.append(f"indirect TPR {tpr:.4f} below required {config.minimum_indirect_prune_tpr:.4f}")
    if fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if margin < config.required_margin:
        failures.append(f"margin {margin:.4f} below required {config.required_margin:.4f}")

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(n, alpha, status, tpr, fpr, margin, tuple(failures))


def evaluate_stage1l_gate(raw: pd.DataFrame, config: Stage1lConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def write_stage1l_report(raw: pd.DataFrame, config: Stage1lConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage1l_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    rows = ["| N | alpha | status | indirect TPR | true-edge FPR | margin | failures |", "|---|---|---|---|---|---|---|"]
    for d in decision.by_n:
        def fmt(value: float | None) -> str:
            return "None" if value is None else f"{value:.4f}"

        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.n} | {d.alpha:.4f} | {d.status} | {fmt(d.indirect_prune_tpr)} | "
            f"{fmt(d.true_edge_prune_fpr)} | {fmt(d.margin)} | {failures} |"
        )
    table = "\n".join(rows)
    (output_dir / "stage1l_report.md").write_text(
        "# Stage 1L Multi-Variable Conditioning Report\n\n"
        f"{table}\n\n"
        "See `raw_metrics.csv`, `decision.json`, and `resolved_config.yaml` "
        "for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
