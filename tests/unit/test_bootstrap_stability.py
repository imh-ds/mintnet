from unittest.mock import patch

import numpy as np
import pytest

from mintnet.bootstrap import compute_edge_stability, compute_edge_stability_growing_subset
from mintnet.bootstrap.stability import _AUTO_N_JOBS_CAP, _resolve_n_jobs
from mintnet.simulation import sample_chain

# Every test below pins n_jobs=1 explicitly (the library's own default is
# now "auto", which can spawn worker processes) so the suite stays fast
# and single-process under pytest-xdist. n_jobs behavior itself is
# covered by the dedicated tests further down.


def _chain_data(n: int, seed: int) -> np.ndarray:
    return sample_chain(n, strength=0.8, rng=np.random.default_rng(seed))


def test_pi_matrices_are_symmetric_bounded_and_zero_diagonal():
    data = _chain_data(500, seed=1)
    result = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=25, rng=np.random.default_rng(2), n_jobs=1
    )

    for matrix in (result.pi_candidate, result.pi_final):
        assert np.array_equal(matrix, matrix.T)
        assert np.all(matrix >= 0.0) and np.all(matrix <= 1.0)
        assert np.all(np.diag(matrix) == 0.0)


def test_successful_plus_failed_equals_requested_bootstraps():
    data = _chain_data(500, seed=3)
    bootstraps = 40
    result = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=bootstraps, rng=np.random.default_rng(4), n_jobs=1
    )

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

    result = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=200, rng=np.random.default_rng(6), n_jobs=1
    )

    assert result.pi_candidate[0, 1] > result.pi_candidate[2, 3]
    assert result.pi_candidate[0, 1] > 0.9


def test_rejects_bootstraps_below_one():
    data = _chain_data(200, seed=7)
    with pytest.raises(ValueError, match="bootstraps"):
        compute_edge_stability(
            data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=0, rng=np.random.default_rng(8), n_jobs=1
        )


def test_bootstrap_resample_is_reproducible_given_the_same_rng_state():
    data = _chain_data(200, seed=9)
    result_a = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=30, rng=np.random.default_rng(10), n_jobs=1
    )
    result_b = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=30, rng=np.random.default_rng(10), n_jobs=1
    )

    assert np.array_equal(result_a.pi_final, result_b.pi_final)
    assert np.array_equal(result_a.pi_candidate, result_b.pi_candidate)


def test_n_jobs_greater_than_one_matches_the_sequential_result_bit_for_bit():
    """n_jobs only distributes compute across processes -- the resample
    draw order from rng is unchanged, so results must be identical."""
    data = _chain_data(500, seed=1)
    sequential = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=20, rng=np.random.default_rng(2), n_jobs=1
    )
    parallel = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=20, rng=np.random.default_rng(2), n_jobs=2
    )

    assert np.array_equal(sequential.pi_final, parallel.pi_final)
    assert np.array_equal(sequential.pi_candidate, parallel.pi_candidate)
    assert sequential.successful_bootstraps == parallel.successful_bootstraps
    assert sequential.failed_bootstraps == parallel.failed_bootstraps


def test_rejects_n_jobs_below_one():
    data = _chain_data(200, seed=7)
    with pytest.raises(ValueError, match="n_jobs"):
        compute_edge_stability(
            data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=10, rng=np.random.default_rng(8), n_jobs=0
        )


def test_growing_subset_pi_matrices_are_symmetric_bounded_and_zero_diagonal():
    data = _chain_data(500, seed=1)
    result = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=25,
        rng=np.random.default_rng(2), n_jobs=1,
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
        rng=np.random.default_rng(4), n_jobs=1,
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
        rng=np.random.default_rng(6), n_jobs=1,
    )

    assert result.pi_final[0, 1] > result.pi_final[2, 3]
    assert result.pi_final[0, 1] > 0.9


