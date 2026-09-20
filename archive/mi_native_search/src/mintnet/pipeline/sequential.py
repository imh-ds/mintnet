"""Sequential/greedy conditioning engine. See docs/stage4a_charter.md.

Builds the final adjacency matrix by ranking candidate pairs by marginal
association strength and testing each, strongest first, against
already-confirmed neighbors -- rather than requiring every pair in a
connected component to be simultaneously flagged before any conditioning
test runs (`mintnet.pipeline.compose_screen_then_prune`'s design). This
is a second, independently validated engine, not a replacement for the
conservative one: see
`outline/information_network_technical_build_plan_v3_2026-08-30.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from mintnet.dpi.multi_conditional import compute_partial_correlation_evidence
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected


@dataclass(frozen=True)
class PairDecision:
    """Diagnostic record of one candidate pair's sequential processing."""

    i: int
    j: int
    rank_z: float
    tested_neighbors: tuple[int, ...]
    neighbor_p_values: tuple[float, ...] = field(default_factory=tuple)
    confirmed: bool = False


def sequential_screen_and_prune_detailed(data: np.ndarray, alpha: float) -> tuple[np.ndarray, list[PairDecision]]:
    """Rank-then-condition sequential pruning, using one alpha for both the
    initial marginal candidacy test and the conditional test, per
    docs/stage4a_charter.md's frozen mechanism. Returns the final adjacency
    matrix plus a per-candidate-pair diagnostic record (processing rank,
    which already-confirmed shared neighbors were tested, their individual
    conditional p-values, and the final decision).

    Pruning is permanent: once an edge is removed because some
    already-confirmed neighbor explains it away, it is never reconsidered
    against a different neighbor or re-tested later. This one-directional
    commitment is this engine's central, deliberately un-mitigated risk in
    this charter -- Stage 4c stress-tests it directly.
    """
    if not np.isscalar(alpha) or not (0.0 < float(alpha) < 1.0):
        raise ValueError("alpha must satisfy 0 < alpha < 1")
    alpha_value = float(alpha)

    evidence = compute_pairwise_screening_evidence(data)
    flagged = screen_uncorrected(evidence, alpha_value)
    p = data.shape[1]

    candidates = [(i, j) for i in range(p) for j in range(i + 1, p) if flagged[i, j]]
    candidates.sort(key=lambda pair: abs(evidence.z_statistic[pair[0], pair[1]]), reverse=True)

    confirmed = np.zeros((p, p), dtype=bool)
    decisions: list[PairDecision] = []
    for i, j in candidates:
        rank_z = float(evidence.z_statistic[i, j])
        shared = [k for k in range(p) if k != i and k != j and confirmed[i, k] and confirmed[j, k]]
        if not shared:
            confirmed[i, j] = confirmed[j, i] = True
            decisions.append(PairDecision(i, j, rank_z, (), (), True))
            continue
        p_values = tuple(compute_partial_correlation_evidence(data, i, j, [k]).p_value for k in shared)
        explained_away = any(p_value > alpha_value for p_value in p_values)
        if not explained_away:
            confirmed[i, j] = confirmed[j, i] = True
        decisions.append(PairDecision(i, j, rank_z, tuple(shared), p_values, not explained_away))
    return confirmed, decisions


def sequential_screen_and_prune(data: np.ndarray, alpha: float) -> np.ndarray:
    """Rank-then-condition sequential pruning; final adjacency only.

    See `sequential_screen_and_prune_detailed` for the same mechanism with
    a full per-pair diagnostic trail.
    """
    confirmed, _decisions = sequential_screen_and_prune_detailed(data, alpha)
    return confirmed
