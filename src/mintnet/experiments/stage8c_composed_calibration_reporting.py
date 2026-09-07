"""Explodes Stage 8c's own per-replicate raw evidence (one row per
replicate, edges embedded as JSON -- see stage8c_composed_calibration.py's
own module docstring) into a long per-edge table, then reuses Stage
8a's own bin/monotonicity/ECE machinery -- unchanged, just grouped by
DGP instead of motif family -- for the gated true-edge check and the
descriptive false-edge comparison. See docs/stage8c_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from mintnet.confidence.recalibration import calibrated_margin, fit_isotonic_curve
from mintnet.experiments.stage8a_calibration_reporting import bin_table, check_monotonicity, compute_ece

if TYPE_CHECKING:
    from mintnet.experiments.stage8c_composed_calibration import Stage8cConfig


def explode_edges(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (dgp, n, replicate, edge) -- only from replicates
    that ran successfully; a replicate whose own screening/pruning
    itself errored contributes no edge rows (its failure is still
    visible in `raw`'s own `status` column)."""
    rows: list[dict[str, object]] = []
    for record in raw.loc[raw["status"] == "ok"].itertuples(index=False):
        for edge in json.loads(record.edges_json):
            rows.append(
                {
                    "dgp": record.dgp, "n": record.n, "replicate": record.replicate,
                    "i": edge["i"], "j": edge["j"], "is_true_edge": edge["is_true_edge"],
                    "decisive_p_value": edge["decisive_p_value"], "margin": edge["margin"],
                    "retained": edge["retained"], "correct": edge["correct"], "status": "ok",
                }
            )
    return pd.DataFrame(rows)


def _bin_edges(exploded: pd.DataFrame, is_true_edge: bool, bin_count: int) -> pd.DataFrame:
    scored = exploded.loc[
        (exploded["status"] == "ok") & exploded["margin"].notna() & (exploded["is_true_edge"] == is_true_edge)
    ].copy()
    scored["motif"] = scored["dgp"]
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    scored["bin"] = pd.cut(scored["margin"], bins=edges, include_lowest=True, labels=False)
    return bin_table(scored, bin_count)


@dataclass(frozen=True)
class Stage8cDecision:
    status: str  # "PROCEED" or "REASSESS" -- gated on true-edge calibration only
    ece_tolerance: float
    true_edge_monotonicity_violations: list[list[object]]
    true_edge_ece_by_cell: dict[str, float]
    max_true_edge_ece: float
    false_edge_ece_by_cell: dict[str, float]
    false_edge_monotonicity_violations: list[list[object]]


def evaluate_stage8c_gate(exploded: pd.DataFrame, config: "Stage8cConfig") -> tuple[Stage8cDecision, pd.DataFrame, pd.DataFrame]:
    true_bins = _bin_edges(exploded, is_true_edge=True, bin_count=config.bin_count)
    false_bins = _bin_edges(exploded, is_true_edge=False, bin_count=config.bin_count)

    true_monotonic = check_monotonicity(true_bins)
    true_ece = compute_ece(true_bins)
    false_monotonic = check_monotonicity(false_bins)
    false_ece = compute_ece(false_bins)

    true_violations = [[dgp, int(n)] for (dgp, n), ok in true_monotonic.items() if not ok]
    max_true_ece = max((v for v in true_ece.values() if v == v), default=float("nan"))
    status = "PROCEED" if (not true_violations and max_true_ece <= config.ece_tolerance) else "REASSESS"

    decision = Stage8cDecision(
        status=status,
        ece_tolerance=config.ece_tolerance,
        true_edge_monotonicity_violations=true_violations,
        true_edge_ece_by_cell={f"{dgp}_n{n}": v for (dgp, n), v in true_ece.items()},
        max_true_edge_ece=max_true_ece,
        false_edge_ece_by_cell={f"{dgp}_n{n}": v for (dgp, n), v in false_ece.items()},
        false_edge_monotonicity_violations=[[dgp, int(n)] for (dgp, n), ok in false_monotonic.items() if not ok],
    )
    return decision, true_bins, false_bins


def exploratory_false_edge_recalibration(
    exploded: pd.DataFrame, config: "Stage8cConfig"
) -> dict[str, float]:
    """Descriptive only (see docs/stage8c_charter.md's own question 2)
    -- fits a FRESH isotonic curve per (dgp, n) directly on this
    charter's own false-edge development replicates (never D-067's own
    chain/fork curve, which has no valid motif-family label to apply
    here), validated on a disjoint held-out half. Returns validation
    ECE per (dgp, n) cell; does not gate anything and is not deployed."""
    false_edges = exploded.loc[(exploded["status"] == "ok") & (~exploded["is_true_edge"]) & exploded["margin"].notna()]
    dev_low, dev_high = config.development_replicates
    val_low, val_high = config.validation_replicates
    development = false_edges.loc[(false_edges["replicate"] >= dev_low) & (false_edges["replicate"] <= dev_high)]
    validation = false_edges.loc[(false_edges["replicate"] >= val_low) & (false_edges["replicate"] <= val_high)].copy()

    curves = {}
    for (dgp, n), group in development.groupby(["dgp", "n"]):
        curves[(dgp, int(n))] = fit_isotonic_curve(
            group["margin"].to_numpy(dtype=float), group["correct"].to_numpy(dtype=float)
        )

    validation["recalibrated"] = [
        calibrated_margin(margin, int(n), dgp, curves=curves)
        for margin, n, dgp in zip(validation["margin"], validation["n"], validation["dgp"])
    ]
    relabeled = validation.rename(columns={"dgp": "motif"})
    relabeled["margin"] = relabeled["recalibrated"]
    edges = np.linspace(0.0, 1.0, config.bin_count + 1)
    relabeled["bin"] = pd.cut(relabeled["margin"], bins=edges, include_lowest=True, labels=False)
    bins = bin_table(relabeled, config.bin_count)
    ece = compute_ece(bins)
    return {f"{dgp}_n{n}": v for (dgp, n), v in ece.items()}


def write_report(raw: pd.DataFrame, config: "Stage8cConfig", output_dir: Path) -> Stage8cDecision:
    exploded = explode_edges(raw)
    exploded.to_csv(output_dir / "exploded_edges.csv", index=False)

    decision, true_bins, false_bins = evaluate_stage8c_gate(exploded, config)
    true_bins.to_csv(output_dir / "true_edge_bin_table.csv", index=False)
    false_bins.to_csv(output_dir / "false_edge_bin_table.csv", index=False)

    exploratory = exploratory_false_edge_recalibration(exploded, config)
    (output_dir / "exploratory_false_edge_recalibration_ece.json").write_text(
        json.dumps(exploratory, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "decision.json").write_text(json.dumps(asdict(decision), indent=2) + "\n", encoding="utf-8")
    return decision
