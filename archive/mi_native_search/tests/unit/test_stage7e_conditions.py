import numpy as np
import pytest

from mintnet.experiments.stage7e_conditions import (
    CHAIN_FORK_STRENGTHS,
    TRIANGLE_FAMILIES,
    all_conditions,
    condition_label,
    condition_pairs,
    parse_condition,
    sample_condition,
)


def test_condition_label_round_trips():
    assert condition_label("chain", 0.3) == "chain_0.3"
    assert parse_condition("chain_0.3") == ("chain", "0.3")
    assert parse_condition(condition_label("triangle", "strong")) == ("triangle", "strong")


def test_all_conditions_covers_every_motif():
    conditions = all_conditions()
    assert len(conditions) == 2 * len(CHAIN_FORK_STRENGTHS) + len(TRIANGLE_FAMILIES)
    assert len(set(conditions)) == len(conditions)
    for strength in CHAIN_FORK_STRENGTHS:
        assert condition_label("chain", strength) in conditions
        assert condition_label("fork", strength) in conditions
    for family in TRIANGLE_FAMILIES:
        assert condition_label("triangle", family) in conditions


def test_condition_pairs_chain_and_fork_have_only_the_null_pair():
    assert condition_pairs("chain_0.3") == ((0, 2),)
    assert condition_pairs("fork_0.5") == ((0, 2),)


def test_condition_pairs_triangle_has_all_three_pairs():
    assert set(condition_pairs("triangle_strong")) == {(0, 1), (0, 2), (1, 2)}


@pytest.mark.parametrize("condition", list(all_conditions()))
def test_sample_condition_returns_a_three_column_array(condition):
    data = sample_condition(condition, 50, np.random.default_rng(0))
    assert data.shape == (50, 3)
    assert np.isfinite(data).all()


def test_sample_condition_rejects_unknown_motif():
    with pytest.raises(ValueError, match="unknown condition motif"):
        sample_condition("bogus_0.1", 10, np.random.default_rng(0))


def test_sample_condition_is_seeded_and_reproducible():
    first = sample_condition("chain_0.5", 50, np.random.default_rng(3))
    second = sample_condition("chain_0.5", 50, np.random.default_rng(3))
    assert np.array_equal(first, second)
