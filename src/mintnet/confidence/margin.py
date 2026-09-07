"""Tier-0 confidence score: decision-boundary distance for a DPI edge
decision, computed for free from a p-value the pipeline already
produces. See docs/stage8a_charter.md. Informative until this
charter's own calibration check resolves; do not present as a
literal probability until then.
"""

from __future__ import annotations

import math

from mintnet.pipeline.growing_subset_dpi import GrowingSubsetResult


def edge_margin(p_value: float, alpha: float, *, retained: bool) -> float:
    """Distance from the alpha decision boundary, in [0, 1], in
    whichever direction the decision went. 0 at the boundary (a coin
    flip); 1 at maximum distance from it. NaN in, NaN out -- an edge
    with no valid decisive p-value (isolated, or every tested subset
    was degenerate) has no margin to report."""
    if math.isnan(p_value):
        return math.nan
    if retained:
        return (alpha - p_value) / alpha
    return (p_value - alpha) / (1 - alpha)


def edge_margins(result: GrowingSubsetResult, alpha: float) -> dict[tuple[int, int], float]:
    """Margin score for every candidate edge in a growing_subset_dpi
    result, keyed the same way as its own decisive_p_value."""
    return {
        pair: edge_margin(p_value, alpha, retained=bool(result.adjacency[pair]))
        for pair, p_value in result.decisive_p_value.items()
    }
