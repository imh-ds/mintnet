"""Wires `growing_subset_dpi` together with Tier-1 bootstrap-stability
into a single, opt-in pipeline feature. See docs/stage9b_charter.md.

Purely additive: does not modify `growing_subset_dpi`'s own default
behavior or return type. A caller must explicitly call this new
function to get stability-rescue behavior at all.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi

# Imported lazily inside the function below, not at module level: mintnet.
# bootstrap.stability imports from mintnet.pipeline (for compose_screen_
# then_prune/growing_subset_dpi), so an eager import here would close a
# circular dependency between the two packages. That cycle happens to
# resolve fine for a normal single-process import, but breaks a spawned
# multiprocessing worker (n_jobs > 1), which re-imports each module fresh
# with no cached partial state to fall back on.

# D-076's own boundary: growing_subset_dpi's own prune decisions are
# reliable at conditioning_size_used <= 1 and genuinely unreliable (not
# merely miscalibrated) at >= 2 -- only edges at or above this boundary
# are ever bootstrapped.
UNRESOLVED_CONDITIONING_SIZE = 2


@dataclass(frozen=True)
class StabilityRescueResult:
    """Per candidate edge (`flagged[i, j]`): the original `growing_
    subset_dpi` decision, the possibly-corrected final decision, and
    the bootstrap evidence behind any correction -- fully transparent,
    never a silent override.
    """

    # growing_subset_dpi's own unmodified decision.
    original_adjacency: np.ndarray
    # Identical to original_adjacency except any edge with
    # conditioning_size_used >= UNRESOLVED_CONDITIONING_SIZE whose own
    # pi_final fell below pi_min is flipped to pruned.
    final_adjacency: np.ndarray
    conditioning_size_used: dict[tuple[int, int], int]
    # Bootstrap edge stability (D-019's/D-077's own pi_final) for every
    # bootstrapped edge; NaN for edges never bootstrapped (conditioning_
    # size_used < UNRESOLVED_CONDITIONING_SIZE, or an isolated edge).
    pi_final: dict[tuple[int, int], float]
    # True only for an edge the filter actually flipped (was retained,
    # pi_final < pi_min) -- False for every edge left unchanged,
    # including every non-bootstrapped one.
    rescued: dict[tuple[int, int], bool]
    # Whether this dataset triggered even one bootstrap run at all --
    # False means this call cost the same as plain growing_subset_dpi.
    bootstrapped: bool


def growing_subset_dpi_with_stability_rescue(
    data: np.ndarray,
    flagged: np.ndarray,
    alpha: float,
    *,
    max_conditioning_size: int = 4,
    motif_family: str | None = None,
    screening_alpha: float,
    bootstraps: int = 500,
    pi_min: float = 0.90,
    rng: np.random.Generator,
    n_jobs: int = 1,
) -> StabilityRescueResult:
    """Run `growing_subset_dpi` once, then bootstrap ONLY the edges
    whose own `conditioning_size_used >= UNRESOLVED_CONDITIONING_SIZE`
    (D-076's own unresolved boundary) -- a dataset with no such edge
    never pays the `bootstraps`-resample cost at all. A single
    `compute_edge_stability_growing_subset` call already returns the
    full `p x p` `pi_final` matrix, so a dataset with multiple
    qualifying edges pays that cost once, not once per edge (Stage 9a's
    own already-validated efficiency design).

    `pi_min=0.90` is D-079's own selected threshold (deliberately
    stricter than the calibration procedure's own smallest-eligible
    default of `0.70` -- see docs/decision_log.md D-079), not
    re-derived here.

    `n_jobs` (default `1`, sequential) is forwarded to `compute_edge_
    stability_growing_subset` -- distributes the `bootstraps`-resample
    compute (D-080's own measured cost: `~80-280s` sequentially per
    qualifying dataset) across local worker processes when a dataset
    does qualify. Purely a wall-clock optimization: the resample draw
    order from `rng` is unaffected by `n_jobs`, so `pi_final` (and
    therefore every downstream decision this function makes) is
    bit-for-bit identical regardless of `n_jobs`.
    """
    from mintnet.bootstrap import compute_edge_stability_growing_subset

    p = flagged.shape[0]
    result = growing_subset_dpi(
        data, flagged, alpha, max_conditioning_size=max_conditioning_size, motif_family=motif_family
    )

    qualifying: list[tuple[int, int]] = [
        (i, j)
        for i in range(p)
        for j in range(i + 1, p)
        if flagged[i, j] and result.conditioning_size_used[(i, j)] >= UNRESOLVED_CONDITIONING_SIZE
    ]

    pi_final: dict[tuple[int, int], float] = {}
    rescued: dict[tuple[int, int], bool] = {}
    final_adjacency = result.adjacency.copy()
    bootstrapped = bool(qualifying)

    if qualifying:
        stability = compute_edge_stability_growing_subset(
            data, screening_alpha, alpha, max_conditioning_size, bootstraps, rng, n_jobs=n_jobs
        )
        for i, j in qualifying:
            value = float(stability.pi_final[i, j])
            pi_final[(i, j)] = value
            flip = bool(result.adjacency[i, j]) and value < pi_min
            rescued[(i, j)] = flip
            if flip:
                final_adjacency[i, j] = final_adjacency[j, i] = False

    for i in range(p):
        for j in range(i + 1, p):
            if not flagged[i, j]:
                continue
            if (i, j) not in pi_final:
                pi_final[(i, j)] = math.nan
                rescued[(i, j)] = False

    return StabilityRescueResult(
        original_adjacency=result.adjacency,
        final_adjacency=final_adjacency,
        conditioning_size_used=result.conditioning_size_used,
        pi_final=pi_final,
        rescued=rescued,
        bootstrapped=bootstrapped,
    )
