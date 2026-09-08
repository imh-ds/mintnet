import numpy as np
import pytest

from mintnet.bootstrap import compute_edge_stability, compute_edge_stability_growing_subset
from mintnet.simulation import sample_chain


def _chain_data(n: int, seed: int) -> np.ndarray:
    return sample_chain(n, strength=0.8, rng=np.random.default_rng(seed))


def test_pi_matrices_are_symmetric_bounded_and_zero_diagonal():
    data = _chain_data(500, seed=1)
    result = compute_edge_stability(data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=25, rng=np.random.default_rng(2))

    for matrix in (result.pi_candidate, result.pi_final):
        assert np.array_equal(matrix, matrix.T)
        assert np.all(matrix >= 0.0) and np.all(matrix <= 1.0)
        assert np.all(np.diag(matrix) == 0.0)


def test_successful_plus_failed_equals_requested_bootstraps():
    data = _chain_data(500, seed=3)
    bootstraps = 40
    result = compute_edge_stability(data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=bootstraps, rng=np.random.default_rng(4))

    assert result.successful_bootstraps + result.failed_bootstraps == bootstraps
    assert result.successful_bootstraps > 0


def test_strong_true_edge_is_more_stable_than_a_pure_noise_pair():
    """A strongly correlated pair should survive resampling far more often
    than two independent noise columns -- otherwise the statistic carries
    no separating information at all."""
    rng = np.random.default_rng(5)
    n = 750
    x1 = rng.normal(size=n)
    x2 = 0.9 * x1 + np.sqrt(1 - 0.9**2) * rng.normal(size=n)
    noise = rng.normal(size=(n, 2))
    data = np.column_stack([x1, x2, noise])

    result = compute_edge_stability(data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=200, rng=np.random.default_rng(6))

    assert result.pi_candidate[0, 1] > result.pi_candidate[2, 3]
    assert result.pi_candidate[0, 1] > 0.9


def test_rejects_bootstraps_below_one():
    data = _chain_data(200, seed=7)
    with pytest.raises(ValueError, match="bootstraps"):
        compute_edge_stability(data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=0, rng=np.random.default_rng(8))


def test_bootstrap_resample_is_reproducible_given_the_same_rng_state():
    data = _chain_data(200, seed=9)
    result_a = compute_edge_stability(data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=30, rng=np.random.default_rng(10))
    result_b = compute_edge_stability(data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=30, rng=np.random.default_rng(10))

    assert np.array_equal(result_a.pi_final, result_b.pi_final)
    assert np.array_equal(result_a.pi_candidate, result_b.pi_candidate)


def test_growing_subset_pi_matrices_are_symmetric_bounded_and_zero_diagonal():
    data = _chain_data(500, seed=1)
    result = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=25, rng=np.random.default_rng(2)
    )

    for matrix in (result.pi_candidate, result.pi_final):
        assert np.array_equal(matrix, matrix.T)
        assert np.all(matrix >= 0.0) and np.all(matrix <= 1.0)
        assert np.all(np.diag(matrix) == 0.0)


def test_growing_subset_successful_plus_failed_equals_requested_bootstraps():
    data = _chain_data(500, seed=3)
    bootstraps = 40
    result = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=bootstraps,
        rng=np.random.default_rng(4),
    )

    assert result.successful_bootstraps + result.failed_bootstraps == bootstraps
    assert result.successful_bootstraps > 0


def test_growing_subset_strong_true_edge_is_more_stable_than_a_pure_noise_pair():
    rng = np.random.default_rng(5)
    n = 750
    x1 = rng.normal(size=n)
    x2 = 0.9 * x1 + np.sqrt(1 - 0.9**2) * rng.normal(size=n)
    noise = rng.normal(size=(n, 2))
    data = np.column_stack([x1, x2, noise])

    result = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=200,
        rng=np.random.default_rng(6),
    )

    assert result.pi_final[0, 1] > result.pi_final[2, 3]
    assert result.pi_final[0, 1] > 0.9


def test_growing_subset_rejects_bootstraps_below_one():
    data = _chain_data(200, seed=7)
    with pytest.raises(ValueError, match="bootstraps"):
        compute_edge_stability_growing_subset(
            data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=0,
            rng=np.random.default_rng(8),
        )


def test_growing_subset_bootstrap_is_reproducible_given_the_same_rng_state():
    data = _chain_data(200, seed=9)
    result_a = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=30,
        rng=np.random.default_rng(10),
    )
    result_b = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=30,
        rng=np.random.default_rng(10),
    )

    assert np.array_equal(result_a.pi_final, result_b.pi_final)
    assert np.array_equal(result_a.pi_candidate, result_b.pi_candidate)
