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

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np

from mintnet.confidence.margin import edge_margin
from mintnet.confidence.recalibration import calibrated_margin
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
    # Per candidate edge: the p-value the final decision actually
    # turned on (see docs/stage8a_charter.md). For a pruned edge, the
    # p-value that triggered the prune. For a retained edge with a
    # non-empty pool, the MAXIMUM p-value among every subset tested --
    # the weakest piece of evidence among those that all had to reject
    # for retention to hold, i.e. the one closest to overturning it.
    # NaN for an isolated edge (no test ever ran) or a retained edge
    # whose every tested subset raised a degenerate-conditioning-set
    # ValueError (no valid evidence obtained).
    decisive_p_value: dict[tuple[int, int], float]
    # Per candidate edge: a [0, 1] confidence score derived from
    # decisive_p_value (see docs/stage8a_charter.md's own margin
    # formula). Ordinal-only (informative, not a literal probability)
    # unless `motif_family` was passed to growing_subset_dpi AND that
    # family/N combination has a validated recalibration curve
    # (docs/stage8b_charter.md, D-067 -- currently chain/fork/triangle/
    # weak_edge_triangle only, N in [300, 3000]) -- in every other case
    # this silently falls back to the raw, uncalibrated margin, since
    # applying a recalibration curve fit on a specific synthetic DGP to
    # an edge of unknown or different structure would be exactly the
    # unvalidated generalization both charters explicitly disclaim.
    # NaN wherever decisive_p_value is NaN.
    confidence: dict[tuple[int, int], float]
    # Per candidate edge: the actual column indices of the conditioning
    # subset whose p-value became decisive_p_value (the triggering
    # subset for a pruned edge; the max-p-value subset for a retained
    # edge, see decisive_p_value's own docstring above) -- an empty
    # tuple for an isolated edge (no test ever ran), mirroring
    # decisive_p_value's own NaN convention. Already implicit in the
    # search below; this field only persists it (docs/stage8g_charter.md).
    decisive_conditioning_subset: dict[tuple[int, int], tuple[int, ...]]


def _confidence(p_value: float, alpha: float, *, retained: bool, n: int, motif_family: str | None) -> float:
    raw_margin = edge_margin(p_value, alpha, retained=retained)
    if motif_family is None or math.isnan(raw_margin):
        return raw_margin
    try:
        return calibrated_margin(raw_margin, n, motif_family)
    except ValueError:
        # Motif family unrecognized or N outside the validated range --
        # fall back to raw margin rather than raise, since confidence
        # is a diagnostic, not a value the caller's own decision depends on.
        return raw_margin


def growing_subset_dpi(
    data: np.ndarray,
    flagged: np.ndarray,
    alpha: float,
    *,
    max_conditioning_size: int = 4,
    motif_family: str | None = None,
) -> GrowingSubsetResult:
    """Prune a candidate edge as soon as any tested conditioning subset
    (drawn from its own connected component, growing from size 1) fails
    to reject independence; retain it only if every subset up to the
    cap rejects. The same OR-rule the Stage 5e PC comparator already
    uses, applied to MINT's own screened graph instead of a from-scratch
    complete graph.

    `motif_family` is optional and defaults to None (no recalibration
    attempted -- every edge's own `confidence` is the raw, ordinal-only
    margin). Only pass it when the caller genuinely knows the DGP an
    edge's own local structure matches one of the validated fitted
    labels below -- e.g. a Stage 8-style evidence runner working with
    a known synthetic fixture, not an arbitrary real network, where no
    such label is knowable:

    - `chain`, `fork`, `triangle`, `weak_edge_triangle` (D-067):
      isolated 3-node fixtures -- a local substructure a real dataset
      could at least plausibly resemble edge-by-edge.
    - `chain_fork_hub`, `overlap` (D-070): specific WHOLE-NETWORK
      (`p=15`) synthetic constructions, not a local substructure at
      all -- valid only for a caller reproducing or closely mirroring
      those exact fixtures. No real or arbitrary composed dataset can
      legitimately claim to *be* one of these DGPs the way three real
      variables might resemble an isolated chain or fork, so this pair
      is scoped even more narrowly than the first four.

    Passing any of these for real data would apply a curve fit on a
    specific synthetic null to an edge that may not resemble it at all
    -- exactly the generalization the Stage 8 charters disclaim as a
    non-goal throughout."""
    p = flagged.shape[0]
    n = data.shape[0]
    final = flagged.copy()
    sizes: dict[tuple[int, int], int] = {}
    cap_reached: dict[tuple[int, int], bool] = {}
    decisive_p_value: dict[tuple[int, int], float] = {}
    confidence: dict[tuple[int, int], float] = {}
    decisive_conditioning_subset: dict[tuple[int, int], tuple[int, ...]] = {}

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
                decisive_p_value[(i, j)] = math.nan
                confidence[(i, j)] = math.nan
                decisive_conditioning_subset[(i, j)] = ()
                continue

            cap = min(len(pool), max_conditioning_size)
            pruned = False
            reached_size = 0
            triggering_p_value = math.nan
            triggering_subset: tuple[int, ...] = ()
            max_p_value = math.nan
            max_p_subset: tuple[int, ...] = ()
            for size in range(1, cap + 1):
                reached_size = size
                for subset in combinations(pool, size):
                    try:
                        evidence = compute_partial_correlation_evidence(data, i, j, subset)
                    except ValueError:
                        # Degenerate conditioning set: inconclusive, not
                        # evidence of independence -- try the next subset.
                        continue
                    if math.isnan(max_p_value) or evidence.p_value > max_p_value:
                        max_p_value = evidence.p_value
                        max_p_subset = subset
                    if evidence.p_value > alpha:
                        pruned = True
                        triggering_p_value = evidence.p_value
                        triggering_subset = subset
                        break
                if pruned:
                    break

            final[i, j] = final[j, i] = not pruned
            sizes[(i, j)] = reached_size
            cap_reached[(i, j)] = (not pruned) and (len(pool) > max_conditioning_size)
            resolved_p_value = triggering_p_value if pruned else max_p_value
            decisive_p_value[(i, j)] = resolved_p_value
            decisive_conditioning_subset[(i, j)] = triggering_subset if pruned else max_p_subset
            confidence[(i, j)] = _confidence(
                resolved_p_value, alpha, retained=not pruned, n=n, motif_family=motif_family
            )

    return GrowingSubsetResult(
        adjacency=final,
        conditioning_size_used=sizes,
        cap_reached=cap_reached,
        decisive_p_value=decisive_p_value,
        confidence=confidence,
        decisive_conditioning_subset=decisive_conditioning_subset,
    )
