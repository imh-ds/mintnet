import numpy as np

from mintnet.pipeline import sequential_screen_and_prune
from mintnet.simulation import sample_chain, sample_measured_fork, sample_precision_triangle


def test_sequential_prunes_the_indirect_chain_edge_at_a_large_n():
    # N and alpha matched to mintnet.pipeline.compose_screen_then_prune's own
    # equivalent test (test_pipeline_compose.py) -- alpha must shrink as N
    # grows (D-009's per-N table) or even a near-zero residual partial
    # correlation becomes "significant" purely from statistical power, which
    # is a property of the shared Fisher-z test, not of either engine.
    rng = np.random.default_rng(1)
    data = sample_chain(2000, 0.7, rng)  # columns 0,1,2 = X1,X2,X3

    final = sequential_screen_and_prune(data, alpha=0.15)

    assert final[0, 1] and final[1, 2]  # direct edges retained
    assert not final[0, 2]  # indirect edge explained away by node 1


def test_sequential_prunes_the_induced_fork_edge_at_a_large_n():
    rng = np.random.default_rng(2)
    data = sample_measured_fork(2000, 0.7, rng)  # columns 0,1,2 = X1,X2,X3; 1 is the shared cause

    final = sequential_screen_and_prune(data, alpha=0.15)

    assert final[0, 1] and final[1, 2]
    assert not final[0, 2]


def test_sequential_retains_every_edge_of_a_genuine_triangle():
    rng = np.random.default_rng(3)
    data = sample_precision_triangle("strong", 2000, rng)

    final = sequential_screen_and_prune(data, alpha=0.15)

    assert final[0, 1] and final[0, 2] and final[1, 2]


def test_sequential_never_returns_a_self_edge_or_asymmetric_matrix():
    rng = np.random.default_rng(4)
    data = sample_chain(2000, 0.5, rng)

    final = sequential_screen_and_prune(data, alpha=0.10)

    assert not final.diagonal().any()
    assert np.array_equal(final, final.T)


def test_sequential_rejects_invalid_alpha():
    rng = np.random.default_rng(5)
    data = sample_chain(500, 0.5, rng)
    import pytest

    with pytest.raises(ValueError):
        sequential_screen_and_prune(data, alpha=0.0)
    with pytest.raises(ValueError):
        sequential_screen_and_prune(data, alpha=1.0)
