import numpy as np
import pytest

from mintnet.api import (
    UntestedEffectSizeError,
    _build_edge_decisions,
    _rescue_qualifying_rate_warning,
    _required_min_n,
    _resolve_pi_min,
    discover,
)


# -- _required_min_n (D-083's own frontier table, collapsed to a step function) --


def test_required_min_n_matches_d083_frontier_table():
    assert _required_min_n(0.20) == 400
    assert _required_min_n(0.12) == 400
    assert _required_min_n(0.10) == 1000
    assert _required_min_n(0.08) == 1000


def test_required_min_n_raises_below_every_tested_effect_size():
    with pytest.raises(UntestedEffectSizeError):
        _required_min_n(0.05)


# -- _resolve_pi_min (D-087's own two calibrated points, no interpolation) --


def test_resolve_pi_min_uses_calibrated_value_at_750_and_1500_with_no_warning():
    warnings: list[str] = []
    assert _resolve_pi_min(750, warnings) == 0.5
    assert _resolve_pi_min(1500, warnings) == 0.6
    assert warnings == []


def test_resolve_pi_min_falls_back_conservatively_with_a_warning_for_untested_n():
    warnings: list[str] = []
    assert _resolve_pi_min(1024, warnings) == 0.6
    assert len(warnings) == 1
    assert "1024" in warnings[0]


# -- discover: upfront guardrails --


def test_discover_raises_when_n_below_the_required_floor_for_the_stated_effect_size():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(300, 4))  # below the N=1000 floor for a 0.08 effect
    with pytest.raises(ValueError, match="below the minimum"):
        discover(data, weakest_expected_effect=0.08)


def test_discover_raises_untested_effect_size_error_before_touching_n():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(300, 4))
    with pytest.raises(UntestedEffectSizeError):
        discover(data, weakest_expected_effect=0.03)


def test_discover_on_null_data_returns_no_edges_and_zero_qualifying_rate():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(400, 4))  # independent columns, nothing should screen in
    result = discover(data, weakest_expected_effect=0.12, random_state=1)
    assert result.edges == []
    assert result.qualifying_rate == 0.0
    assert result.rescue_used is False


def test_discover_warns_when_n_is_outside_the_two_validated_rescue_points():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(400, 4))
    result = discover(data, weakest_expected_effect=0.12, random_state=1)
    assert any("outside the two points" in w for w in result.warnings)


# -- _rescue_qualifying_rate_warning: regression test for the exact
# failure caught when trying this against real overlap-DGP data (see
# outline/api_design_v1.md, 2026-09-14 correction) -- must never call a
# rate "well-supported" just because it is numerically nearer
# chain_fork_hub's own reference point than overlap's own.


def test_qualifying_rate_warning_near_the_validated_point_is_affirmative():
    message = _rescue_qualifying_rate_warning(0.05)
    assert "validated" in message and "NOT" not in message


def test_qualifying_rate_warning_never_affirms_support_for_a_rate_this_project_has_no_evidence_for():
    """The exact regression case: 43.75% is numerically nearer
    chain_fork_hub's ~7.4% than overlap's ~100%, but this rate was
    observed on data actually drawn from the unvalidated overlap DGP --
    it must never be described as well-supported or safe."""
    message = _rescue_qualifying_rate_warning(0.4375)
    assert "NOT" in message
    assert "well-supported" not in message
    assert "reasonably" not in message


def test_discover_does_not_warn_about_rescue_interpolation_at_a_validated_n():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(750, 4))
    result = discover(data, weakest_expected_effect=0.12, random_state=1)
    assert not any("outside the two points" in w for w in result.warnings)


# -- _build_edge_decisions: the safety-critical flagging logic, tested directly --
# (D-085's own risk category is a RETAINED edge at conditioning depth >= 2,
# not a pruned one -- see the corrected direction in outline/api_design_v1.md.
# These synthetic inputs let us check every branch without an expensive
# structured-density search.)


def _adjacency(p: int, retained_pairs: set[tuple[int, int]]) -> np.ndarray:
    a = np.zeros((p, p), dtype=bool)
    for i, j in retained_pairs:
        a[i, j] = a[j, i] = True
    return a


def test_shallow_retained_edge_is_never_flagged():
    edges = _build_edge_decisions(
        candidate_pairs=[(0, 1)], deep_pairs=[], final_adjacency=_adjacency(2, {(0, 1)}),
        conditioning_size_used={(0, 1): 1}, confidence={(0, 1): 0.9},
        pi_final_by_pair={}, rescue_used=False,
    )
    assert edges[0].retained is True
    assert edges[0].low_confidence is False


def test_deep_pruned_edge_is_never_flagged_even_without_rescue():
    edges = _build_edge_decisions(
        candidate_pairs=[(0, 1)], deep_pairs=[(0, 1)], final_adjacency=_adjacency(2, set()),
        conditioning_size_used={(0, 1): 2}, confidence={(0, 1): 0.5},
        pi_final_by_pair={}, rescue_used=False,
    )
    assert edges[0].retained is False
    assert edges[0].low_confidence is False


def test_deep_retained_edge_without_rescue_is_flagged_low_confidence():
    """The exact failure mode D-085 found: a retained edge at depth >= 2
    with no rescue applied has no basis for trust (accuracy on this
    category collapses .906 -> .119 by depth)."""
    edges = _build_edge_decisions(
        candidate_pairs=[(0, 1)], deep_pairs=[(0, 1)], final_adjacency=_adjacency(2, {(0, 1)}),
        conditioning_size_used={(0, 1): 3}, confidence={(0, 1): 0.6},
        pi_final_by_pair={}, rescue_used=False,
    )
    assert edges[0].retained is True
    assert edges[0].low_confidence is True
    assert edges[0].rescue_applied is False


def test_deep_retained_edge_confirmed_by_rescue_is_not_flagged():
    edges = _build_edge_decisions(
        candidate_pairs=[(0, 1)], deep_pairs=[(0, 1)], final_adjacency=_adjacency(2, {(0, 1)}),
        conditioning_size_used={(0, 1): 3}, confidence={(0, 1): 0.6},
        pi_final_by_pair={(0, 1): 0.9}, rescue_used=True,
    )
    assert edges[0].retained is True
    assert edges[0].low_confidence is False
    assert edges[0].rescue_applied is True
    assert edges[0].pi_final == 0.9


def test_deep_edge_flipped_by_rescue_exits_retained_bucket_and_is_not_flagged():
    """Rescue corrected this edge from retained to pruned -- the flip
    itself is the validated outcome (D-087), not something to flag."""
    edges = _build_edge_decisions(
        candidate_pairs=[(0, 1)], deep_pairs=[(0, 1)], final_adjacency=_adjacency(2, set()),
        conditioning_size_used={(0, 1): 3}, confidence={(0, 1): 0.6},
        pi_final_by_pair={(0, 1): 0.2}, rescue_used=True,
    )
    assert edges[0].retained is False
    assert edges[0].low_confidence is False
    assert edges[0].rescue_applied is True
    assert edges[0].pi_final == 0.2
