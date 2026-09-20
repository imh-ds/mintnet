import numpy as np
import pytest
from scipy.stats import norm

from mintnet.screening import (
    ScreeningEvidence,
    benjamini_hochberg_threshold,
    compute_pairwise_screening_evidence,
    screen_uncorrected,
)


def _crafted_data() -> np.ndarray:
    rng = np.random.default_rng(20260829)
    x1 = rng.normal(size=200)
    x2 = 0.6 * x1 + np.sqrt(1 - 0.6**2) * rng.normal(size=200)
    x3 = rng.normal(size=200)  # independent of x1, x2
    return np.column_stack((x1, x2, x3))


def test_z_statistic_and_p_value_follow_the_unconditional_fisher_transform():
    data = _crafted_data()
    n = data.shape[0]
    evidence = compute_pairwise_screening_evidence(data)

    r = evidence.correlation[0, 1]
    expected_z = np.arctanh(r) * np.sqrt(n - 3)
    expected_p = 2.0 * norm.sf(abs(expected_z))
    assert evidence.z_statistic[0, 1] == pytest.approx(expected_z)
    assert evidence.p_value[0, 1] == pytest.approx(expected_p)


def test_evidence_matrices_are_symmetric_with_expected_diagonal():
    evidence = compute_pairwise_screening_evidence(_crafted_data())

    assert np.array_equal(evidence.correlation, evidence.correlation.T)
    assert np.array_equal(evidence.z_statistic, evidence.z_statistic.T)
    assert np.array_equal(evidence.p_value, evidence.p_value.T)
    assert np.all(np.diag(evidence.correlation) == 0.0)
    assert np.all(np.diag(evidence.p_value) == 1.0)


def test_independent_pair_has_a_near_zero_sample_correlation_at_large_n():
    """A true-null p-value is uniform(0,1) regardless of N, so check magnitude instead."""
    rng = np.random.default_rng(1)
    x1 = rng.normal(size=5000)
    x2 = rng.normal(size=5000)
    evidence = compute_pairwise_screening_evidence(np.column_stack((x1, x2)))

    assert abs(evidence.correlation[0, 1]) < 0.05


def test_screen_uncorrected_flags_iff_p_value_within_alpha():
    data = _crafted_data()
    evidence = compute_pairwise_screening_evidence(data)
    alpha = 0.05

    flagged = screen_uncorrected(evidence, alpha)

    expected = evidence.p_value <= alpha
    np.fill_diagonal(expected, False)
    assert np.array_equal(flagged, expected)


@pytest.mark.parametrize("alpha", [-0.01, 0.0, 1.0, np.nan, np.inf])
def test_screen_uncorrected_rejects_invalid_alpha(alpha):
    with pytest.raises(ValueError):
        screen_uncorrected(compute_pairwise_screening_evidence(_crafted_data()), alpha)


def test_benjamini_hochberg_flags_no_more_pairs_than_uncorrected_at_the_same_level():
    """BH at level q should never flag more pairs than an uncorrected test at alpha=q."""
    data = _crafted_data()
    evidence = compute_pairwise_screening_evidence(data)

    bh_flagged = benjamini_hochberg_threshold(evidence, 0.10)
    uncorrected_flagged = screen_uncorrected(evidence, 0.10)

    assert bh_flagged.sum() <= uncorrected_flagged.sum()


def test_rejects_zero_variance_column():
    """A constant column must raise, not silently propagate NaN through the
    correlation/p-value matrices that screen_uncorrected would then misread
    as 'not significant' (nan <= alpha == False)."""
    rng = np.random.default_rng(11)
    data = rng.normal(size=(200, 3))
    data[:, 1] = 3.0  # column 1 is constant

    with pytest.raises(ValueError, match="zero variance"):
        compute_pairwise_screening_evidence(data)


def test_benjamini_hochberg_matches_hand_worked_example():
    """p=4 gives m=C(4,2)=6 tests. p-values .01, .04, .30 plus three untested
    pairs at 1.0. Sorted ranks/thresholds at q=.10: rank1 .01<=.1/6=.0167 (pass),
    rank2 .04<=.2/6=.0333 (fail), rank3+ all fail. BH's largest-passing-rank
    rule means only the rank-1 pair (p=.01) is flagged, even though .04 alone
    would pass an uncorrected alpha=.05 test.
    """
    p = 4
    p_value = np.ones((p, p))
    pairs = {(0, 1): 0.01, (0, 2): 0.04, (0, 3): 0.30}
    for (i, j), pv in pairs.items():
        p_value[i, j] = p_value[j, i] = pv

    evidence = ScreeningEvidence(correlation=np.zeros((p, p)), z_statistic=np.zeros((p, p)), p_value=p_value)

    flagged = benjamini_hochberg_threshold(evidence, 0.10)

    assert flagged[0, 1]
    assert not flagged[0, 2]
    assert not flagged[0, 3]
    assert not flagged[1, 2]
    assert not flagged[1, 3]
    assert not flagged[2, 3]
    assert flagged.sum() == 2  # symmetric matrix counts (0,1) and (1,0)