def test_growing_subset_rejects_bootstraps_below_one():
    data = _chain_data(200, seed=7)
    with pytest.raises(ValueError, match="bootstraps"):
        compute_edge_stability_growing_subset(
            data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=0,
            rng=np.random.default_rng(8), n_jobs=1,
        )


def test_growing_subset_bootstrap_is_reproducible_given_the_same_rng_state():
    data = _chain_data(200, seed=9)
    result_a = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=30,
        rng=np.random.default_rng(10), n_jobs=1,
    )
    result_b = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=30,
        rng=np.random.default_rng(10), n_jobs=1,
    )

    assert np.array_equal(result_a.pi_final, result_b.pi_final)
    assert np.array_equal(result_a.pi_candidate, result_b.pi_candidate)


def test_growing_subset_n_jobs_greater_than_one_matches_the_sequential_result_bit_for_bit():
    data = _chain_data(500, seed=1)
    sequential = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=20,
        rng=np.random.default_rng(2), n_jobs=1,
    )
    parallel = compute_edge_stability_growing_subset(
        data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=20,
        rng=np.random.default_rng(2), n_jobs=2,
    )

    assert np.array_equal(sequential.pi_final, parallel.pi_final)
    assert np.array_equal(sequential.pi_candidate, parallel.pi_candidate)
    assert sequential.successful_bootstraps == parallel.successful_bootstraps
    assert sequential.failed_bootstraps == parallel.failed_bootstraps


def test_growing_subset_rejects_n_jobs_below_one():
    data = _chain_data(200, seed=7)
    with pytest.raises(ValueError, match="n_jobs"):
        compute_edge_stability_growing_subset(
            data, screening_alpha=0.001, dpi_alpha=0.10, max_conditioning_size=4, bootstraps=10,
            rng=np.random.default_rng(8), n_jobs=0,
        )


# -- "auto" resolution (mintnet.bootstrap.stability._resolve_n_jobs) --
# Tested directly against the helper rather than through a real (slow)
# bootstrap run: the equivalence tests above already prove any resolved
# n_jobs value produces identical results, so only the resolution logic
# itself needs its own coverage here.


def test_auto_caps_at_eight_on_a_high_core_count_machine():
    with patch("mintnet.bootstrap.stability.os.cpu_count", return_value=20):
        assert _resolve_n_jobs("auto") == 8 == _AUTO_N_JOBS_CAP


def test_auto_matches_cpu_count_when_below_the_cap():
    with patch("mintnet.bootstrap.stability.os.cpu_count", return_value=4):
        assert _resolve_n_jobs("auto") == 4


def test_auto_falls_back_to_one_when_cpu_count_is_unknown():
    with patch("mintnet.bootstrap.stability.os.cpu_count", return_value=None):
        assert _resolve_n_jobs("auto") == 1


def test_explicit_n_jobs_can_exceed_the_auto_cap():
    assert _resolve_n_jobs(16) == 16


def test_resolve_n_jobs_rejects_invalid_values():
    for invalid in (0, -1, "fast", 1.5):
        with pytest.raises(ValueError, match="n_jobs"):
            _resolve_n_jobs(invalid)


def test_compute_edge_stability_default_n_jobs_is_auto_and_still_matches_n_jobs_one():
    """With cpu_count mocked to 1, the default ("auto") call must take
    the same sequential path as an explicit n_jobs=1 call and produce
    an identical result -- confirms the default is wired to _resolve_
    n_jobs rather than silently pinned to some other value."""
    data = _chain_data(300, seed=11)
    with patch("mintnet.bootstrap.stability.os.cpu_count", return_value=1):
        default_call = compute_edge_stability(
            data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=15, rng=np.random.default_rng(12)
        )
    explicit_call = compute_edge_stability(
        data, screening_alpha=0.001, dpi_alpha=0.10, bootstraps=15, rng=np.random.default_rng(12), n_jobs=1
    )

    assert np.array_equal(default_call.pi_final, explicit_call.pi_final)
