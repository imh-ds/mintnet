"""Recall/removal comparison and the PROCEED/REASSESS gate for Stage
9b's own raw evidence. See docs/stage9b_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from mintnet.experiments.stage9b_stability_rescue_validation import Stage9bConfig


def explode_qualifying(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (dgp, n, replicate, i, j) with conditioning_size_
    used >= 2 -- only from replicates that ran successfully."""
    rows: list[dict[str, object]] = []
    for record in raw.loc[raw["status"] == "ok"].itertuples(index=False):
        for edge in json.loads(record.qualifying_json):
            rows.append(
                {
                    "dgp": record.dgp, "n": record.n, "replicate": record.replicate,
                    "i": edge["i"], "j": edge["j"], "is_true_edge": edge["is_true_edge"],
                    "original_retained": edge["original_retained"], "final_retained": edge["final_retained"],
                    "conditioning_size_used": edge["conditioning_size_used"],
                    "pi_final": edge["pi_final"], "rescued": edge["rescued"],
                }
            )
    return pd.DataFrame(rows)


_METRICS_COLUMNS = (
    "dgp", "n", "true_retained_count", "recall", "false_wrongly_retained_count", "removal_rate",
)


def recall_removal_table(exploded: pd.DataFrame) -> pd.DataFrame:
    """Per (dgp, n), among conditioning_size_used >= 2 edges: recall
    (fraction of originally-and-correctly-retained true edges that stay
    retained after rescue) and removal rate (fraction of wrongly-
    retained false edges the rescue flips to pruned)."""
    bootstrapped = exploded.loc[exploded["pi_final"].notna()]
    rows: list[dict[str, object]] = []
    for (dgp, n), group in bootstrapped.groupby(["dgp", "n"]):
        true_retained = group.loc[group["is_true_edge"] & group["original_retained"]]
        false_wrongly_retained = group.loc[(~group["is_true_edge"]) & group["original_retained"]]
        recall = float(true_retained["final_retained"].mean()) if len(true_retained) else float("nan")
        removal_rate = float(false_wrongly_retained["rescued"].mean()) if len(false_wrongly_retained) else float("nan")
        rows.append(
            {
                "dgp": dgp, "n": n,
                "true_retained_count": len(true_retained), "recall": recall,
                "false_wrongly_retained_count": len(false_wrongly_retained), "removal_rate": removal_rate,
            }
        )
    return pd.DataFrame(rows, columns=list(_METRICS_COLUMNS))


@dataclass(frozen=True)
class Stage9bDecision:
    status: str  # "PROCEED" or "REASSESS"
    min_recall: float
    min_removal_rate: float
    min_count: int
    cells_passing: list[list[object]]
    cells_failing: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_stage9b_gate(
    table: pd.DataFrame, min_recall: float = 0.95, min_removal_rate: float = 0.85, min_count: int = 10
) -> Stage9bDecision:
    passing, failing, inconclusive = [], [], []
    for _, row in table.iterrows():
        if row["true_retained_count"] < min_count or row["false_wrongly_retained_count"] < min_count:
            inconclusive.append([row["dgp"], int(row["n"])])
            continue
        if row["recall"] >= min_recall and row["removal_rate"] >= min_removal_rate:
            passing.append([row["dgp"], int(row["n"])])
        else:
            failing.append([row["dgp"], int(row["n"])])

    status = "PROCEED" if passing and not failing else "REASSESS"
    return Stage9bDecision(
        status=status, min_recall=min_recall, min_removal_rate=min_removal_rate, min_count=min_count,
        cells_passing=passing, cells_failing=failing, cells_inconclusive=inconclusive,
    )


def write_report(raw: pd.DataFrame, config: "Stage9bConfig", output_dir: Path) -> Stage9bDecision:
    exploded = explode_qualifying(raw)
    table = recall_removal_table(exploded)
    decision = evaluate_stage9b_gate(table)

    output_dir.mkdir(parents=True, exist_ok=True)
    exploded.to_csv(output_dir / "exploded_qualifying.csv", index=False)
    table.to_csv(output_dir / "recall_removal_table.csv", index=False)
    (output_dir / "decision.json").write_text(json.dumps(asdict(decision), indent=2) + "\n", encoding="utf-8")
    return decision
