"""H9 (stability separates correct from incorrect) and the Step 4
`pi_min` filter gate for Stage 9a's own raw evidence. See
docs/stage9a_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

if TYPE_CHECKING:
    from mintnet.experiments.stage9a_bootstrap_stability import Stage9aConfig


def explode_qualifying(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (dgp, n, replicate, i, j) -- only from replicates
    that ran successfully, mirroring stage8c_composed_calibration_
    reporting.explode_edges's own convention exactly."""
    rows: list[dict[str, object]] = []
    for record in raw.loc[raw["status"] == "ok"].itertuples(index=False):
        for edge in json.loads(record.qualifying_json):
            rows.append(
                {
                    "dgp": record.dgp, "n": record.n, "replicate": record.replicate,
                    "i": edge["i"], "j": edge["j"], "is_true_edge": edge["is_true_edge"],
                    "retained": edge["retained"], "category": edge["category"],
                    "conditioning_size_used": edge["conditioning_size_used"],
                    "decisive_p_value": edge["decisive_p_value"],
                    "bootstrapped": edge["bootstrapped"], "pi_final": edge["pi_final"],
                }
            )
    return pd.DataFrame(rows)


def pi_final_summary(exploded: pd.DataFrame) -> pd.DataFrame:
    """Per (dgp, n, category), among bootstrapped rows only: count,
    mean/median pi_final."""
    scored = exploded.loc[exploded["bootstrapped"] & exploded["pi_final"].notna()]
    rows: list[dict[str, object]] = []
    for (dgp, n, category), group in scored.groupby(["dgp", "n", "category"]):
        rows.append(
            {
                "dgp": dgp, "n": n, "category": category, "count": len(group),
                "mean_pi_final": float(group["pi_final"].mean()),
                "median_pi_final": float(group["pi_final"].median()),
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class H9Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h9(exploded: pd.DataFrame, min_count: int = 20, alpha: float = 0.05) -> H9Verdict:
    """Per (dgp, n): "supports" H9 if false_wrongly_retained's own
    pi_final distribution is reliably (one-sided Mann-Whitney U,
    p < alpha) lower than true_retained's own -- mirroring D-019's own
    "intermediate, not high, stability" question on a different engine.
    Requires at least `min_count` bootstrapped rows in each category."""
    scored = exploded.loc[exploded["bootstrapped"] & exploded["pi_final"].notna()]
    supporting, contradicting, inconclusive = [], [], []
    for (dgp, n), group in scored.groupby(["dgp", "n"]):
        true_retained = group.loc[group["category"] == "true_retained", "pi_final"]
        false_wrongly_retained = group.loc[group["category"] == "false_wrongly_retained", "pi_final"]
        if len(true_retained) < min_count or len(false_wrongly_retained) < min_count:
            inconclusive.append([dgp, int(n)])
            continue
        statistic, p_value = mannwhitneyu(false_wrongly_retained, true_retained, alternative="less")
        if p_value < alpha:
            supporting.append([dgp, int(n)])
        else:
            contradicting.append([dgp, int(n)])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"
    return H9Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


_PI_MIN_GRID: tuple[float, ...] = (0.70, 0.80, 0.90, 0.95)


def _filter_metrics(group: pd.DataFrame, pi_min: float) -> dict[str, float]:
    true_retained = group.loc[group["category"] == "true_retained", "pi_final"]
    false_wrongly_retained = group.loc[group["category"] == "false_wrongly_retained", "pi_final"]
    recall = float((true_retained >= pi_min).mean()) if len(true_retained) else float("nan")
    removal_rate = float((false_wrongly_retained < pi_min).mean()) if len(false_wrongly_retained) else float("nan")
    return {
        "pi_min": pi_min, "true_retained_count": len(true_retained), "recall": recall,
        "false_wrongly_retained_count": len(false_wrongly_retained), "removal_rate": removal_rate,
    }


@dataclass(frozen=True)
class Stage9aFilterDecision:
    status: str  # "PROCEED" or "REASSESS"
    selected_pi_min: float | None
    development: dict[str, float] | None
    validation: dict[str, float] | None
    min_recall: float
    min_removal_rate: float


def calibrate_pi_min_filter(
    exploded: pd.DataFrame,
    development_replicates: tuple[int, int],
    validation_replicates: tuple[int, int],
    min_recall: float = 0.90,
    min_removal_rate: float = 0.50,
) -> Stage9aFilterDecision:
    """Development/validation split, smallest eligible `pi_min` on
    development confirmed again on validation -- mirrors D-020's own
    gate design exactly, scoped to conditioning_size_used >= 2."""
    scored = exploded.loc[exploded["bootstrapped"] & exploded["pi_final"].notna()]
    dev = scored.loc[(scored["replicate"] >= development_replicates[0]) & (scored["replicate"] <= development_replicates[1])]
    val = scored.loc[(scored["replicate"] >= validation_replicates[0]) & (scored["replicate"] <= validation_replicates[1])]

    for pi_min in sorted(_PI_MIN_GRID):
        dev_metrics = _filter_metrics(dev, pi_min)
        if dev_metrics["recall"] >= min_recall and dev_metrics["removal_rate"] >= min_removal_rate:
            val_metrics = _filter_metrics(val, pi_min)
            if val_metrics["recall"] >= min_recall and val_metrics["removal_rate"] >= min_removal_rate:
                return Stage9aFilterDecision(
                    status="PROCEED", selected_pi_min=pi_min, development=dev_metrics, validation=val_metrics,
                    min_recall=min_recall, min_removal_rate=min_removal_rate,
                )
            return Stage9aFilterDecision(
                status="REASSESS", selected_pi_min=pi_min, development=dev_metrics, validation=val_metrics,
                min_recall=min_recall, min_removal_rate=min_removal_rate,
            )
    return Stage9aFilterDecision(
        status="REASSESS", selected_pi_min=None, development=None, validation=None,
        min_recall=min_recall, min_removal_rate=min_removal_rate,
    )


def write_report(raw: pd.DataFrame, config: "Stage9aConfig", output_dir: Path) -> tuple[H9Verdict, Stage9aFilterDecision | None]:
    exploded = explode_qualifying(raw)
    summary = pi_final_summary(exploded)
    h9 = evaluate_h9(exploded)

    output_dir.mkdir(parents=True, exist_ok=True)
    exploded.to_csv(output_dir / "exploded_qualifying.csv", index=False)
    summary.to_csv(output_dir / "pi_final_summary.csv", index=False)
    (output_dir / "h9_verdict.json").write_text(json.dumps(asdict(h9), indent=2) + "\n", encoding="utf-8")

    filter_decision = None
    if h9.status == "CONFIRMED":
        filter_decision = calibrate_pi_min_filter(exploded, config.development_replicates, config.validation_replicates)
        (output_dir / "filter_decision.json").write_text(
            json.dumps(asdict(filter_decision), indent=2) + "\n", encoding="utf-8"
        )
    return h9, filter_decision
