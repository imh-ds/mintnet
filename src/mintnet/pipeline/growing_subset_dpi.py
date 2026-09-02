"""PC-style growing-conditioning-set DPI, run on MINT's own screened
candidate graph as the starting adjacency (not PC's from-scratch
complete graph). Additive alternative to
`mintnet.pipeline.compose.compose_screen_then_prune` -- does not
modify it, and both remain available for direct comparison. See
docs/stage6a_charter.md.

Applies to every connected component of the screened candidate graph,
not just validated 3/4/5-node clique shapes -- the scope extension
docs/decision_log.md D-052 identified as a concrete candidate fix for
MINT's own passthrough-unconditioned false positives.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from mintnet.dpi.multi_conditional import compute_partial_correlation_evidence
from mintnet.pipeline.compose import connected_components


@dataclass(frozen=True)
class GrowingSubsetResult:
    adjacency: np.ndarray
    # Per candidate edge (i < j): the conditioning-set size that
    # determined its final retain/prune decision. 0 means the edge's
    # component had no other members (an isolated two-node component,
    # retained unconditionally -- the same case that passes through
    # untested in compose_screen_then_prune).
    conditioning_size_used: dict[tuple[int, int], int]
    # Per candidate edge: True if the search-depth cap was reached
    # while the component still had untested larger subsets available
    # (a disclosed bound, see docs/stage6a_charter.md's own non-goals;
    # reported so it is never silently absorbed into "retain").
    cap_reached: dict[tuple[int, int], bool]


def growing_subset_dpi(
    data: np.ndarray, flagged: np.ndarray, alpha: float, *, max_conditioning_size: int = 4
) -> GrowingSubsetResult:
    """Prune a candidate edge as soon as any tested conditioning subset
    (drawn from its own connected component, growing from size 1) fails
    to reject independence; retain it only if every subset up to the
    cap rejects. The same OR-rule the Stage 5e PC comparator already
    uses, applied to MINT's own screened graph instead of a from-scratch
    complete graph."""
    p = flagged.shape[0]
    final = flagged.copy()
    sizes: dict[tuple[int, int], int] = {}
    cap_reached: dict[tuple[int, int], bool] = {}

    node_to_component: dict[int, frozenset[int]] = {}
    for component in connected_components(flagged):
        for node in component:
            node_to_component[node] = component

    for i in range(p):
        for j in range(i + 1, p):
            if not flagged[i, j]:
                continue
            component = node_to_component.get(i, frozenset())
            pool = sorted(component - {i, j})

            if not pool:
                final[i, j] = final[j, i] = True
                sizes[(i, j)] = 0
                cap_reached[(i, j)] = False
                continue

            cap = min(len(pool), max_conditioning_size)
            pruned = False
            reached_size = 0
            for size in range(1, cap + 1):
                reached_size = size
                for subset in combinations(pool, size):
                    try:
                        evidence = compute_partial_correlation_evidence(data, i, j, subset)
                    except ValueError:
                        # Degenerate conditioning set: inconclusive, not
                        # evidence of independence -- try the next subset.
                        continue
                    if evidence.p_value > alpha:
                        pruned = True
                        break
                if pruned:
                    break

            final[i, j] = final[j, i] = not pruned
            sizes[(i, j)] = reached_size
            cap_reached[(i, j)] = (not pruned) and (len(pool) > max_conditioning_size)

    return GrowingSubsetResult(adjacency=final, conditioning_size_used=sizes, cap_reached=cap_reached)
