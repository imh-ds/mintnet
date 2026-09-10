"""Part A (stratified accuracy, D-076-style) and Part B (confidence-
transfer check, Stage 7g's own methodology) for Stage 7h's own raw
evidence. See docs/stage7h_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

if TYPE_CHECKING:
    from mintnet.experiments.stage7h_composed import Stage7hConfig

UNRESOLVED_CONDITIONING_SIZE = 2  # D-076's own boundary


def explode_qualifying(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (condition, dgp, strength, n, replicate, i, j) --
    every screened candidate edge, with its own decision, ground truth,
    conditioning depth, and confidence. Only from successful replicates."""
    rows: list[dict[str, object]] = []
    for record in raw.loc[raw["status"] == "ok"].itertuples(index=False):
        for edge in json.loads(record.qualifying_json):
            rows.append(
                {
                    "condition": record.condition, "dgp": record.dgp, "strength": record.strength,
                    "n": record.n, "replicate": record.replicate,
                    "i": edge["i"], "j": edge["j"], "is_true_edge": edge["is_true_edge"],
                    "retained": edge["retained"], "conditioning_size_used": edge["conditioning_size_used"],
                    "decisive_p_value": edge["decisive_p_value"], "confidence": edge["confidence"],
                }
            )
    return pd.DataFrame(rows)


def stratified_accuracy_table(exploded: pd.DataFrame) -> pd.DataFrame:
    """D-076's own design: accuracy (decision matches ground truth) by
    (dgp, strength, n, is_true_edge, conditioning_size_used) -- retain
    reliability vs. prune reliability, tracked separately, extended
    across the N/strength grid D-076 itself never swept."""
    exploded = exploded.copy()
    exploded["correct"] = exploded["retained"] == exploded["is_true_edge"]
    grouped = exploded.groupby(["dgp", "strength", "n", "is_true_edge", "conditioning_size_used"])
    table = grouped.agg(count=("correct", "size"), accuracy=("correct", "mean")).reset_index()
    return table.sort_values(["dgp", "strength", "n", "is_true_edge", "conditioning_size_used"]).reset_index(drop=True)


@dataclass(frozen=True)
class ConfidenceTransferResult:
    """Part B's own gate, per (dgp, strength): is confidence informative
    (correct > incorrect) among conditioning_size_used >= 2 decisions,
    and does it trend with N -- using Stage 7g's own validated
    methodology (Mann-Whitney / Spearman), not a brittle pointwise rule."""

    dgp: str
    strength: float
    n_decisions: int
    mean_confidence_correct: float
    mean_confidence_incorrect: float
    informative: bool  # correct mean > incorrect mean (both must exist)
    spearman_correlation: float
    spearman_p_value: float
    significant_positive_trend: bool
    status: str  # "PROCEED" or "REASSESS"


def confidence_transfer_check(exploded: pd.DataFrame, *, min_count: int = 20) -> pd.DataFrame:
    unresolved = exploded.loc[exploded["conditioning_size_used"] >= UNRESOLVED_CONDITIONING_SIZE].copy()
    unresolved["correct"] = unresolved["retained"] == unresolved["is_true_edge"]

    results: list[ConfidenceTransferResult] = []
    for (dgp, strength), group in unresolved.groupby(["dgp", "strength"]):
        group = group.dropna(subset=["confidence"])
        correct = group.loc[group["correct"], "confidence"]
        incorrect = group.loc[~group["correct"], "confidence"]
        if len(group) < min_count or len(correct) == 0 or len(incorrect) == 0:
            results.append(
                ConfidenceTransferResult(
                    dgp=dgp, strength=float(strength), n_decisions=len(group),
                    mean_confidence_correct=float(correct.mean()) if len(correct) else float("nan"),
                    mean_confidence_incorrect=float(incorrect.mean()) if len(incorrect) else float("nan"),
                    informative=False, spearman_correlation=float("nan"), spearman_p_value=float("nan"),
                    significant_positive_trend=False, status="REASSESS",
                )
            )
            continue

        correct_mean = float(correct.mean())
        incorrect_mean = float(incorrect.mean())
        informative = correct_mean > incorrect_mean

        corr, trend_p = spearmanr(group["n"], group["confidence"])
        significant_positive_trend = bool(trend_p < 0.05 and corr > 0)

        status = "PROCEED" if informative and significant_positive_trend else "REASSESS"
        results.append(
            ConfidenceTransferResult(
                dgp=dgp, strength=float(strength), n_decisions=len(group),
                mean_confidence_correct=correct_mean, mean_confidence_incorrect=incorrect_mean,
                informative=informative, spearman_correlation=float(corr), spearman_p_value=float(trend_p),
                significant_positive_trend=significant_positive_trend, status=status,
            )
        )
    return pd.DataFrame([asdict(r) for r in results])


@dataclass(frozen=True)
class Stage7hDecision:
    part_a_status: str  # "PROCEED" or "REASSESS" -- see accessibility_gate
    part_a_min_true_edge_accuracy: float
    part_b_status: str  # "PROCEED" if every (dgp, strength) cell PROCEEDs, else "REASSESS"
    part_b_failing_cells: list[list[object]]


def accessibility_gate(table: pd.DataFrame, *, min_true_edge_accuracy: float = 0.95) -> tuple[str, float]:
    true_edges = table.loc[table["is_true_edge"]]
    if true_edges.empty:
        return "REASSESS", float("nan")
    min_accuracy = float(true_edges["accuracy"].min())
    return ("PROCEED" if min_accuracy >= min_true_edge_accuracy else "REASSESS"), min_accuracy


def evaluate(table: pd.DataFrame, transfer: pd.DataFrame) -> Stage7hDecision:
    part_a_status, part_a_min = accessibility_gate(table)
    failing = transfer.loc[transfer["status"] != "PROCEED", ["dgp", "strength"]].values.tolist()
    part_b_status = "PROCEED" if not failing else "REASSESS"
    return Stage7hDecision(
        part_a_status=part_a_status, part_a_min_true_edge_accuracy=part_a_min,
        part_b_status=part_b_status, part_b_failing_cells=failing,
    )


def write_report(raw: pd.DataFrame, config: "Stage7hConfig", output_dir: Path) -> Stage7hDecision:
    exploded = explode_qualifying(raw)
    table = stratified_accuracy_table(exploded)
    transfer = confidence_transfer_check(exploded)
    decision = evaluate(table, transfer)

    output_dir.mkdir(parents=True, exist_ok=True)
    exploded.to_csv(output_dir / "exploded_qualifying.csv", index=False)
    table.to_csv(output_dir / "stratified_accuracy_table.csv", index=False)
    transfer.to_csv(output_dir / "confidence_transfer_table.csv", index=False)
    (output_dir / "decision.json").write_text(json.dumps(asdict(decision), indent=2) + "\n", encoding="utf-8")
    return decision
