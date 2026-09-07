"""Binning, monotonicity, and calibration (ECE) analysis plus the
PROCEED/REASSESS gate for Stage 8a's own raw per-edge evidence. See
docs/stage8a_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from mintnet.experiments.stage6c_reporting import wilson_ci

if TYPE_CHECKING:
    from mintnet.experiments.stage8a_calibration import Stage8aConfig


def _motif_of(condition: str) -> str:
    # "chain_0.5" -> "chain", "weak_edge_triangle_0.08" -> "weak_edge_triangle"
    family, _, _ = condition.rpartition("_")
    return family


def bin_margins(raw: pd.DataFrame, bin_count: int) -> pd.DataFrame:
    """Assign every valid (non-NaN-margin) row to a margin decile bin."""
    scored = raw.loc[(raw["status"] == "ok") & raw["margin"].notna()].copy()
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    scored["bin"] = pd.cut(scored["margin"], bins=edges, include_lowest=True, labels=False)
    scored["motif"] = scored["condition"].map(_motif_of)
    return scored


def bin_table(scored: pd.DataFrame, bin_count: int) -> pd.DataFrame:
    """Per (motif, n, bin): mean margin, empirical accuracy, Wilson CI, count."""
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    rows: list[dict[str, object]] = []
    for (motif, n), group in scored.groupby(["motif", "n"]):
        for bin_index in range(bin_count):
            in_bin = group.loc[group["bin"] == bin_index]
            count = len(in_bin)
            if count == 0:
                rows.append(
                    {
                        "motif": motif,
                        "n": n,
                        "bin": bin_index,
                        "bin_low": edges[bin_index],
                        "bin_high": edges[bin_index + 1],
                        "count": 0,
                        "mean_margin": np.nan,
                        "empirical_accuracy": np.nan,
                        "ci_low": np.nan,
                        "ci_high": np.nan,
                    }
                )
                continue
            correct = int(in_bin["correct"].sum())
            ci_low, ci_high = wilson_ci(correct, count)
            rows.append(
                {
                    "motif": motif,
                    "n": n,
                    "bin": bin_index,
                    "bin_low": edges[bin_index],
                    "bin_high": edges[bin_index + 1],
                    "count": count,
                    "mean_margin": float(in_bin["margin"].mean()),
                    "empirical_accuracy": correct / count,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                }
            )
    return pd.DataFrame(rows)


def check_monotonicity(bins: pd.DataFrame) -> dict[tuple[str, int], bool]:
    """Per (motif, n): True if empirical accuracy is non-decreasing
    across populated bins, within Wilson-CI overlap (a CI overlap
    between adjacent populated bins does not count as a violation)."""
    result: dict[tuple[str, int], bool] = {}
    for (motif, n), group in bins.groupby(["motif", "n"]):
        populated = group.loc[group["count"] > 0].sort_values("bin")
        ok = True
        previous = None
        for _, row in populated.iterrows():
            if previous is not None:
                # Violation only if this bin's accuracy is strictly
                # lower AND its CI does not overlap the previous bin's.
                if row["empirical_accuracy"] < previous["empirical_accuracy"] and row["ci_high"] < previous["ci_low"]:
                    ok = False
            previous = row
        result[(motif, n)] = ok
    return result


def compute_ece(bins: pd.DataFrame) -> dict[tuple[str, int], float]:
    """Per (motif, n): count-weighted mean |mean_margin - empirical_accuracy| over populated bins."""
    result: dict[tuple[str, int], float] = {}
    for (motif, n), group in bins.groupby(["motif", "n"]):
        populated = group.loc[group["count"] > 0]
        total = populated["count"].sum()
        if total == 0:
            result[(motif, n)] = float("nan")
            continue
        weighted_error = (populated["count"] * (populated["mean_margin"] - populated["empirical_accuracy"]).abs()).sum()
        result[(motif, n)] = float(weighted_error / total)
    return result


@dataclass(frozen=True)
class Stage8aDecision:
    status: str  # "PROCEED", "REASSESS_RECALIBRATION", or "REASSESS_DEFECT"
    ece_tolerance: float
    monotonicity_violations: list[list[object]]
    ece_by_cell: dict[str, float]
    max_ece: float


def evaluate_stage8a_gate(raw: pd.DataFrame, config: "Stage8aConfig") -> Stage8aDecision:
    scored = bin_margins(raw, config.bin_count)
    bins = bin_table(scored, config.bin_count)
    monotonic = check_monotonicity(bins)
    ece = compute_ece(bins)

    violations = [[motif, int(n)] for (motif, n), ok in monotonic.items() if not ok]
    max_ece = max((value for value in ece.values() if not np.isnan(value)), default=float("nan"))

    if violations:
        status = "REASSESS_DEFECT"
    elif max_ece > config.ece_tolerance:
        status = "REASSESS_RECALIBRATION"
    else:
        status = "PROCEED"

    return Stage8aDecision(
        status=status,
        ece_tolerance=config.ece_tolerance,
        monotonicity_violations=violations,
        ece_by_cell={f"{motif}_n{int(n)}": value for (motif, n), value in ece.items()},
        max_ece=max_ece,
    )


def write_report(raw: pd.DataFrame, config: "Stage8aConfig", output_dir: Path) -> Stage8aDecision:
    scored = bin_margins(raw, config.bin_count)
    bins = bin_table(scored, config.bin_count)
    decision = evaluate_stage8a_gate(raw, config)

    bins.to_csv(output_dir / "bin_table.csv", index=False)
    (output_dir / "decision.json").write_text(json.dumps(asdict(decision), indent=2) + "\n", encoding="utf-8")
    return decision
