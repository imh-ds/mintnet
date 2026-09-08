"""Rejection-rate analysis and the H4/H5 verdicts for Stage 8h's own
raw evidence. See docs/stage8h_charter.md.
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
    from mintnet.experiments.stage8h_overconditioning_diagnosis import Stage8hConfig


def rejection_rate_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Per (decoy_count, n, strength): count, rejection rate, Wilson CI."""
    scored = raw.loc[(raw["status"] == "ok") & raw["rejected"].notna()]
    rows: list[dict[str, object]] = []
    for (decoy_count, n, strength), group in scored.groupby(["decoy_count", "n", "strength"]):
        count = len(group)
        rejections = int(group["rejected"].sum())
        ci_low, ci_high = wilson_ci(rejections, count) if count else (np.nan, np.nan)
        rows.append(
            {
                "decoy_count": decoy_count,
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
class H4Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h4(table: pd.DataFrame, min_count: int = 100) -> H4Verdict:
    """Per (n, strength): "supports" H4 if decoy_count=1's own
    rejection-rate CI sits entirely above decoy_count=0's own CI
    (non-overlapping, plus-one-decoy higher) -- adding one provably
    irrelevant conditioning variable to an already-sufficient set
    raises false rejection. "Contradicts" if not."""
    baseline = table.loc[table["decoy_count"] == 0].set_index(["n", "strength"])
    plus_one = table.loc[table["decoy_count"] == 1].set_index(["n", "strength"])

    supporting, contradicting, inconclusive = [], [], []
    for key in sorted(set(baseline.index) & set(plus_one.index)):
        base_row, plus_row = baseline.loc[key], plus_one.loc[key]
        if (
            base_row["count"] < min_count
            or plus_row["count"] < min_count
            or pd.isna(base_row["ci_high"])
            or pd.isna(plus_row["ci_low"])
        ):
            inconclusive.append([key[0], key[1]])
            continue
        if plus_row["ci_low"] > base_row["ci_high"]:
            supporting.append([int(key[0]), float(key[1])])
        else:
            contradicting.append([int(key[0]), float(key[1])])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"
    return H4Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


@dataclass(frozen=True)
class H5Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h5(table: pd.DataFrame, min_count: int = 100) -> H5Verdict:
    """Per (n, strength): "supports" H5 (saturation, matching D-069's
    own observed shape) if NEITHER decoy_count=2 nor decoy_count=3 has
    a rejection-rate CI sitting entirely above decoy_count=1's own CI
    -- i.e. no reliable further increase beyond the first added decoy.
    "Contradicts" if either does (a graded, still-climbing effect)."""
    plus_one = table.loc[table["decoy_count"] == 1].set_index(["n", "strength"])
    supporting, contradicting, inconclusive = [], [], []
    for key in sorted(plus_one.index):
        one_row = plus_one.loc[key]
        rows_at_larger = [
            table.loc[(table["decoy_count"] == count) & (table["n"] == key[0]) & (table["strength"] == key[1])]
            for count in (2, 3)
        ]
        if any(r.empty for r in rows_at_larger) or one_row["count"] < min_count or pd.isna(one_row["ci_high"]):
            inconclusive.append([key[0], key[1]])
            continue
        larger_rows = [r.iloc[0] for r in rows_at_larger]
        if any(r["count"] < min_count or pd.isna(r["ci_low"]) for r in larger_rows):
            inconclusive.append([key[0], key[1]])
            continue
        climbs_further = any(r["ci_low"] > one_row["ci_high"] for r in larger_rows)
        if climbs_further:
            contradicting.append([int(key[0]), float(key[1])])
        else:
            supporting.append([int(key[0]), float(key[1])])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"
    return H5Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


def write_report(raw: pd.DataFrame, config: "Stage8hConfig", output_dir: Path) -> tuple[H4Verdict, H5Verdict]:
    table = rejection_rate_table(raw)
    h4 = evaluate_h4(table)
    h5 = evaluate_h5(table)

    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "rejection_rate_table.csv", index=False)
    (output_dir / "h4_verdict.json").write_text(json.dumps(asdict(h4), indent=2) + "\n", encoding="utf-8")
    (output_dir / "h5_verdict.json").write_text(json.dumps(asdict(h5), indent=2) + "\n", encoding="utf-8")
    return h4, h5
