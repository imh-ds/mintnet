import math

import numpy as np

from mintnet.confidence import edge_margin, edge_margins
from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi
from mintnet.simulation.motifs import sample_hub


def test_edge_margin_is_zero_exactly_at_the_decision_boundary() -> None:
    assert edge_margin(0.05, alpha=0.05, retained=True) == 0.0
    assert edge_margin(0.05, alpha=0.05, retained=False) == 0.0


def test_edge_margin_is_one_at_maximum_distance_from_the_boundary() -> None:
    assert edge_margin(0.0, alpha=0.05, retained=True) == 1.0
    assert edge_margin(1.0, alpha=0.05, retained=False) == 1.0


def test_edge_margin_confidently_retained_and_confidently_pruned_both_score_high() -> None:
    """A p-value far below alpha (confidently retained) and a p-value
    far above alpha (confidently pruned) should both read as high
    confidence -- margin is decision-relative, not raw 1 - p_value."""
    confidently_retained = edge_margin(0.001, alpha=0.05, retained=True)
    confidently_pruned = edge_margin(0.95, alpha=0.05, retained=False)

    assert confidently_retained > 0.9
    assert confidently_pruned > 0.9


def test_edge_margin_near_boundary_scores_low_regardless_of_which_way_the_decision_went() -> None:
    barely_retained = edge_margin(0.049, alpha=0.05, retained=True)
    barely_pruned = edge_margin(0.051, alpha=0.05, retained=False)

    assert barely_retained < 0.05
    assert barely_pruned < 0.05


def test_edge_margin_is_bounded_in_zero_one() -> None:
    """Bounded for every (p, retained) pair consistent with how
    growing_subset_dpi actually derives them -- retained only ever
    means every tested p_value was <= alpha, pruned only ever means
    the triggering p_value was > alpha."""
    alpha = 0.05
    for p in (0.0, 0.001, 0.04, alpha):
        assert 0.0 <= edge_margin(p, alpha=alpha, retained=True) <= 1.0
    for p in (alpha + 1e-9, 0.06, 0.5, 0.99, 1.0):
        assert 0.0 <= edge_margin(p, alpha=alpha, retained=False) <= 1.0


def test_edge_margin_propagates_nan_for_no_valid_evidence() -> None:
    assert math.isnan(edge_margin(math.nan, alpha=0.05, retained=True))


def test_edge_margins_matches_edge_margin_for_every_candidate_pair() -> None:
    rng = np.random.default_rng(1)
    data = sample_hub(2000, 0.5, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)
    alpha = 0.01

    result = growing_subset_dpi(data, flagged, alpha=alpha)
    margins = edge_margins(result, alpha)

    assert set(margins) == set(result.decisive_p_value)
    for pair, p_value in result.decisive_p_value.items():
        expected = edge_margin(p_value, alpha, retained=bool(result.adjacency[pair]))
        if math.isnan(expected):
            assert math.isnan(margins[pair])
        else:
            assert margins[pair] == expected
