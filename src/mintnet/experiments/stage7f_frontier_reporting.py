"""Frontier table (Part A) and confidence-score verification (Part B)
for Stage 7f's own raw evidence. See docs/stage7f_charter.md.

Both re-derive everything from the raw `decisive_p_value` columns
`stage7f_frontier.py` stores once per replicate -- no new significance
tests, mirroring D-065's own free re-analysis technique.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from mintnet.confidence.margin import edge_margin

if TYPE_CHECKING:
    from mintnet.experiments.stage7f_frontier import Stage7fConfig

# D-065's own frozen fine-grained grid, reused unchanged.
ALPHA_GRID: tuple[float, ...] = tuple(round(0.05 + 0.01 * step, 2) for step in range(31))  # .05 .. .35

_TRUE_EDGE_PAIRS = {
    "chain": {(0, 1): True, (0, 2): False, (1, 2): True},
    "fork": {(0, 1): True, (0, 2): False, (1, 2): True},
    "triangle": {(0, 1): True, (0, 2): True, (1, 2): True},
}

# Part B's own single canonical alpha -- a moderate, disclosed value
# within the historically-relevant D-064/D-065 window, not tuned to
# produce a favorable result (chosen before this module saw any
# evidence, per this charter's own frozen status).
_CANONICAL_ALPHA = 0.10


def _decisions_at_alpha(raw: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """One row per (condition, n, replicate, pair): retained, is_true_edge,
    correct, confidence -- at the given alpha. Excludes error rows."""
    ok = raw.loc[raw["status"] == "ok"].copy()
    frames = []
    for suffix, pair in ((("01"), (0, 1)), (("02"), (0, 2)), (("12"), (1, 2))):
        column = f"decisive_p_value_{suffix}"
        frame = ok[["condition", "motif", "index", "n", "replicate", column]].copy()
        frame = frame.rename(columns={column: "p_value"})
        frame["pair"] = [pair] * len(frame)
        frame["is_true_edge"] = frame["motif"].map(lambda motif, pair=pair: _TRUE_EDGE_PAIRS[motif][pair])
        frame["retained"] = frame["p_value"] <= alpha
        frame["correct"] = frame["retained"] == frame["is_true_edge"]
        frame["confidence"] = [
            edge_margin(p, alpha, retained=bool(r)) for p, r in zip(frame["p_value"], frame["retained"])
        ]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _cell_metrics(decisions: pd.DataFrame) -> pd.DataFrame:
    """Per (condition, n): indirect_prune_tpr (chain/fork) or
    true_edge_retention_rate (triangle) -- mirrors mintnet.metrics.
    topology.score_motif's own definitions, aggregated over replicates
    rather than computed per-replicate-matrix."""
    rows = []
    for (condition, motif, index, n), group in decisions.groupby(["condition", "motif", "index", "n"]):
        if motif == "triangle":
            true_edge_fpr = float((~group["retained"]).mean())
            rows.append({"condition": condition, "motif": motif, "index": index, "n": n, "true_edge_fpr": true_edge_fpr})
        else:
            indirect = group.loc[group["pair"].apply(lambda p: p == (0, 2))]
            indirect_prune_tpr = float((~indirect["retained"]).mean())
            rows.append(
                {"condition": condition, "motif": motif, "index": index, "n": n, "indirect_prune_tpr": indirect_prune_tpr}
            )
    return pd.DataFrame(rows)


def frontier_table(
    raw: pd.DataFrame, config: "Stage7fConfig", *, min_tpr: float = 0.80, max_fpr: float = 0.10
) -> pd.DataFrame:
    """Part A's own primary deliverable: for every (n, target_rho), does
    ANY alpha in ALPHA_GRID satisfy min_tpr on every chain/fork strength
    cell AND max_fpr on this specific triangle's own true-edge FPR,
    simultaneously, at this n? Mirrors D-065's own gate criteria exactly."""
    rows = []
    for n in config.sample_sizes:
        chain_fork_tpr_by_alpha: dict[float, float] = {}
        for alpha in ALPHA_GRID:
            decisions = _decisions_at_alpha(raw.loc[(raw["n"] == n) & (raw["motif"] != "triangle")], alpha)
            metrics = _cell_metrics(decisions)
            chain_fork_tpr_by_alpha[alpha] = float(metrics["indirect_prune_tpr"].min()) if len(metrics) else float("nan")

        for target_rho_index, target_rho in enumerate(config.target_rhos):
            condition = f"triangle_{target_rho_index}"
            feasible_alphas = []
            for alpha in ALPHA_GRID:
                decisions = _decisions_at_alpha(
                    raw.loc[(raw["n"] == n) & (raw["condition"] == condition)], alpha
                )
                metrics = _cell_metrics(decisions)
                triangle_fpr = float(metrics["true_edge_fpr"].iloc[0]) if len(metrics) else float("nan")
                if chain_fork_tpr_by_alpha[alpha] >= min_tpr and triangle_fpr <= max_fpr:
                    feasible_alphas.append(alpha)
            rows.append(
                {
                    "n": n, "target_rho": target_rho, "feasible": bool(feasible_alphas),
                    "window_low": min(feasible_alphas) if feasible_alphas else float("nan"),
                    "window_high": max(feasible_alphas) if feasible_alphas else float("nan"),
                    "n_feasible_alphas": len(feasible_alphas),
                }
            )
    return pd.DataFrame(rows)


