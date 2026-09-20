import numpy as np
import pytest

from mintnet.metrics.topology import score_motif


def test_triangle_score_counts_any_pruned_true_edge():
    adjacency = np.array([[False, True, False], [True, False, True], [False, True, False]])
    assert score_motif(adjacency, "triangle")["true_edge_prune_fpr"] == 1 / 3
    assert np.isnan(score_motif(adjacency, "triangle")["indirect_prune_tpr"])


def test_chain_score_requires_indirect_edge_pruned_and_true_edges_retained():
    adjacency = np.array([[False, True, False], [True, False, True], [False, True, False]])
    assert score_motif(adjacency, "chain") == {
        "indirect_prune_tpr": 1.0,
        "true_edge_prune_fpr": 0.0,
        "perfect_recovery": 1.0,
    }


def test_score_rejects_invalid_motif_and_shape():
    with pytest.raises(ValueError):
        score_motif(np.zeros((2, 2), dtype=bool), "chain")
    with pytest.raises(ValueError):
        score_motif(np.zeros((3, 3), dtype=bool), "unknown")
