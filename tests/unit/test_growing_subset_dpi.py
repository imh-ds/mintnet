import numpy as np

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
