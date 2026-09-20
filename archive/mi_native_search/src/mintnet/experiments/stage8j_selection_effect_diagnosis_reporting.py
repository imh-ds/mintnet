"""Rejection-rate analysis and the H7/H8 verdicts for Stage 8j's own
raw evidence. See docs/stage8j_charter.md.
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
    from mintnet.experiments.stage8j_selection_effect_diagnosis import Stage8jConfig


def rejection_rate_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Per (condition, k, n, strength): count, rejection rate, Wilson CI."""
    scored = raw.loc[(raw["status"] == "ok") & raw["rejected"].notna()]
    rows: list[dict[str, object]] = []
    for (condition, k, n, strength), group in scored.groupby(["condition", "k", "n", "strength"]):
        count = len(group)
        rejections = int(group["rejected"].sum())
        ci_low, ci_high = wilson_ci(rejections, count) if count else (np.nan, np.nan)
        rows.append(
            {
                "condition": condition,
                "k": k,
                "n": n,
                "strength": strength,
                "count": count,
                "rejections": rejections,
                "rejection_rate": rejections / count if count else np.nan,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "mean_alpha": float(group["alpha"].mean()) if count else np.nan,
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class H7Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h7(table: pd.DataFrame, min_count: int = 100) -> H7Verdict:
    """Per (k, n, strength): "supports" H7 if selected_decoy's own
    rejection-rate CI sits entirely above random_decoy's own CI
    (non-overlapping, selected higher) -- both conditions add exactly
    one decoy at the same conditioning size, differing only in whether
    it was chosen via selection. "Contradicts" if not."""
    random_decoy = table.loc[table["condition"] == "random_decoy"].set_index(["k", "n", "strength"])
    selected_decoy = table.loc[table["condition"] == "selected_decoy"].set_index(["k", "n", "strength"])

    supporting, contradicting, inconclusive = [], [], []
    for key in sorted(set(random_decoy.index) & set(selected_decoy.index)):
        random_row, selected_row = random_decoy.loc[key], selected_decoy.loc[key]
        if (
            random_row["count"] < min_count
            or selected_row["count"] < min_count
            or pd.isna(random_row["ci_high"])
            or pd.isna(selected_row["ci_low"])
        ):
            inconclusive.append([int(key[0]), int(key[1]), float(key[2])])
            continue
        if selected_row["ci_low"] > random_row["ci_high"]:
            supporting.append([int(key[0]), int(key[1]), float(key[2])])
        else:
            contradicting.append([int(key[0]), int(key[1]), float(key[2])])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"
    return H7Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


@dataclass(frozen=True)
class H8Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h8(table: pd.DataFrame, min_count: int = 100, small_k: int = 5, large_k: int = 20) -> H8Verdict:
    """Per (n, strength): "supports" H8 if selected_decoy's own
    rejection-rate CI at `large_k` sits entirely above its own CI at
    `small_k` -- a larger selection pool produces a larger effect, as
    extreme-value reasoning predicts if selection is the real driver."""
    selected_decoy = table.loc[table["condition"] == "selected_decoy"]
    small = selected_decoy.loc[selected_decoy["k"] == small_k].set_index(["n", "strength"])
    large = selected_decoy.loc[selected_decoy["k"] == large_k].set_index(["n", "strength"])

    supporting, contradicting, inconclusive = [], [], []
    for key in sorted(set(small.index) & set(large.index)):
        small_row, large_row = small.loc[key], large.loc[key]
        if (
            small_row["count"] < min_count
            or large_row["count"] < min_count
            or pd.isna(small_row["ci_high"])
            or pd.isna(large_row["ci_low"])
        ):
            inconclusive.append([int(key[0]), float(key[1])])
            continue
        if large_row["ci_low"] > small_row["ci_high"]:
            supporting.append([int(key[0]), float(key[1])])
        else:
            contradicting.append([int(key[0]), float(key[1])])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"
    return H8Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


def write_report(raw: pd.DataFrame, config: "Stage8jConfig", output_dir: Path) -> tuple[H7Verdict, H8Verdict]:
    table = rejection_rate_table(raw)
    h7 = evaluate_h7(table)
    h8 = evaluate_h8(table)

    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "rejection_rate_table.csv", index=False)
    (output_dir / "h7_verdict.json").write_text(json.dumps(asdict(h7), indent=2) + "\n", encoding="utf-8")
    (output_dir / "h8_verdict.json").write_text(json.dumps(asdict(h8), indent=2) + "\n", encoding="utf-8")
    return h7, h8
