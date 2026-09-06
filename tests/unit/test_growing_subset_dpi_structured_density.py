import numpy as np

from mintnet.pipeline.growing_subset_dpi_structured_density import growing_subset_dpi_structured_density
from mintnet.simulation.motifs import sample_hub, sample_overlapping_triangles


def test_growing_subset_dpi_structured_density_isolated_edge_passes_through_unconditioned() -> None:
    rng = np.random.default_rng(0)
    data = rng.normal(size=(500, 4))
    flagged = np.zeros((4, 4), dtype=bool)
    flagged[0, 1] = flagged[1, 0] = True  # only candidate edge, no other component members

    result = growing_subset_dpi_structured_density(
        data, flagged, alpha=0.001, master_seed=1, replicate=0, permutations=19
    )

    assert result.adjacency[0, 1] and result.adjacency[1, 0]
    assert result.conditioning_size_used[(0, 1)] == 0
    assert not result.cap_reached[(0, 1)]
    assert result.n_significance_tests == 0  # isolated pair: no test needed


def test_growing_subset_dpi_structured_density_prunes_indirect_hub_edges_at_size_one() -> None:
    rng = np.random.default_rng(1)
    data = sample_hub(600, 0.8, 3, rng)  # strong signal + modest N -- fast but still cleanly separable
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi_structured_density(
        data, flagged, alpha=0.05, master_seed=2, replicate=0, permutations=19
    )

    assert result.adjacency[0, 1] and result.adjacency[0, 2] and result.adjacency[0, 3]
    assert not result.adjacency[1, 2] and not result.adjacency[1, 3] and not result.adjacency[2, 3]
    for pair in ((1, 2), (1, 3), (2, 3)):
        assert result.conditioning_size_used[pair] == 1
    assert result.n_significance_tests > 0


def test_growing_subset_dpi_structured_density_recovers_overlapping_triangle_structure() -> None:
    """|S|=3 conditioning (this shape's own pool size) is D-057's own
    documented hardest case for CMIknn's own power -- kept at the same
    elevated N/permutations this project's own CMIknn-equivalent test
    uses, not assumed cheaper just because the estimator itself is
    faster per call."""
    rng = np.random.default_rng(2)
    data = sample_overlapping_triangles(1200, rng)
    flagged = np.ones((5, 5), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi_structured_density(
        data, flagged, alpha=0.05, master_seed=3, replicate=0, permutations=49
    )

    true_edges = {(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)}
    for i in range(5):
        for j in range(i + 1, 5):
            expected = (i, j) in true_edges
            assert bool(result.adjacency[i, j]) == expected, f"pair ({i},{j})"


def test_growing_subset_dpi_structured_density_respects_max_conditioning_size_cap() -> None:
    rng = np.random.default_rng(4)
    data = rng.normal(size=(300, 6))
    flagged = np.ones((6, 6), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi_structured_density(
        data, flagged, alpha=1.0, master_seed=5, replicate=0, permutations=19, max_conditioning_size=2,
    )

    for pair, size in result.conditioning_size_used.items():
        assert size <= 2
    assert all(result.cap_reached.values())


def test_growing_subset_dpi_structured_density_is_deterministic_given_the_same_seed_and_replicate() -> None:
    rng = np.random.default_rng(6)
    data = sample_hub(500, 0.6, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    first = growing_subset_dpi_structured_density(
        data, flagged, alpha=0.05, master_seed=7, replicate=0, permutations=19
    )
    second = growing_subset_dpi_structured_density(
        data, flagged, alpha=0.05, master_seed=7, replicate=0, permutations=19
    )

    assert np.array_equal(first.adjacency, second.adjacency)
    assert first.conditioning_size_used == second.conditioning_size_used
    assert first.n_significance_tests == second.n_significance_tests
