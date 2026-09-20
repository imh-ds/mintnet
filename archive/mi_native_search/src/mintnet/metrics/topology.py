"""Motif-level scoring for retained adjacency matrices."""

from typing import Literal

import numpy as np

Motif = Literal["chain", "fork", "triangle"]


def score_motif(adjacency: np.ndarray, motif: Motif) -> dict[str, float]:
    """Score indirect-edge pruning and genuine-edge retention for a motif."""
    if motif not in ("chain", "fork", "triangle"):
        raise ValueError("motif must be 'chain', 'fork', or 'triangle'")
    raw_graph = np.asarray(adjacency)
    if raw_graph.shape != (3, 3):
        raise ValueError("adjacency must be a 3 by 3 matrix")
    if raw_graph.dtype != np.dtype(bool):
        raise ValueError("adjacency must be boolean")
    graph = raw_graph
    if not np.array_equal(graph, graph.T) or np.any(np.diag(graph)):
        raise ValueError("adjacency must be symmetric with a false diagonal")

    if motif == "triangle":
        true_edges = ((0, 1), (0, 2), (1, 2))
        indirect_tpr = float("nan")
    else:
        true_edges = ((0, 1), (1, 2))
        indirect_tpr = float(not graph[0, 2])
    pruned_true = sum(not graph[left, right] for left, right in true_edges)
    true_edge_fpr = float(pruned_true / len(true_edges))
    perfect = float(indirect_tpr == 1.0 and true_edge_fpr == 0.0) if motif != "triangle" else float(true_edge_fpr == 0.0)
    return {
        "indirect_prune_tpr": indirect_tpr,
        "true_edge_prune_fpr": true_edge_fpr,
        "perfect_recovery": perfect,
    }
