"""Diagnoses D-068's own composed-tier false-edge margin reversal. See
docs/stage8d_charter.md.

Steps 1-3 (this module): consumes Stage 8c's own enriched evidence
(conditioning_size_used/cap_reached now carried per edge -- see
stage8c_composed_calibration.py and stage8c_composed_calibration_
reporting.explode_edges) and tests two falsifiable hypotheses:

- H1 (cap-reached): within the reversed top margin bin, is a
  cap_reached=True edge's own accuracy materially lower than a
  cap_reached=False edge's own accuracy?
- H2 (conditioning-size-graded): does the false-edge monotonicity/ECE
  picture improve when restricted to small conditioning_size_used
  values and worsen at large ones?

Step 4 (the candidate-fix re-run at a larger max_conditioning_size) is
intentionally not implemented here -- the charter only calls for it if
H1 or H2 is confirmed against real evidence, not built speculatively
ahead of that result.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from mintnet.experiments.stage6c_reporting import wilson_ci
from mintnet.experiments.stage8a_calibration_reporting import bin_table, check_monotonicity, compute_ece
from mintnet.experiments.stage8c_composed_calibration_reporting import explode_edges

if TYPE_CHECKING:
    pass


def _false_edges_with_diagnostics(exploded: pd.DataFrame) -> pd.DataFrame:
    return exploded.loc[
        (exploded["status"] == "ok")
        & (~exploded["is_true_edge"])
        & exploded["margin"].notna()
        & exploded["cap_reached"].notna()
    ].copy()


def h1_cap_reached_table(exploded: pd.DataFrame, bin_count: int) -> pd.DataFrame:
    """Per (dgp, n), within the top margin bin only: accuracy and
    Wilson CI for cap_reached=True vs. cap_reached=False false edges."""
    false_edges = _false_edges_with_diagnostics(exploded)
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    false_edges["bin"] = pd.cut(false_edges["margin"], bins=edges, include_lowest=True, labels=False)
    top_bin = bin_count - 1
    top = false_edges.loc[false_edges["bin"] == top_bin]

    rows: list[dict[str, object]] = []
    for (dgp, n), group in top.groupby(["dgp", "n"]):
        for cap_reached in (True, False):
            sub = group.loc[group["cap_reached"] == cap_reached]
            count = len(sub)
            if count == 0:
                rows.append(
                    {"dgp": dgp, "n": n, "cap_reached": cap_reached, "count": 0,
                     "accuracy": np.nan, "ci_low": np.nan, "ci_high": np.nan}
                )
                continue
            correct = int(sub["correct"].sum())
            ci_low, ci_high = wilson_ci(correct, count)
            rows.append(
                {"dgp": dgp, "n": n, "cap_reached": cap_reached, "count": count,
                 "accuracy": correct / count, "ci_low": ci_low, "ci_high": ci_high}
            )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class H1Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE" (too few cap_reached=True cases anywhere)
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h1(table: pd.DataFrame, min_count: int = 30) -> H1Verdict:
    """A cell "supports" H1 if cap_reached=True's accuracy CI sits
    entirely below cap_reached=False's own CI (non-overlapping, in the
    expected direction) and both sides have at least `min_count`
    edges. "Contradicts" if the CIs are non-overlapping the OTHER way.
    Otherwise inconclusive (overlapping CIs, or too few cap_reached
    cases in that cell to say anything)."""
    supporting, contradicting, inconclusive = [], [], []
    for (dgp, n), group in table.groupby(["dgp", "n"]):
        true_row = group.loc[group["cap_reached"] == True]  # noqa: E712
        false_row = group.loc[group["cap_reached"] == False]  # noqa: E712
        if true_row.empty or false_row.empty:
            inconclusive.append([dgp, int(n)])
            continue
        true_row, false_row = true_row.iloc[0], false_row.iloc[0]
        if true_row["count"] < min_count or false_row["count"] < min_count:
            inconclusive.append([dgp, int(n)])
            continue
        if true_row["ci_high"] < false_row["ci_low"]:
            supporting.append([dgp, int(n)])
        elif false_row["ci_high"] < true_row["ci_low"]:
            contradicting.append([dgp, int(n)])
        else:
            inconclusive.append([dgp, int(n)])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"  # any contradicting cell is enough to withhold confirmation
    return H1Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


def h2_conditioning_size_bins(exploded: pd.DataFrame, bin_count: int) -> pd.DataFrame:
    """Per (dgp, conditioning_size_used) -- pooled across N, since H2
    asks a coarser question than H1's own per-(dgp, N) grain and
    conditioning_size_used cells are otherwise sparse -- the same
    margin-decile bin table Stage 8a's own reporting produces,
    reusing that machinery by relabeling "n" as conditioning_size_used."""
    false_edges = _false_edges_with_diagnostics(exploded)
    false_edges["motif"] = false_edges["dgp"]
    false_edges["n"] = false_edges["conditioning_size_used"]
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    false_edges["bin"] = pd.cut(false_edges["margin"], bins=edges, include_lowest=True, labels=False)
    return bin_table(false_edges, bin_count)


@dataclass(frozen=True)
class H2Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    monotonicity_by_conditioning_size: dict[str, bool]
    ece_by_conditioning_size: dict[str, float]


def evaluate_h2(bins: pd.DataFrame, small_sizes: tuple[int, ...] = (0, 1), large_sizes: tuple[int, ...] = (3, 4)) -> H2Verdict:
    """CONFIRMED if monotonicity holds (or ECE is materially lower) at
    small conditioning sizes and fails (or ECE is materially higher)
    at large ones, for every dgp with data at both. INCONCLUSIVE if
    either side lacks data to compare."""
    monotonic = check_monotonicity(bins)
    ece = compute_ece(bins)

    dgps = {dgp for dgp, _ in monotonic}
    supporting, contradicting, inconclusive = [], [], []
    for dgp in dgps:
        small_ece = [ece[(dgp, s)] for s in small_sizes if (dgp, s) in ece and ece[(dgp, s)] == ece[(dgp, s)]]
        large_ece = [ece[(dgp, s)] for s in large_sizes if (dgp, s) in ece and ece[(dgp, s)] == ece[(dgp, s)]]
        large_monotonic = [monotonic[(dgp, s)] for s in large_sizes if (dgp, s) in monotonic]
        if not small_ece or not large_ece:
            inconclusive.append(dgp)
            continue
        large_broke_monotonicity = any(not ok for ok in large_monotonic)
        large_ece_worse = min(large_ece) > max(small_ece)
        if large_broke_monotonicity or large_ece_worse:
            supporting.append(dgp)
        else:
            contradicting.append(dgp)

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"

    return H2Verdict(
        status=status,
        monotonicity_by_conditioning_size={f"{dgp}_size{size}": ok for (dgp, size), ok in monotonic.items()},
        ece_by_conditioning_size={f"{dgp}_size{size}": v for (dgp, size), v in ece.items()},
    )


def run_stage8d_diagnosis(raw_path: Path, output_dir: Path, bin_count: int = 10) -> tuple[H1Verdict, H2Verdict]:
    raw = pd.read_csv(raw_path)
    exploded = explode_edges(raw)
    if "cap_reached" not in exploded.columns or exploded["cap_reached"].isna().all():
        raise ValueError(
            f"{raw_path} has no cap_reached data -- it predates Stage 8c's own "
            "conditioning_size_used/cap_reached enrichment (see stage8c_composed_calibration.py); "
            "re-run Stage 8c to produce enriched evidence before running this diagnosis"
        )

    h1_table = h1_cap_reached_table(exploded, bin_count)
    h1_verdict = evaluate_h1(h1_table)
    h2_bins = h2_conditioning_size_bins(exploded, bin_count)
    h2_verdict = evaluate_h2(h2_bins)

    output_dir.mkdir(parents=True, exist_ok=True)
    h1_table.to_csv(output_dir / "h1_cap_reached_table.csv", index=False)
    h2_bins.to_csv(output_dir / "h2_conditioning_size_bins.csv", index=False)
    (output_dir / "h1_verdict.json").write_text(json.dumps(asdict(h1_verdict), indent=2) + "\n", encoding="utf-8")
    (output_dir / "h2_verdict.json").write_text(json.dumps(asdict(h2_verdict), indent=2) + "\n", encoding="utf-8")
    return h1_verdict, h2_verdict
