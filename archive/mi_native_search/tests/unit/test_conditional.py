import numpy as np
import pytest
from scipy.stats import norm

from mintnet.dpi import compute_conditional_independence_evidence, prune_conditional_independence


def _crafted_data() -> np.ndarray:
    """A small fixed sample with an exactly reproducible correlation structure."""
    rng = np.random.default_rng(20260829)
    x1 = rng.normal(size=60)
    x2 = 0.6 * x1 + np.sqrt(1 - 0.6**2) * rng.normal(size=60)
    x3 = 0.5 * x2 + np.sqrt(1 - 0.5**2) * rng.normal(size=60)
    return np.column_stack((x1, x2, x3))


def _expected_partial(data: np.ndarray, i: int, j: int, k: int) -> float:
    r = np.corrcoef(data, rowvar=False)
    return (r[i, j] - r[i, k] * r[j, k]) / np.sqrt((1 - r[i, k] ** 2) * (1 - r[j, k] ** 2))


def test_partial_correlation_matches_the_classic_three_variable_formula():
    data = _crafted_data()
    evidence = compute_conditional_independence_evidence(data)

    assert evidence.partial_correlation[0, 2] == pytest.approx(_expected_partial(data, 0, 2, 1))
    assert evidence.partial_correlation[0, 1] == pytest.approx(_expected_partial(data, 0, 1, 2))
    assert evidence.partial_correlation[1, 2] == pytest.approx(_expected_partial(data, 1, 2, 0))


def test_z_statistic_and_p_value_follow_the_fisher_transform():
    data = _crafted_data()
    n = data.shape[0]
    evidence = compute_conditional_independence_evidence(data)

    r = evidence.partial_correlation[0, 2]
    expected_z = np.arctanh(r) * np.sqrt(n - 4)
    expected_p = 2.0 * norm.sf(abs(expected_z))
    assert evidence.z_statistic[0, 2] == pytest.approx(expected_z)
    assert evidence.p_value[0, 2] == pytest.approx(expected_p)


def test_evidence_matrices_are_symmetric_with_expected_diagonal():
    evidence = compute_conditional_independence_evidence(_crafted_data())

    assert np.array_equal(evidence.partial_correlation, evidence.partial_correlation.T)
    assert np.array_equal(evidence.z_statistic, evidence.z_statistic.T)
    assert np.array_equal(evidence.p_value, evidence.p_value.T)
    assert np.all(np.diag(evidence.partial_correlation) == 0.0)
    assert np.all(np.diag(evidence.z_statistic) == 0.0)
    assert np.all(np.diag(evidence.p_value) == 1.0)


def test_chain_indirect_edge_has_a_near_zero_partial_correlation():
    """A chain's endpoints should be conditionally independent given the mediator."""
    rng = np.random.default_rng(1)
    x1 = rng.normal(size=5000)
    x2 = 0.7 * x1 + np.sqrt(1 - 0.7**2) * rng.normal(size=5000)
    x3 = 0.7 * x2 + np.sqrt(1 - 0.7**2) * rng.normal(size=5000)
    data = np.column_stack((x1, x2, x3))

    evidence = compute_conditional_independence_evidence(data)

    assert abs(evidence.partial_correlation[0, 2]) < 0.05


@pytest.mark.parametrize(
    "data",
    [
        np.zeros((10, 2)),
        np.zeros((3, 3)),
        np.full((10, 3), np.nan),
    ],
)
def test_evidence_rejects_invalid_data(data):
    with pytest.raises(ValueError):
        compute_conditional_independence_evidence(data)


def test_prune_conditional_independence_retains_iff_p_value_within_alpha():
    data = _crafted_data()
    evidence = compute_conditional_independence_evidence(data)
    alpha = 0.05

    adjacency = prune_conditional_independence(data, alpha)

    expected = evidence.p_value <= alpha
    np.fill_diagonal(expected, False)
    assert np.array_equal(adjacency, expected)
    assert not np.any(np.diag(adjacency))


@pytest.mark.parametrize("alpha", [-0.01, 0.0, 1.0, np.nan, np.inf])
def test_prune_conditional_independence_rejects_invalid_alpha(alpha):
    with pytest.raises(ValueError):
        prune_conditional_independence(_crafted_data(), alpha)
