import numpy as np
import pytest

from mintnet.experiments.stage8a_conditions import (
    CHAIN_FORK_STRENGTHS,
    TRIANGLE_FAMILIES,
    WEAK_EDGE_RHOS,
    all_conditions,
    condition_label,
    parse_condition,
    sample_condition,
    true_edges_for,
)


def test_all_conditions_round_trip_through_parse() -> None:
    for condition in all_conditions():
        family, param = parse_condition(condition)
        assert condition_label(family, param) == condition


def test_all_conditions_covers_every_swept_value() -> None:
    conditions = set(all_conditions())
    for strength in CHAIN_FORK_STRENGTHS:
        assert condition_label("chain", strength) in conditions
        assert condition_label("fork", strength) in conditions
    for family in TRIANGLE_FAMILIES:
        assert condition_label("triangle", family) in conditions
    for rho in WEAK_EDGE_RHOS:
        assert condition_label("weak_edge_triangle", rho) in conditions


@pytest.mark.parametrize("strength", CHAIN_FORK_STRENGTHS)
def test_chain_and_fork_true_edges_are_the_adjacent_pair(strength: float) -> None:
    for family in ("chain", "fork"):
        truth = true_edges_for(condition_label(family, strength))
        assert truth == {(0, 1): True, (0, 2): False, (1, 2): True}


@pytest.mark.parametrize("family", TRIANGLE_FAMILIES)
def test_triangle_true_edges_are_all_three(family: str) -> None:
    truth = true_edges_for(condition_label("triangle", family))
    assert truth == {(0, 1): True, (0, 2): True, (1, 2): True}


def test_weak_edge_triangle_third_edge_truth_tracks_target_rho() -> None:
    null = true_edges_for(condition_label("weak_edge_triangle", 0.0))
    assert null == {(0, 1): True, (0, 2): True, (1, 2): False}

    nonzero = true_edges_for(condition_label("weak_edge_triangle", 0.08))
    assert nonzero == {(0, 1): True, (0, 2): True, (1, 2): True}


def test_sample_condition_produces_a_three_column_array_for_every_condition() -> None:
    rng = np.random.default_rng(0)
    for condition in all_conditions():
        data = sample_condition(condition, 50, rng)
        assert data.shape == (50, 3)


def test_parse_condition_rejects_malformed_labels() -> None:
    with pytest.raises(ValueError, match="malformed condition label"):
        parse_condition("noparamhere")