def smallest_resolvable_target_rho(table: pd.DataFrame) -> pd.DataFrame:
    """Per N, the smallest tested target_rho with feasible=True -- NaN
    if none tested resolves at that N."""
    rows = []
    for n, group in table.groupby("n"):
        feasible = group.loc[group["feasible"]]
        rows.append({"n": n, "smallest_resolvable_target_rho": float(feasible["target_rho"].min()) if len(feasible) else float("nan")})
    return pd.DataFrame(rows).sort_values("n").reset_index(drop=True)


@dataclass(frozen=True)
class ConfidenceVerification:
    """Part B's own gate: at every tested N, is the exposed confidence
    score actually informative (correct decisions score higher than
    incorrect ones, on average) at the canonical alpha, and does the
    frontier-relevant true edge's own average confidence increase with
    N? Both computed directly from ground truth, not assumed."""

    canonical_alpha: float
    informative_at_every_n: bool
    mean_confidence_by_n_and_correctness: list[dict[str, object]]
    frontier_edge_mean_confidence_by_n: list[dict[str, object]]
    monotonic_with_n: bool
    status: str  # "PROCEED" or "REASSESS"


def verify_confidence_score(raw: pd.DataFrame, config: "Stage7fConfig") -> ConfidenceVerification:
    decisions = _decisions_at_alpha(raw, _CANONICAL_ALPHA)

    by_n_correctness = []
    informative_at_every_n = True
    for n, group in decisions.groupby("n"):
        correct_mean = float(group.loc[group["correct"], "confidence"].mean())
        incorrect = group.loc[~group["correct"], "confidence"]
        incorrect_mean = float(incorrect.mean()) if len(incorrect) else float("nan")
        by_n_correctness.append(
            {"n": int(n), "mean_confidence_correct": correct_mean, "mean_confidence_incorrect": incorrect_mean}
        )
        if not np.isnan(incorrect_mean) and not (correct_mean > incorrect_mean):
            informative_at_every_n = False

    # Frontier-relevant edge: the weakest triangle pair (1, 2) at the
    # smallest tested target_rho -- the case closest to the detection
    # floor, where an N-dependent confidence trend matters most.
    smallest_rho_index = int(np.argmin(config.target_rhos))
    frontier_condition = f"triangle_{smallest_rho_index}"
    frontier_decisions = decisions.loc[
        (decisions["condition"] == frontier_condition) & (decisions["pair"].apply(lambda p: p == (1, 2)))
    ]
    by_n_frontier = []
    for n, group in frontier_decisions.groupby("n"):
        by_n_frontier.append({"n": int(n), "mean_confidence": float(group["confidence"].mean())})
    by_n_frontier.sort(key=lambda row: row["n"])
    monotonic_with_n = all(
        by_n_frontier[i + 1]["mean_confidence"] >= by_n_frontier[i]["mean_confidence"] - 1e-9
        for i in range(len(by_n_frontier) - 1)
    )

    status = "PROCEED" if informative_at_every_n and monotonic_with_n else "REASSESS"
    return ConfidenceVerification(
        canonical_alpha=_CANONICAL_ALPHA,
        informative_at_every_n=informative_at_every_n,
        mean_confidence_by_n_and_correctness=by_n_correctness,
        frontier_edge_mean_confidence_by_n=by_n_frontier,
        monotonic_with_n=monotonic_with_n,
        status=status,
    )


def write_report(raw: pd.DataFrame, config: "Stage7fConfig", output_dir: Path) -> ConfidenceVerification:
    table = frontier_table(raw, config)
    smallest = smallest_resolvable_target_rho(table)
    verification = verify_confidence_score(raw, config)

    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "frontier_table.csv", index=False)
    smallest.to_csv(output_dir / "smallest_resolvable_target_rho.csv", index=False)
    (output_dir / "confidence_verification.json").write_text(
        json.dumps(asdict(verification), indent=2) + "\n", encoding="utf-8"
    )
    return verification
