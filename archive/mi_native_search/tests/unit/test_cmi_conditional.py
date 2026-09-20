import numpy as np

from mintnet.dpi.cmi_conditional import compute_cmi_conditional_independence_evidence, prune_cmi_conditional_independence
from mintnet.simulation.motifs import sample_chain, sample_precision_triangle


def test_compute_cmi_conditional_independence_evidence_matches_expected_shape() -> None:
    rng = np.random.default_rng(0)
    data = sample_chain(600, 0.8, rng)

    evidence = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), k_cmi=10, k_perm=3, permutations=19
    )

    assert evidence.cmi.shape == (3, 3)
    assert evidence.p_value.shape == (3, 3)
    assert np.array_equal(evidence.cmi, evidence.cmi.T)
    assert np.array_equal(evidence.p_value, evidence.p_value.T)
    assert np.all(np.diag(evidence.cmi) == 0.0)


def test_compute_cmi_conditional_independence_evidence_is_deterministic() -> None:
    rng = np.random.default_rng(1)
    data = sample_chain(600, 0.8, rng)

    first = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), k_cmi=10, k_perm=3, permutations=19
    )
    second = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), k_cmi=10, k_perm=3, permutations=19
    )

    assert np.array_equal(first.cmi, second.cmi)
    assert np.array_equal(first.p_value, second.p_value)


def test_compute_cmi_conditional_independence_evidence_different_seed_context_differs() -> None:
    """The point estimate (`cmi`) is a deterministic function of the
    data alone -- no randomness there, by design -- so only `p_value`
    (driven by the permutation null) can differ here. Uses a higher
    permutation count than most tests in this file specifically to
    keep the two seeds' own p-values from coincidentally quantizing to
    the same value (a real risk at very low B, not a flaky test)."""
    rng = np.random.default_rng(2)
    data = sample_chain(600, 0.8, rng)

    first = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), k_cmi=10, k_perm=3, permutations=99
    )
    second = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 1), k_cmi=10, k_perm=3, permutations=99
    )

    assert np.array_equal(first.cmi, second.cmi)  # deterministic point estimate, same data
    assert not np.array_equal(first.p_value, second.p_value)  # different permutation draws


def test_prune_cmi_conditional_independence_recovers_chain_structure() -> None:
    """Reused evidence, thresholded at one alpha: chain's indirect
    (0, 2) pair should prune; the two true edges should retain."""
    rng = np.random.default_rng(3)
    data = sample_chain(1500, 0.8, rng)

    evidence = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), k_cmi=15, k_perm=3, permutations=49
    )
    adjacency = prune_cmi_conditional_independence(evidence, alpha=0.05)

    assert adjacency[0, 1] and adjacency[1, 2]
    assert not adjacency[0, 2]


def test_prune_cmi_conditional_independence_recovers_triangle_structure() -> None:
    """'balanced' (equal moderate partial correlations on all three
    edges), not 'strong' -- the 'strong' fixture deliberately has one
    very weak third edge (partial r=-0.08) as a hard case for the real
    charter's own alpha-selection process to resolve, not something a
    cheap plumbing check with reduced power should expect to recover."""
    rng = np.random.default_rng(4)
    data = sample_precision_triangle("balanced", 1500, rng)

    evidence = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 2, 0, 0, 0), k_cmi=20, k_perm=3, permutations=99
    )
    adjacency = prune_cmi_conditional_independence(evidence, alpha=0.05)

    assert adjacency[0, 1] and adjacency[0, 2] and adjacency[1, 2]


def test_prune_cmi_conditional_independence_reuses_evidence_across_alphas_without_recomputation() -> None:
    """The whole point of computing evidence once: thresholding at
    several alphas must not call the significance test again."""
    rng = np.random.default_rng(5)
    data = sample_chain(600, 0.8, rng)

    evidence = compute_cmi_conditional_independence_evidence(
        data, seed_context=(1, 0, 0, 0, 0), k_cmi=10, k_perm=3, permutations=19
    )
    for alpha in (0.5, 0.1, 0.05, 0.01):
        adjacency = prune_cmi_conditional_independence(evidence, alpha)
        assert adjacency.shape == (3, 3)
        assert not np.any(np.diag(adjacency))
