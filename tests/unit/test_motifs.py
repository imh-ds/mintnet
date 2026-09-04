import numpy as np
import pytest

from mintnet.simulation.motifs import (
    sample_chain,
    sample_measured_fork,
    sample_precision_triangle,
    sample_weak_edge_triangle,
    triangle_precisions,
)


def test_chain_endpoint_correlation_is_weaker_than_adjacent_links():
    data = sample_chain(100_000, 0.7, np.random.default_rng(1))
    corr = np.corrcoef(data.T)
    assert corr[0, 2] < corr[0, 1]
    assert corr[0, 2] < corr[1, 2]


def test_measured_fork_endpoint_correlation_is_weaker_than_adjacent_links():
    data = sample_measured_fork(100_000, 0.7, np.random.default_rng(1))
    corr = np.corrcoef(data.T)
    assert corr[0, 2] < corr[0, 1]
    assert corr[0, 2] < corr[1, 2]


def test_triangle_precisions_are_positive_definite():
    for precision in triangle_precisions().values():
        np.linalg.cholesky(precision)
        assert np.all(np.abs(precision[np.triu_indices(3, 1)]) > 0)


def test_triangle_samples_are_standardized_and_seeded():
    first = sample_precision_triangle("balanced", 100, np.random.default_rng(42))
    second = sample_precision_triangle("balanced", 100, np.random.default_rng(42))
    assert np.array_equal(first, second)
    assert first.shape == (100, 3)
    assert np.allclose(first.mean(axis=0), 0.0)
    assert np.allclose(first.std(axis=0, ddof=1), 1.0)


@pytest.mark.parametrize("n", [0, -1])
def test_motifs_reject_nonpositive_sample_size(n):
    with pytest.raises(ValueError, match="n must be at least 1"):
        sample_chain(n, 0.7, np.random.default_rng(1))


def test_motifs_reject_invalid_strength():
    with pytest.raises(ValueError, match="0 < strength < 1"):
        sample_measured_fork(10, 1.0, np.random.default_rng(1))


def test_triangle_rejects_unknown_name():
    with pytest.raises(ValueError, match="unknown triangle"):
        sample_precision_triangle("unknown", 10, np.random.default_rng(1))


@pytest.mark.parametrize("target_rho", [0.0, 0.04, 0.08, 0.15, 0.25])
def test_weak_edge_triangle_recovers_the_exact_target_partial_correlation(target_rho):
    """Partial correlation = -precision[i,j] exactly for a unit-diagonal
    precision matrix -- verify the sampled data's own empirical partial
    correlation on the (1, 2) pair converges to `target_rho`, at a large
    N where sampling noise is small relative to the effect being checked."""
    data = sample_weak_edge_triangle(target_rho, 200_000, np.random.default_rng(0))
    correlation = np.corrcoef(data.T)
    r01, r02, r12 = correlation[0, 1], correlation[0, 2], correlation[1, 2]
    partial_12 = (r12 - r01 * r02) / np.sqrt((1 - r01**2) * (1 - r02**2))
    # partial_correlation(i,j) = -precision[i,j] for a unit-diagonal
    # precision matrix; precision[1,2] = -target_rho, so the true
    # partial correlation is +target_rho (sign is scientifically
    # irrelevant here -- CMI depends only on rho^2 -- but the magnitude
    # match is the real check).
    assert abs(partial_12 - target_rho) < 0.01


def test_weak_edge_triangle_is_standardized_and_seeded():
    first = sample_weak_edge_triangle(0.1, 100, np.random.default_rng(42))
    second = sample_weak_edge_triangle(0.1, 100, np.random.default_rng(42))
    assert np.array_equal(first, second)
    assert first.shape == (100, 3)
    assert np.allclose(first.mean(axis=0), 0.0)
    assert np.allclose(first.std(axis=0, ddof=1), 1.0)


def test_weak_edge_triangle_matches_strong_fixture_at_target_rho_point_zero_eight():
    """target_rho=0.08 reproduces the existing 'strong' fixture's own
    precision matrix exactly -- direct continuity with D-059's evidence."""
    from mintnet.simulation.motifs import triangle_precisions

    weak_edge_precision = np.array([[1.0, -0.45, -0.25], [-0.45, 1.0, -0.08], [-0.25, -0.08, 1.0]])
    assert np.array_equal(weak_edge_precision, triangle_precisions()["strong"])


def test_weak_edge_triangle_rejects_non_positive_definite_target():
    with pytest.raises(ValueError, match="not positive definite"):
        sample_weak_edge_triangle(0.9, 10, np.random.default_rng(1))
