import numpy as np
import pytest

from mintnet.mi.structured_density import local_permutation_test
from mintnet.simulation.motifs import sample_ushape_triangle, sample_weak_edge_triangle


def test_rejects_a_genuine_direct_edge():
    data = sample_weak_edge_triangle(0.4, 1500, np.random.default_rng(1))
    result = local_permutation_test(
        data[:, 1], data[:, 2], data[:, 0], permutations=99, rng=np.random.default_rng(2)
    )
    assert result.p_value <= 0.05


def test_rejects_the_ushape_dependence_that_a_linear_test_would_miss():
    """The whole reason this estimator exists: it must actually reject
    independence on the diagnostic U-shape fixture, not just report a
    positive point estimate."""
    data = sample_ushape_triangle(0.6, 1500, np.random.default_rng(1))
    result = local_permutation_test(
        data[:, 1], data[:, 2], data[:, 0], permutations=99, rng=np.random.default_rng(2)
    )
    assert result.p_value <= 0.05


def test_unconditional_rejects_independent_data_rarely():
    rng = np.random.default_rng(4)
    trials = 30
    rejections = 0
    for _ in range(trials):
        x = rng.normal(size=300)
        y = rng.normal(size=300)
        result = local_permutation_test(x, y, None, permutations=49, rng=rng)
        if result.p_value <= 0.05:
            rejections += 1
    assert rejections / trials <= 0.15


def test_conditional_rejects_independent_data_rarely():
    rng = np.random.default_rng(5)
    trials = 30
    rejections = 0
    for _ in range(trials):
        data = sample_weak_edge_triangle(0.0, 600, rng)
        result = local_permutation_test(data[:, 1], data[:, 2], data[:, 0], permutations=49, rng=rng)
        if result.p_value <= 0.05:
            rejections += 1
    assert rejections / trials <= 0.15


def test_symmetrized_statistic_matches_the_average_of_both_orderings():
    """Directly check the disclosed symmetrization construction, not
    just its downstream effect on the p-value."""
    from mintnet.mi.structured_density import estimate_structured_cmi

    data = sample_weak_edge_triangle(0.3, 800, np.random.default_rng(1))
    x, y, z = data[:, 1], data[:, 2], data[:, 0]

    result = local_permutation_test(x, y, z, permutations=9, symmetrize=True, rng=np.random.default_rng(7))

    forward_seed_rng = np.random.default_rng(7)
    forward_seed = int(forward_seed_rng.integers(0, 2**31 - 1))
    backward_seed = int(forward_seed_rng.integers(0, 2**31 - 1))
    forward = estimate_structured_cmi(x, y, z, rng=np.random.default_rng(forward_seed))
    backward = estimate_structured_cmi(y, x, z, rng=np.random.default_rng(backward_seed))
    assert result.statistic == pytest.approx(0.5 * (forward + backward))


def test_symmetrize_false_uses_only_the_forward_orientation():
    from mintnet.mi.structured_density import estimate_structured_cmi

    data = sample_weak_edge_triangle(0.3, 800, np.random.default_rng(1))
    x, y, z = data[:, 1], data[:, 2], data[:, 0]

    result = local_permutation_test(x, y, z, permutations=9, symmetrize=False, rng=np.random.default_rng(7))

    forward_seed_rng = np.random.default_rng(7)
    forward_seed = int(forward_seed_rng.integers(0, 2**31 - 1))
    forward = estimate_structured_cmi(x, y, z, rng=np.random.default_rng(forward_seed))
    assert result.statistic == pytest.approx(forward)


def test_folds_are_fixed_across_the_observed_statistic_and_every_null_replicate():
    """Calling the estimator twice with a freshly re-seeded generator of
    the same seed must give bit-identical cross-fitting folds -- this is
    the mechanism the docstring claims isolates null variability to the
    Y-permutation. Verify indirectly: two calls to `local_permutation_test`
    with the same `rng` seed and same data must be exactly reproducible."""
    data = sample_weak_edge_triangle(0.2, 500, np.random.default_rng(1))
    x, y, z = data[:, 1], data[:, 2], data[:, 0]
    first = local_permutation_test(x, y, z, permutations=19, rng=np.random.default_rng(11))
    second = local_permutation_test(x, y, z, permutations=19, rng=np.random.default_rng(11))
    assert first.statistic == second.statistic
    assert first.null_distribution == second.null_distribution
    assert first.p_value == second.p_value
