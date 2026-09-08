import numpy as np
import pandas as pd
import pytest

from mintnet.experiments.stage8i_population_ground_truth import (
    build_covariance,
    classify_subset_members,
    enrich_with_population_ground_truth,
    evaluate_h6,
    population_partial_correlation,
)


@pytest.mark.parametrize("dgp", ["chain_fork_hub", "overlap"])
def test_build_covariance_is_positive_definite_and_unit_diagonal(dgp):
    covariance = build_covariance(dgp, strength=0.5)
    assert covariance.shape == (15, 15)
    np.testing.assert_allclose(np.diag(covariance), 1.0)
    np.linalg.cholesky(covariance)  # raises if not positive definite


def test_build_covariance_matches_empirical_chain_fork_hub_correlation_at_large_n():
    from mintnet.experiments.stage5a import _DGP_REGISTRY

    rng = np.random.default_rng(0)
    data = _DGP_REGISTRY["chain_fork_hub"]["sample"](500_000, 0.5, rng)
    empirical = np.corrcoef(data.T)
    covariance = build_covariance("chain_fork_hub", 0.5)
    np.testing.assert_allclose(empirical, covariance, atol=0.02)


def test_build_covariance_matches_empirical_overlap_correlation_at_large_n():
    from mintnet.experiments.stage5a import _DGP_REGISTRY

    rng = np.random.default_rng(1)
    data = _DGP_REGISTRY["overlap"]["sample"](500_000, 0.5, rng)
    empirical = np.corrcoef(data.T)
    covariance = build_covariance("overlap", 0.5)
    np.testing.assert_allclose(empirical, covariance, atol=0.03)


def test_population_partial_correlation_is_exactly_zero_for_chains_own_indirect_pair():
    """Chain's own already-validated ground truth: X1, X3 are exactly
    conditionally independent given X2 alone, in the population."""
    covariance = build_covariance("chain_fork_hub", strength=0.5)
    assert population_partial_correlation(covariance, 0, 2, (1,)) == pytest.approx(0.0, abs=1e-10)


def test_population_partial_correlation_stays_zero_when_unrelated_blocks_are_added():
    """The core claim this charter tests: adding cross-block variables
    (fork's own center, hub members, noise) to chain's own already-
    correct conditioning set changes NOTHING about the population
    conditional relationship -- block independence guarantees this
    analytically, checked here directly."""
    covariance = build_covariance("chain_fork_hub", strength=0.5)
    for subset in ((1, 4), (1, 7, 8), (1, 10), (1, 6, 7, 8)):
        assert population_partial_correlation(covariance, 0, 2, subset) == pytest.approx(0.0, abs=1e-10)


def test_population_partial_correlation_is_zero_for_cross_motif_pairs_given_any_subset():
    """A pair from two different, mutually independent blocks (e.g.
    column 0 from chain, column 9 a noise column) is population-
    independent given ANY conditioning content at all."""
    covariance = build_covariance("chain_fork_hub", strength=0.5)
    for subset in ((), (1,), (4, 7), (1, 4, 6, 8)):
        assert population_partial_correlation(covariance, 0, 9, subset) == pytest.approx(0.0, abs=1e-10)


def test_population_partial_correlation_is_nonzero_within_a_true_dependency():
    """Sanity check the formula itself isn't trivially always zero:
    conditioning on nothing, X1 and X2 (adjacent chain members) are
    genuinely correlated."""
    covariance = build_covariance("chain_fork_hub", strength=0.5)
    assert abs(population_partial_correlation(covariance, 0, 1, ())) > 0.4


def test_classify_subset_members_counts_different_block_members_for_chain():
    result = classify_subset_members("chain_fork_hub", (0, 2), decisive_conditioning_subset=(1, 4, 7))
    assert result == {"same_block": 0, "different_block": 2}


def test_classify_subset_members_counts_same_block_members_for_overlap_shared_node_pair():
    """Overlap's own 5-node block (columns 6-10) means a pair like
    (6, 9) can have an EXTRA same-block member (7 or 10) besides the
    shared separator (8) -- structurally impossible for chain/fork/hub's
    own 3-node blocks."""
    result = classify_subset_members("overlap", (6, 9), decisive_conditioning_subset=(8, 7, 12))
    assert result == {"same_block": 1, "different_block": 1}


def test_enrich_with_population_ground_truth_flags_no_violation_for_synthetic_flagged_rows():
    candidates = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "n": 750, "replicate": 0, "i": 0, "j": 2, "correct": False, "decisive_conditioning_subset": (1, 7, 8), "chance_correlation": 0.3},
            {"dgp": "chain_fork_hub", "n": 750, "replicate": 1, "i": 3, "j": 5, "correct": False, "decisive_conditioning_subset": (4, 12), "chance_correlation": 0.2},
        ]
    )
    enriched = enrich_with_population_ground_truth(candidates, {"chain_fork_hub": 0.5})
    assert (enriched["population_partial_correlation"].abs() < 1e-9).all()
    assert (enriched["is_named_indirect_pair"]).all()

    verdict = evaluate_h6(enriched)
    assert verdict.status == "NOT_CONFIRMED"
    assert verdict.violating_row_count == 0


def test_evaluate_h6_confirms_when_a_row_exceeds_tolerance():
    enriched = pd.DataFrame(
        [{"population_partial_correlation": 0.2}, {"population_partial_correlation": 0.01}]
    )
    verdict = evaluate_h6(enriched, tolerance=0.05)
    assert verdict.status == "CONFIRMED"
    assert verdict.violating_row_count == 1


def test_evaluate_h6_not_confirmed_on_empty_input():
    verdict = evaluate_h6(pd.DataFrame(columns=["population_partial_correlation"]))
    assert verdict.status == "NOT_CONFIRMED"
    assert verdict.total_row_count == 0


def test_evaluate_h6_ignores_correctly_pruned_rows_even_if_nonzero():
    """A correctly-pruned edge's own decisive subset only needs to look
    insignificant, not be a formal population separator -- a nonzero
    population value there is expected and benign (see the real
    evidence: 370/2,163 correctly-pruned rows show this), and must not
    inflate H6's own violation count, which concerns only WRONGLY-
    retained edges."""
    enriched = pd.DataFrame(
        [
            {"population_partial_correlation": 0.2, "correct": True},  # benign, correctly pruned
            {"population_partial_correlation": 0.01, "correct": False},
        ]
    )
    verdict = evaluate_h6(enriched, tolerance=0.05)
    assert verdict.status == "NOT_CONFIRMED"
    assert verdict.violating_row_count == 0
    assert verdict.total_row_count == 1
