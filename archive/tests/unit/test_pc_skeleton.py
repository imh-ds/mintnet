import numpy as np

from mintnet.comparators.pc_skeleton import fit_pc_skeleton


def test_fit_pc_skeleton_recovers_chain_and_removes_marginal_edge() -> None:
    # X0 -- X1 -- X2, with X0 and X2 marginally correlated (via X1) but
    # conditionally independent given X1 -- the canonical PC textbook case.
    precision = np.array(
        [
            [1.0, -0.6, 0.0],
            [-0.6, 1.0, -0.6],
            [0.0, -0.6, 1.0],
        ]
    )
    covariance = np.linalg.inv(precision)
    rng = np.random.default_rng(0)
    data = rng.multivariate_normal(np.zeros(3), covariance, size=5000)

    result = fit_pc_skeleton(data, alpha=0.01)

    assert result.adjacency[0, 1] and result.adjacency[1, 0]
    assert result.adjacency[1, 2] and result.adjacency[2, 1]
    assert not result.adjacency[0, 2] and not result.adjacency[2, 0]
    assert not result.adjacency.diagonal().any()
    assert result.n_edges == 2
    assert result.max_conditioning_set_size >= 1


def test_fit_pc_skeleton_null_data_yields_sparse_or_empty_graph() -> None:
    rng = np.random.default_rng(1)
    data = rng.normal(size=(2000, 5))

    result = fit_pc_skeleton(data, alpha=0.01)

    assert result.n_edges <= 1


def test_fit_pc_skeleton_adjacency_is_symmetric() -> None:
    rng = np.random.default_rng(2)
    data = rng.normal(size=(500, 6))

    result = fit_pc_skeleton(data)

    np.testing.assert_array_equal(result.adjacency, result.adjacency.T)


def test_fit_pc_skeleton_fully_connected_when_alpha_is_one() -> None:
    rng = np.random.default_rng(3)
    data = rng.normal(size=(200, 4))

    # alpha=1 means every test "rejects" (p_value <= 1 always true) except
    # where a conditioning set makes the test degenerate -- with independent
    # noise columns and a lenient alpha, no edge should ever test independent.
    result = fit_pc_skeleton(data, alpha=1.0)

    expected_edges = 4 * 3 // 2
    assert result.n_edges == expected_edges
