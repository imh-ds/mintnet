import numpy as np

from mintnet.mi.cmiknn import _restricted_permutation, _z_neighbors, estimate_cmiknn, local_permutation_test
from mintnet.mi.ksg import estimate_ksg_mi


def test_estimate_cmiknn_matches_bivariate_ksg_exactly_when_z_is_none() -> None:
    """|S|=0 must reduce exactly to the already-validated bivariate
    estimator -- docs/stage6b_charter.md's own primary correctness
    check before any conditional claim is trusted."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=400)
    y = 0.6 * x + np.sqrt(1 - 0.6**2) * rng.normal(size=400)

    conditional = estimate_cmiknn(x, y, None, k=20)
    bivariate = estimate_ksg_mi(x, y, k=20)

    assert conditional == bivariate


def test_estimate_cmiknn_near_zero_for_conditionally_independent_chain() -> None:
    rng = np.random.default_rng(1)
    n = 3000
    x1 = rng.normal(size=n)
    x2 = 0.6 * x1 + np.sqrt(1 - 0.6**2) * rng.normal(size=n)
    x3 = 0.6 * x2 + np.sqrt(1 - 0.6**2) * rng.normal(size=n)

    estimate = estimate_cmiknn(x1, x3, x2, k=20)

    assert abs(estimate) < 0.05


def test_estimate_cmiknn_recovers_analytic_gaussian_reference_for_direct_edge() -> None:
    rng = np.random.default_rng(2)
    n = 3000
    x1 = rng.normal(size=n)
    x2 = 0.6 * x1 + np.sqrt(1 - 0.6**2) * rng.normal(size=n)
    x3 = 0.6 * x2 + np.sqrt(1 - 0.6**2) * rng.normal(size=n)

    estimate = estimate_cmiknn(x1, x2, x3, k=20)

    # Analytic reference is the true partial correlation r_{12.3}, not
    # the raw pairwise r12=0.6 -- X3 is downstream of X2, so
    # conditioning on it changes the apparent X1-X2 relationship.
    # r12=.6, r13=.36 (=.6^2, since X1->X2->X3), r23=.6.
    r12, r13, r23 = 0.6, 0.36, 0.6
    r12_3 = (r12 - r13 * r23) / np.sqrt((1 - r13**2) * (1 - r23**2))
    analytic = -0.5 * np.log(1 - r12_3**2)

    assert abs(estimate - analytic) < 0.05


def test_local_permutation_test_rejects_a_genuine_direct_edge() -> None:
    rng = np.random.default_rng(3)
    n = 1500
    x1 = rng.normal(size=n)
    x2 = 0.6 * x1 + np.sqrt(1 - 0.6**2) * rng.normal(size=n)
    x3 = 0.6 * x2 + np.sqrt(1 - 0.6**2) * rng.normal(size=n)

    result = local_permutation_test(x1, x2, x3, k=20, permutations=99, rng=rng)

    assert result.p_value <= 0.05


def test_z_neighbors_are_self_inclusive() -> None:
    """D-055's fix, point 1: matches Runge/tigramite's own reference --
    each point's own index must appear in its own neighbor list (a
    point is its own nearest neighbor at distance 0), not excluded."""
    rng = np.random.default_rng(5)
    z = rng.normal(size=(50, 2))
    neighbors = _z_neighbors(z, k_perm=5)
    assert all(i in neighbors[i] for i in range(50))


def test_restricted_permutation_never_reaches_outside_the_local_neighborhood() -> None:
    """D-055's fix, point 2: every assigned index must come from the
    point's own neighbor list -- unlike the prior version, which fell
    back to a uniformly random pick from the entire dataset (possibly
    far in Z-space) whenever local candidates were exhausted."""
    rng = np.random.default_rng(6)
    n = 30
    z = rng.normal(size=(n, 1))  # 1D Z and small k_perm forces frequent exhaustion
    neighbors = _z_neighbors(z, k_perm=3)

    for _ in range(20):
        perm = _restricted_permutation(neighbors, rng)
        assert len(perm) == n
        for i in range(n):
            assert perm[i] in neighbors[i], "assigned index must be one of the point's own k_perm neighbors"


def test_restricted_permutation_can_collide_rather_than_reach_globally() -> None:
    """With k_perm=1 (no alternative but self), every point maps to
    itself -- the identity permutation, not an error and not a global
    fallback -- confirming the 'reuse the last one anyway' behavior
    rather than raising or substituting a distant point."""
    rng = np.random.default_rng(7)
    z = rng.normal(size=(20, 1))
    neighbors = _z_neighbors(z, k_perm=1)
    perm = _restricted_permutation(neighbors, rng)
    assert np.array_equal(perm, np.arange(20))


def test_local_permutation_test_unconditional_rejects_independent_data_rarely() -> None:
    rng = np.random.default_rng(4)
    trials = 40
    rejections = 0
    for _ in range(trials):
        x = rng.normal(size=300)
        y = rng.normal(size=300)
        result = local_permutation_test(x, y, None, k=10, permutations=99, rng=rng)
        if result.p_value <= 0.05:
            rejections += 1

    assert rejections / trials <= 0.15
