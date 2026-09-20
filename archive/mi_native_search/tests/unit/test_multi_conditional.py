import numpy as np
import pytest

from mintnet.dpi import (
    compute_conditional_independence_evidence,
    compute_partial_correlation_evidence,
    prune_pair,
)
from mintnet.simulation import sample_chain, sample_hub


def test_single_variable_conditioning_matches_the_original_closed_form_exactly():
    """The general mechanism, given one conditioning variable, must reproduce
    Stage 1's original three-column closed-form exactly -- this is what
    justifies replacing the triad-only special case in mintnet.pipeline.compose
    with one general rule (see docs/stage2c_charter.md)."""
    rng = np.random.default_rng(0)
    data = sample_chain(500, 0.6, rng)

    original = compute_conditional_independence_evidence(data)
    general = compute_partial_correlation_evidence(data, 0, 2, conditioning=[1])

    assert general.partial_correlation == pytest.approx(original.partial_correlation[0, 2])
    assert general.p_value == pytest.approx(original.p_value[0, 2])


def test_child_pair_conditioned_on_hub_alone_is_near_independent():
    """The one-conditioning-variable case should match the existing partial-corr identity."""
    rng = np.random.default_rng(1)
    data = sample_hub(200000, 0.6, children=2, rng=rng)  # columns: hub=0, child1=1, child2=2

    evidence = compute_partial_correlation_evidence(data, 1, 2, conditioning=[0])

    assert abs(evidence.partial_correlation) < 0.02


def test_hub_child_edge_survives_conditioning_on_other_children():
    rng = np.random.default_rng(2)
    data = sample_hub(200000, 0.6, children=3, rng=rng)  # hub=0, children=1,2,3

    evidence = compute_partial_correlation_evidence(data, 0, 1, conditioning=[2, 3])

    assert abs(evidence.partial_correlation) > 0.3


def test_child_child_pair_becomes_independent_once_hub_and_other_child_conditioned_out():
    rng = np.random.default_rng(3)
    data = sample_hub(200000, 0.6, children=3, rng=rng)

    evidence = compute_partial_correlation_evidence(data, 1, 2, conditioning=[0, 3])

    assert abs(evidence.partial_correlation) < 0.02


def test_empty_conditioning_set_matches_plain_correlation():
    rng = np.random.default_rng(4)
    data = rng.normal(size=(500, 3))
    data[:, 1] = 0.5 * data[:, 0] + np.sqrt(0.75) * data[:, 1]

    evidence = compute_partial_correlation_evidence(data, 0, 1, conditioning=[])

    expected_r = np.corrcoef(data[:, 0], data[:, 1])[0, 1]
    assert evidence.partial_correlation == pytest.approx(expected_r, abs=1e-9)


@pytest.mark.parametrize(
    ("i", "j", "conditioning"),
    [
        (0, 0, [1]),  # i == j
        (0, 1, [0]),  # i in conditioning
        (0, 1, [1]),  # j in conditioning
        (0, 5, [1]),  # out of range
    ],
)
def test_rejects_invalid_column_selection(i, j, conditioning):
    data = np.random.default_rng(0).normal(size=(500, 4))
    with pytest.raises(ValueError):
        compute_partial_correlation_evidence(data, i, j, conditioning)


def test_prune_pair_retains_iff_p_value_within_alpha():
    rng = np.random.default_rng(5)
    data = sample_hub(500, 0.6, children=3, rng=rng)
    evidence = compute_partial_correlation_evidence(data, 0, 1, conditioning=[2, 3])

    assert prune_pair(data, 0, 1, [2, 3], alpha=0.5) == (evidence.p_value <= 0.5)


@pytest.mark.parametrize("alpha", [-0.01, 0.0, 1.0, np.nan, np.inf])
def test_prune_pair_rejects_invalid_alpha(alpha):
    data = sample_hub(200, 0.6, children=3, rng=np.random.default_rng(6))
    with pytest.raises(ValueError):
        prune_pair(data, 0, 1, [2, 3], alpha)


def test_rejects_zero_variance_target_column():
    """A constant column i or j must raise, not silently produce a NaN p-value
    that downstream alpha comparisons (nan <= alpha == False) would misread
    as 'not significant' rather than 'undefined'."""
    rng = np.random.default_rng(9)
    data = rng.normal(size=(200, 4))
    data[:, 1] = 5.0  # column 1 is constant

    with pytest.raises(ValueError, match="zero variance"):
        compute_partial_correlation_evidence(data, 0, 1, conditioning=[2])
    with pytest.raises(ValueError, match="zero variance"):
        compute_partial_correlation_evidence(data, 1, 0, conditioning=[2])


def test_rejects_perfect_collinearity_after_conditioning():
    """If conditioning fully explains column i (or j), the residual has zero
    variance and the partial correlation is undefined -- must raise, not NaN."""
    rng = np.random.default_rng(10)
    data = rng.normal(size=(200, 3))
    data[:, 0] = 2.0 * data[:, 2]  # column 0 is an exact linear function of column 2

    with pytest.raises(ValueError, match="collinear|undefined"):
        compute_partial_correlation_evidence(data, 0, 1, conditioning=[2])


def test_sample_hub_shape_and_validation():
    data = sample_hub(300, 0.5, children=4, rng=np.random.default_rng(7))
    assert data.shape == (300, 5)

    with pytest.raises(ValueError):
        sample_hub(300, 0.5, children=1, rng=np.random.default_rng(8))
