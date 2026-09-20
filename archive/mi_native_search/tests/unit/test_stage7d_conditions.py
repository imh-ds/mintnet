import numpy as np
import pytest

from mintnet.experiments.stage7d_conditions import (
    CURVATURE_RHOS,
    LINEAR_RHOS,
    USHAPE_CURVATURES,
    all_conditions,
    condition_label,
    parse_condition,
    sample_condition,
)


def test_condition_label_round_trips():
    assert condition_label("linear", 0.08) == "linear_0.08"
    assert parse_condition("linear_0.08") == ("linear", 0.08)
    assert parse_condition(condition_label("ushape", 0.0)) == ("ushape", 0.0)


def test_all_conditions_covers_every_family_and_param():
    conditions = all_conditions()
    assert len(conditions) == len(LINEAR_RHOS) + len(CURVATURE_RHOS) + len(USHAPE_CURVATURES)
    assert len(set(conditions)) == len(conditions)
    for rho in LINEAR_RHOS:
        assert condition_label("linear", rho) in conditions
    for rho in CURVATURE_RHOS:
        assert condition_label("curvature", rho) in conditions
    for curvature in USHAPE_CURVATURES:
        assert condition_label("ushape", curvature) in conditions


@pytest.mark.parametrize("condition", list(all_conditions()))
def test_sample_condition_returns_a_three_column_array(condition):
    data = sample_condition(condition, 50, np.random.default_rng(0))
    assert data.shape == (50, 3)
    assert np.isfinite(data).all()


def test_sample_condition_rejects_unknown_family():
    with pytest.raises(ValueError, match="unknown condition family"):
        sample_condition("bogus_0.1", 10, np.random.default_rng(0))


def test_sample_condition_is_seeded_and_reproducible():
    first = sample_condition("linear_0.1", 50, np.random.default_rng(3))
    second = sample_condition("linear_0.1", 50, np.random.default_rng(3))
    assert np.array_equal(first, second)
