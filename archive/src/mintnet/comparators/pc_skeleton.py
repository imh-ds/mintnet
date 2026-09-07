"""Native implementation of the PC algorithm's skeleton phase only
(PC-stable, Colombo & Maathuis 2014) -- no orientation phase. See
docs/stage5e_charter.md for why the orientation phase is deliberately
never implemented here, not merely unused.

Reuses `mintnet.dpi.multi_conditional.compute_partial_correlation_evidence`,
the same exact-for-Gaussian-data Fisher-z partial-correlation test
MINT's own screening/DPI steps use, so the comparator and MINT share
one tested statistical primitive rather than two independent
implementations of the same math.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from mintnet.dpi.multi_conditional import compute_partial_correlation_evidence


@dataclass(frozen=True)
class PCSkeletonResult:
    adjacency: np.ndarray
    n_edges: int
    max_conditioning_set_size: int


def fit_pc_skeleton(data: np.ndarray, *, alpha: float = 0.01) -> PCSkeletonResult:
    """PC-stable skeleton recovery: iteratively test conditional
    independence of each still-adjacent pair over growing-size subsets
    of its own endpoints' adjacency sets, removing an edge as soon as
    any tested subset fails to reject independence. Adjacency sets used
    for conditioning are fixed at the start of each level (the "stable"
    fix -- order-independent results, not updated mid-level), and both
    endpoints' own neighbor sets are checked per pair (canonical PC
    behavior, not just one arbitrary direction). No orientation step;
    the returned adjacency is undirected and symmetric."""
    n, p = data.shape
    adjacency = np.ones((p, p), dtype=bool)
    np.fill_diagonal(adjacency, False)

    ell = 0
    max_ell_with_removal = 0
    while True:
        neighbors = {i: set(np.flatnonzero(adjacency[i]).tolist()) for i in range(p)}
        any_tested = False
        edges_to_remove: set[tuple[int, int]] = set()
        for i in range(p):
            for j in range(i + 1, p):
                if not adjacency[i, j]:
                    continue
                independent = False
                for a, b in ((i, j), (j, i)):
                    candidates = neighbors[a] - {b}
                    if len(candidates) < ell:
                        continue
                    any_tested = True
                    for subset in combinations(sorted(candidates), ell):
                        try:
                            evidence = compute_partial_correlation_evidence(data, i, j, subset)
                        except ValueError:
                            # Degenerate conditioning set (e.g. collinearity):
                            # inconclusive, not evidence of independence --
                            # try the next subset rather than removing the edge.
                            continue
                        if evidence.p_value > alpha:
                            independent = True
                            break
                    if independent:
                        break
                if independent:
                    edges_to_remove.add((i, j))
        if edges_to_remove:
            max_ell_with_removal = ell
        for i, j in edges_to_remove:
            adjacency[i, j] = False
            adjacency[j, i] = False
        if not any_tested:
            break
        ell += 1

    n_edges = int(np.triu(adjacency, k=1).sum())
    return PCSkeletonResult(
        adjacency=adjacency,
        n_edges=n_edges,
        max_conditioning_set_size=max_ell_with_removal,
    )
