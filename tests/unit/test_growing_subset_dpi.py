import math

import numpy as np

from mintnet.dpi.multi_conditional import compute_partial_correlation_evidence
from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi
from mintnet.simulation.motifs import sample_hub, sample_overlapping_triangles


def test_growing_subset_dpi_isolated_edge_passes_through_unconditioned() -> None:
    rng = np.random.default_rng(0)
    data = rng.normal(size=(500, 4))
    flagged = np.zeros((4, 4), dtype=bool)
    flagged[0, 1] = flagged[1, 0] = True  # only candidate edge, no other component members

    result = growing_subset_dpi(data, flagged, alpha=0.001)

    assert result.adjacency[0, 1] and result.adjacency[1, 0]
    assert result.conditioning_size_used[(0, 1)] == 0
    assert not result.cap_reached[(0, 1)]
    assert math.isnan(result.decisive_p_value[(0, 1)])


def test_growing_subset_dpi_decisive_p_value_for_pruned_edge_is_the_triggering_test() -> None:
    """A pruned edge's decisive_p_value must be exactly the p-value the
    OR-rule search stopped on, not some other subset's own p-value."""
    rng = np.random.default_rng(1)
    data = sample_hub(2000, 0.5, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi(data, flagged, alpha=0.01)

    for pair in ((1, 2), (1, 3), (2, 3)):
        assert not result.adjacency[pair]
        # pool is sorted ascending and node 0 (the hub) is always its
        # smallest member for these pairs, so subset (0,) is always the
        # first -- and, since conditioning on the true hub immediately
        # reveals independence, the only -- subset tested.
        expected = compute_partial_correlation_evidence(data, pair[0], pair[1], (0,)).p_value
        assert result.decisive_p_value[pair] == expected
        assert result.decisive_p_value[pair] > 0.01


def test_growing_subset_dpi_decisive_p_value_for_retained_edge_is_the_maximum_tested() -> None:
    """A retained edge's decisive_p_value must be the largest p-value
    among every subset actually tested (the weakest evidence for
    independence, i.e. the one closest to overturning retention), not
    the first or the smallest."""
    rng = np.random.default_rng(2)
    data = sample_overlapping_triangles(3000, rng)
    flagged = np.ones((5, 5), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi(data, flagged, alpha=0.01)

    true_edges = {(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)}
    for pair in true_edges:
        assert result.adjacency[pair]
        assert not math.isnan(result.decisive_p_value[pair])
        assert result.decisive_p_value[pair] <= 0.01


def test_growing_subset_dpi_prunes_indirect_hub_edges_at_size_one() -> None:
    rng = np.random.default_rng(1)
    data = sample_hub(2000, 0.5, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi(data, flagged, alpha=0.01)

    assert result.adjacency[0, 1] and result.adjacency[0, 2] and result.adjacency[0, 3]
    assert not result.adjacency[1, 2] and not result.adjacency[1, 3] and not result.adjacency[2, 3]
    for pair in ((1, 2), (1, 3), (2, 3)):
        assert result.conditioning_size_used[pair] == 1


def test_growing_subset_dpi_recovers_overlapping_triangle_structure() -> None:
    rng = np.random.default_rng(2)
    data = sample_overlapping_triangles(3000, rng)
    flagged = np.ones((5, 5), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi(data, flagged, alpha=0.01)

    true_edges = {(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)}
    for i in range(5):
        for j in range(i + 1, 5):
            expected = (i, j) in true_edges
            assert bool(result.adjacency[i, j]) == expected, f"pair ({i},{j})"


def test_growing_subset_dpi_respects_max_conditioning_size_cap() -> None:
    rng = np.random.default_rng(3)
    data = rng.normal(size=(500, 8))
    flagged = np.ones((8, 8), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi(data, flagged, alpha=1.0, max_conditioning_size=2)

    for pair, size in result.conditioning_size_used.items():
        assert size <= 2
    # alpha=1.0 means no subset ever prunes (p_value > 1.0 is never
    # true), so every pair exhausts the cap with a 6-node remaining pool
    assert all(result.cap_reached.values())
