import numpy as np
import pytest

from mintnet.simulation.motifs import (
    sample_chain,
    sample_measured_fork,
    sample_monotonic_curvature_triangle,
    sample_precision_triangle,
    sample_ushape_triangle,
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


def _partial_correlation_12(data: np.ndarray) -> float:
    correlation = np.corrcoef(data.T)
    r01, r02, r12 = correlation[0, 1], correlation[0, 2], correlation[1, 2]
    return (r12 - r01 * r02) / np.sqrt((1 - r01**2) * (1 - r02**2))


@pytest.mark.parametrize("target_rho", [0.0, 0.08, 0.15, 0.25])
def test_monotonic_curvature_triangle_preserves_rank_order_of_the_untransformed_column(target_rho):
    """`tanh` (and standardization) are both strictly monotonic increasing,
    so the transformed fixture's column 2 must have the *exact same rank
    order* as the untransformed weak-edge fixture's own column 2, given
    the same seed -- this is the direct, exact consequence of the
    invariance claim in the docstring, checkable with no tolerance."""
    raw = sample_weak_edge_triangle(target_rho, 5_000, np.random.default_rng(7))
    transformed = sample_monotonic_curvature_triangle(target_rho, 5_000, np.random.default_rng(7))
    assert np.array_equal(np.argsort(raw[:, 2]), np.argsort(transformed[:, 2]))


def test_monotonic_curvature_triangle_attenuates_the_linear_partial_correlation():
    """The whole point of this fixture: a linear/Pearson-based partial
    correlation test sees a *weaker* relationship here than the matched-
    MI untransformed fixture, since `tanh` distorts (but does not
    destroy) the true dependence for a linear measure."""
    target_rho = 0.3
    raw = sample_weak_edge_triangle(target_rho, 400_000, np.random.default_rng(11))
    transformed = sample_monotonic_curvature_triangle(target_rho, 400_000, np.random.default_rng(11))
    raw_partial = abs(_partial_correlation_12(raw))
    transformed_partial = abs(_partial_correlation_12(transformed))
    assert abs(raw_partial - target_rho) < 0.01
    assert transformed_partial < raw_partial - 0.008


def test_monotonic_curvature_triangle_is_standardized_and_seeded():
    first = sample_monotonic_curvature_triangle(0.1, 100, np.random.default_rng(42))
    second = sample_monotonic_curvature_triangle(0.1, 100, np.random.default_rng(42))
    assert np.array_equal(first, second)
    assert first.shape == (100, 3)
    assert np.allclose(first.mean(axis=0), 0.0)
    assert np.allclose(first.std(axis=0, ddof=1), 1.0)


def test_monotonic_curvature_triangle_rejects_non_positive_definite_target():
    with pytest.raises(ValueError, match="not positive definite"):
        sample_monotonic_curvature_triangle(0.9, 10, np.random.default_rng(1))


@pytest.mark.parametrize("curvature", [-0.6, -0.3, 0.0, 0.3, 0.6])
def test_ushape_triangle_has_exactly_zero_linear_partial_correlation(curvature):
    """The defining property: regardless of curvature (sign or magnitude,
    within the valid range), the column-0-partialled linear correlation
    between columns 1 and 2 is exactly zero by construction -- a Fisher-
    z/partial-correlation test must see a perfect null here."""
    data = sample_ushape_triangle(curvature, 200_000, np.random.default_rng(3))
    assert abs(_partial_correlation_12(data)) < 0.01


@pytest.mark.parametrize("curvature", [-0.6, -0.3, 0.3, 0.6])
def test_ushape_triangle_has_real_quadratic_dependence_despite_zero_correlation(curvature):
    """Confirm the "zero linear correlation" result above is not simply
    because there is no dependence at all: regress out column 0 from
    columns 1 and 2 (ordinary least squares, using only the returned
    data -- no access to the generator's own internals), then check that
    the *squared* residual of column 1 correlates with the residual of
    column 2, with a sign matching curvature's own sign. This is exactly
    the quadratic relationship a linear/Pearson test cannot see."""
    data = sample_ushape_triangle(curvature, 200_000, np.random.default_rng(3))
    x0, x1, x2 = data[:, 0], data[:, 1], data[:, 2]
    beta1 = np.cov(x1, x0)[0, 1] / np.var(x0, ddof=1)
    beta2 = np.cov(x2, x0)[0, 1] / np.var(x0, ddof=1)
    residual_1 = x1 - beta1 * x0
    residual_2 = x2 - beta2 * x0
    quadratic_correlation = np.corrcoef(residual_1**2, residual_2)[0, 1]
    assert np.sign(quadratic_correlation) == np.sign(curvature)
    assert abs(quadratic_correlation) > 0.05


def test_ushape_triangle_curvature_zero_is_a_valid_conditional_independence_null():
    """At `curvature=0`, column 2's residual is pure noise -- columns 1
    and 2 should be fully independent given column 0, not just linearly
    uncorrelated: the squared-residual check above should show no
    relationship either, unlike the nonzero-curvature cases."""
    data = sample_ushape_triangle(0.0, 200_000, np.random.default_rng(3))
    x0, x1, x2 = data[:, 0], data[:, 1], data[:, 2]
    beta1 = np.cov(x1, x0)[0, 1] / np.var(x0, ddof=1)
    beta2 = np.cov(x2, x0)[0, 1] / np.var(x0, ddof=1)
    residual_1 = x1 - beta1 * x0
    residual_2 = x2 - beta2 * x0
    quadratic_correlation = np.corrcoef(residual_1**2, residual_2)[0, 1]
    assert abs(quadratic_correlation) < 0.05


def test_ushape_triangle_is_standardized_and_seeded():
    first = sample_ushape_triangle(0.3, 100, np.random.default_rng(42))
    second = sample_ushape_triangle(0.3, 100, np.random.default_rng(42))
    assert np.array_equal(first, second)
    assert first.shape == (100, 3)
    assert np.allclose(first.mean(axis=0), 0.0)
    assert np.allclose(first.std(axis=0, ddof=1), 1.0)


@pytest.mark.parametrize("curvature", [0.7071068, 0.8, -0.8])
def test_ushape_triangle_rejects_curvature_out_of_bounds(curvature):
    with pytest.raises(ValueError, match="curvature must satisfy"):
        sample_ushape_triangle(curvature, 10, np.random.default_rng(1))
