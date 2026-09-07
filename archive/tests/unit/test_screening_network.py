from itertools import combinations

import numpy as np

from mintnet.simulation import TRUE_PAIR_INDICES, sample_screening_network


def test_sample_screening_network_has_expected_shape():
    rng = np.random.default_rng(1)
    data = sample_screening_network(500, 0.5, "moderate", noise_count=6, rng=rng)

    assert data.shape == (500, 15)


def test_true_pair_indices_are_exactly_the_nine_within_motif_pairs():
    assert TRUE_PAIR_INDICES == {
        (0, 1), (0, 2), (1, 2),
        (3, 4), (3, 5), (4, 5),
        (6, 7), (6, 8), (7, 8),
    }


def test_null_pairs_show_essentially_zero_population_correlation():
    """Motif-to-noise and noise-to-noise pairs should be uncorrelated at large N."""
    rng = np.random.default_rng(2)
    data = sample_screening_network(200000, 0.5, "moderate", noise_count=6, rng=rng)
    correlation = np.corrcoef(data, rowvar=False)

    all_pairs = set(combinations(range(15), 2))
    null_pairs = all_pairs - TRUE_PAIR_INDICES
    assert len(null_pairs) == 96

    for i, j in null_pairs:
        assert abs(correlation[i, j]) < 0.02


def test_true_pairs_show_nonzero_correlation_including_indirect_chain_endpoints():
    rng = np.random.default_rng(3)
    data = sample_screening_network(200000, 0.5, "moderate", noise_count=6, rng=rng)
    correlation = np.corrcoef(data, rowvar=False)

    for i, j in TRUE_PAIR_INDICES:
        assert abs(correlation[i, j]) > 0.05
