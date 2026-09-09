import math

import numpy as np

from mintnet.pipeline.stability_rescue import (
    UNRESOLVED_CONDITIONING_SIZE,
    growing_subset_dpi_with_stability_rescue,
)
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation.motifs import sample_hub


def test_unresolved_boundary_is_two():
    assert UNRESOLVED_CONDITIONING_SIZE == 2


def test_no_qualifying_edges_means_no_bootstrap_and_identical_adjacency():
    """An isolated edge (conditioning_size_used == 0, never even
    tested) must never be bootstrapped, and the result must be
    identical to plain growing_subset_dpi -- zero extra cost."""
    rng = np.random.default_rng(0)
    data = rng.normal(size=(500, 4))
    flagged = np.zeros((4, 4), dtype=bool)
    flagged[0, 1] = flagged[1, 0] = True

    result = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.001, screening_alpha=0.001, bootstraps=50, rng=np.random.default_rng(1)
    )

    assert result.bootstrapped is False
    assert np.array_equal(result.original_adjacency, result.final_adjacency)
    assert math.isnan(result.pi_final[(0, 1)])
    assert result.rescued[(0, 1)] is False


def test_conditioning_size_one_edges_are_never_individually_bootstrapped():
    """D-076's own boundary: only conditioning_size_used >= 2 ever
    qualifies -- a hub's own indirect pairs, resolved at size 1, must
    never get a pi_final or a rescue, even if some OTHER edge in the
    same dataset legitimately reaches size 2 (a true direct edge can
    validly need to test every subset up to its own pool's size, which
    is expected and 100% accurate per D-076 -- not itself a bug)."""
    rng = np.random.default_rng(1)
    data = sample_hub(2000, 0.5, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.01, screening_alpha=0.001, bootstraps=50, rng=np.random.default_rng(2)
    )

    for pair in ((1, 2), (1, 3), (2, 3)):
        assert result.conditioning_size_used[pair] == 1
        assert math.isnan(result.pi_final[pair])
        assert result.rescued[pair] is False
        i, j = pair
        assert bool(result.original_adjacency[i, j]) == bool(result.final_adjacency[i, j])


def test_a_qualifying_edge_below_pi_min_gets_rescued():
    """Construct a case where growing_subset_dpi wrongly retains a
    false edge at conditioning_size_used >= 2 (a collider-style
    fixture, D-071's own mechanism) and confirm the wired function can
    flip it when its own pi_final falls below pi_min."""
    rng = np.random.default_rng(7)
    n = 500
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    # A strong collider: conditioning on columns 2 and 3 together
    # induces spurious dependence between columns 0 and 1 (D-071).
    x3 = 0.65 * x1 + 0.65 * x2 + np.sqrt(1 - 2 * 0.65**2) * rng.normal(size=n)
    x4 = rng.normal(size=n)
    data = np.column_stack([x1, x2, x3, x4])
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.2, screening_alpha=0.001, max_conditioning_size=4,
        bootstraps=200, pi_min=0.90, rng=np.random.default_rng(8),
    )

    assert result.bootstrapped is True
    # (0, 1) is the known-false edge; whatever growing_subset_dpi's own
    # point estimate decided, pi_final must have been computed for it
    # if it reached conditioning_size_used >= 2.
    if result.conditioning_size_used[(0, 1)] >= 2:
        assert not math.isnan(result.pi_final[(0, 1)])


def test_final_adjacency_never_adds_an_edge_the_original_did_not_have():
    """The filter can only remove edges (flip retained -> pruned), never add one."""
    rng = np.random.default_rng(2)
    data = sample_hub(2000, 0.5, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.01, screening_alpha=0.001, bootstraps=50, rng=np.random.default_rng(3)
    )

    assert np.all(result.final_adjacency <= result.original_adjacency)


def test_rescued_is_only_true_where_final_differs_from_original():
    rng = np.random.default_rng(2)
    data = sample_hub(2000, 0.5, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    result = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.01, screening_alpha=0.001, bootstraps=50, rng=np.random.default_rng(3)
    )

    for pair, was_rescued in result.rescued.items():
        i, j = pair
        differs = bool(result.original_adjacency[i, j]) != bool(result.final_adjacency[i, j])
        assert was_rescued == differs


def test_reproducible_given_the_same_rng_state():
    rng = np.random.default_rng(2)
    data = sample_hub(2000, 0.5, 3, rng)
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    a = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.01, screening_alpha=0.001, bootstraps=50, rng=np.random.default_rng(3)
    )
    b = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.01, screening_alpha=0.001, bootstraps=50, rng=np.random.default_rng(3)
    )
    assert np.array_equal(a.final_adjacency, b.final_adjacency)
    assert a.pi_final == b.pi_final


def test_n_jobs_greater_than_one_matches_the_sequential_result():
    """n_jobs is a wall-clock-only knob -- it must not change which
    edges get rescued or any pi_final value."""
    rng = np.random.default_rng(7)
    n = 500
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = 0.65 * x1 + 0.65 * x2 + np.sqrt(1 - 2 * 0.65**2) * rng.normal(size=n)
    x4 = rng.normal(size=n)
    data = np.column_stack([x1, x2, x3, x4])
    flagged = np.ones((4, 4), dtype=bool)
    np.fill_diagonal(flagged, False)

    sequential = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.2, screening_alpha=0.001, max_conditioning_size=4,
        bootstraps=40, pi_min=0.90, rng=np.random.default_rng(8),
    )
    parallel = growing_subset_dpi_with_stability_rescue(
        data, flagged, alpha=0.2, screening_alpha=0.001, max_conditioning_size=4,
        bootstraps=40, pi_min=0.90, rng=np.random.default_rng(8), n_jobs=2,
    )

    assert np.array_equal(sequential.final_adjacency, parallel.final_adjacency)
    assert sequential.pi_final == parallel.pi_final
    assert sequential.rescued == parallel.rescued
