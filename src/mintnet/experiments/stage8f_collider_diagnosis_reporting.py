"""Rejection-rate analysis and the H1/H2 verdicts for Stage 8f's own
raw evidence. See docs/stage8f_charter.md.
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
    from mintnet.experiments.stage8f_collider_diagnosis import Stage8fConfig


def rejection_rate_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Per (fixture, n, strength): count, rejection rate, Wilson CI, and
    the mean nominal alpha the cell was tested against (constant across
    replicates for a fixed n, carried through for H1's own comparison)."""
    scored = raw.loc[(raw["status"] == "ok") & raw["rejected"].notna()]
    rows: list[dict[str, object]] = []
    for (fixture, n, strength), group in scored.groupby(["fixture", "n", "strength"]):
        count = len(group)
        rejections = int(group["rejected"].sum())
        ci_low, ci_high = wilson_ci(rejections, count) if count else (np.nan, np.nan)
        rows.append(
            {
                "fixture": fixture,
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
class H1Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE" (no cell had enough data)
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h1(table: pd.DataFrame, min_count: int = 100) -> H1Verdict:
    """A `step1` cell "supports" H1 if its rejection-rate CI sits
    entirely above the cell's own nominal alpha (`ci_low > mean_alpha`)
    -- conditioning on the sole collider rejects independence more
    often than a well-calibrated test targeting that same alpha ever
    should. "Contradicts" if the CI sits at or below alpha (no elevated
    bias detected). Inconclusive only if the cell lacks `min_count`
    valid replicates."""
    step1 = table.loc[table["fixture"] == "step1"]
    supporting, contradicting, inconclusive = [], [], []
    for _, row in step1.iterrows():
        if row["count"] < min_count or pd.isna(row["ci_low"]):
            inconclusive.append([row["n"], row["strength"]])
            continue
        if row["ci_low"] > row["mean_alpha"]:
            supporting.append([int(row["n"]), float(row["strength"])])
        else:
            contradicting.append([int(row["n"]), float(row["strength"])])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"  # any contradicting cell is enough to withhold confirmation
    return H1Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


@dataclass(frozen=True)
class H2Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h2(table: pd.DataFrame, min_count: int = 100) -> H2Verdict:
    """Per (n, strength): a cell "supports" H2 if `step2_collider`'s own
    rejection-rate CI sits entirely above `step2_control`'s own CI
    (non-overlapping, collider higher) -- the size-2 conditioning set's
    elevated bias is attributable to the collider's presence, not to
    conditioning-set size alone. "Contradicts" if the two CIs overlap or
    the control's own CI is not below the collider's -- i.e. no
    collider-specific effect beyond whatever a same-size, no-collider
    conditioning set already shows."""
    collider = table.loc[table["fixture"] == "step2_collider"].set_index(["n", "strength"])
    control = table.loc[table["fixture"] == "step2_control"].set_index(["n", "strength"])

    supporting, contradicting, inconclusive = [], [], []
    for key in sorted(set(collider.index) & set(control.index)):
        collider_row, control_row = collider.loc[key], control.loc[key]
        if (
            collider_row["count"] < min_count
            or control_row["count"] < min_count
            or pd.isna(collider_row["ci_low"])
            or pd.isna(control_row["ci_high"])
        ):
            inconclusive.append([key[0], key[1]])
            continue
        if collider_row["ci_low"] > control_row["ci_high"]:
            supporting.append([int(key[0]), float(key[1])])
        else:
            contradicting.append([int(key[0]), float(key[1])])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"
    return H2Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


def write_report(raw: pd.DataFrame, config: "Stage8fConfig", output_dir: Path) -> tuple[H1Verdict, H2Verdict]:
    table = rejection_rate_table(raw)
    h1 = evaluate_h1(table)
    h2 = evaluate_h2(table)

    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "rejection_rate_table.csv", index=False)
    (output_dir / "h1_verdict.json").write_text(json.dumps(asdict(h1), indent=2) + "\n", encoding="utf-8")
    (output_dir / "h2_verdict.json").write_text(json.dumps(asdict(h2), indent=2) + "\n", encoding="utf-8")
    return h1, h2
