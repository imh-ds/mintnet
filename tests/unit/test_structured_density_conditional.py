import numpy as np

from mintnet.dpi.structured_density_conditional import (
    compute_structured_density_conditional_independence_evidence,
    prune_structured_density_conditional_independence,
)
from mintnet.simulation.motifs import sample_chain, sample_precision_triangle, sample_ushape_triangle


def test_compute_evidence_matches_expected_shape():
    rng = np.random.default_rng(0)
    data = sample_chain(600, 0.8, rng)

    evidence = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), permutations=19
    )

    assert evidence.cmi.shape == (3, 3)
    assert evidence.p_value.shape == (3, 3)
    assert np.array_equal(evidence.cmi, evidence.cmi.T)
    assert np.array_equal(evidence.p_value, evidence.p_value.T)
    assert np.all(np.diag(evidence.cmi) == 0.0)


def test_compute_evidence_is_deterministic():
    rng = np.random.default_rng(1)
    data = sample_chain(600, 0.8, rng)

    first = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), permutations=19
    )
    second = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), permutations=19
    )

    assert np.array_equal(first.cmi, second.cmi)
    assert np.array_equal(first.p_value, second.p_value)


def test_compute_evidence_different_seed_context_differs():
    """Unlike CMIknn's own point estimate (a deterministic function of
    data alone), this estimator's `cmi` itself depends on the
    cross-fitting fold assignment, which is drawn from `seed_context`
    -- so a different `seed_context` can shift *both* `cmi` and
    `p_value`, not just `p_value` as in `test_cmi_conditional.py`'s own
    equivalent test. This is expected, disclosed behavior (see
    `mintnet.mi.structured_density.local_permutation_test`'s own
    docstring on fixed-but-seeded folds), not nondeterminism."""
    rng = np.random.default_rng(2)
    data = sample_chain(600, 0.8, rng)

    first = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), permutations=99
    )
    second = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 1), permutations=99
    )

    assert not np.array_equal(first.cmi, second.cmi)
    assert not np.array_equal(first.p_value, second.p_value)


def test_prune_recovers_chain_structure():
    rng = np.random.default_rng(3)
    data = sample_chain(1500, 0.8, rng)

    evidence = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), permutations=49
    )
    adjacency = prune_structured_density_conditional_independence(evidence, alpha=0.05)

    assert adjacency[0, 1] and adjacency[1, 2]
    assert not adjacency[0, 2]


def test_prune_recovers_triangle_structure():
    rng = np.random.default_rng(4)
    data = sample_precision_triangle("balanced", 1500, rng)

    evidence = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 2, 0, 0, 0), permutations=99
    )
    adjacency = prune_structured_density_conditional_independence(evidence, alpha=0.05)

    assert adjacency[0, 1] and adjacency[0, 2] and adjacency[1, 2]


def test_prune_recovers_the_ushape_edge_that_a_linear_test_cannot_see():
    """The point of this whole estimator: a real, strong quadratic
    dependence must survive pruning at a conventional alpha, unlike a
    Fisher-z/partial-correlation test, which sees exactly zero
    correlation here by this fixture's own construction."""
    rng = np.random.default_rng(6)
    data = sample_ushape_triangle(0.6, 1500, rng)

    evidence = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 3, 0, 0, 0), permutations=99
    )
    adjacency = prune_structured_density_conditional_independence(evidence, alpha=0.05)

    assert adjacency[1, 2]


def test_prune_reuses_evidence_across_alphas_without_recomputation():
    rng = np.random.default_rng(5)
    data = sample_chain(600, 0.8, rng)

    evidence = compute_structured_density_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), permutations=19
    )
    for alpha in (0.5, 0.1, 0.05, 0.01):
        adjacency = prune_structured_density_conditional_independence(evidence, alpha)
        assert adjacency.shape == (3, 3)
        assert not np.any(np.diag(adjacency))
