"""Screen-then-prune pipeline composition, per docs/stage2b_charter.md,
docs/stage2c_charter.md, and docs/stage2d_charter.md.

Screening produces a candidate-edge graph. Candidate edges are grouped
into connected components; DPI conditioning (general multi-variable
conditioning, mintnet.dpi.multi_conditional -- proven numerically
equivalent to Stage 1's original one-variable mechanism when there is
exactly one conditioning variable, see
tests/unit/test_multi_conditional.py) is applied only within components
that are a *validated clique shape*: every pair within the component is
itself a candidate edge, and the component has 3 nodes (Stage 1's
original triad, D-008-D-012), 4 nodes (the hub shape, D-015), or 5 nodes
(shared-node overlap, D-017; extended to any 5-node clique per
docs/stage2d_charter.md, since screening cannot reveal which specific
5-node topology a clean clique represents -- only that it is one).
Every other component -- non-clique shapes, or cliques of any other size
-- is passed through unmodified. This is a stated scope boundary, not an
oversight: the code can mechanically run the conditioning test on any
component size, but only these three sizes have supporting evidence, and
even for validated sizes, whether screening reliably *produces* a clean
clique in the first place is a separate, DGP-dependent question (see
D-017's and D-016's discussion of detection power).
"""

from itertools import combinations

import numpy as np
from scipy.sparse.csgraph import connected_components as _scipy_connected_components

from mintnet.dpi import prune_pair

VALIDATED_CLIQUE_SIZES: frozenset[int] = frozenset({3, 4, 5})


def connected_components(flagged: np.ndarray) -> list[frozenset[int]]:
    """Group nodes with at least one candidate edge into connected components."""
    _, labels = _scipy_connected_components(csgraph=flagged, directed=False)
    groups: dict[int, set[int]] = {}
    for node, label in enumerate(labels):
        groups.setdefault(int(label), set()).add(node)
    return [frozenset(nodes) for nodes in groups.values() if len(nodes) >= 2]


def _is_candidate_clique(component: frozenset[int], flagged: np.ndarray) -> bool:
    nodes = sorted(component)
    return all(flagged[i, j] for i, j in combinations(nodes, 2))


def describe_component(component: frozenset[int], flagged: np.ndarray) -> dict[str, object]:
    """Descriptive shape info for one connected component (for reporting)."""
    is_clique = _is_candidate_clique(component, flagged)
    return {
        "size": len(component),
        "is_clique": is_clique,
        "is_validated_shape": is_clique and len(component) in VALIDATED_CLIQUE_SIZES,
    }


def compose_screen_then_prune(
    data: np.ndarray, flagged: np.ndarray, alpha: float
) -> tuple[np.ndarray, dict[frozenset[int], dict[str, object]]]:
    """Apply DPI within every validated-shape candidate component; pass through the rest.

    Returns the final p x p adjacency matrix and a dict mapping each
    connected component to its shape descriptor (size, whether it was a
    clique, whether that clique size is validated) for reporting how often
    each shape actually occurs.
    """
    final = flagged.copy()
    shapes: dict[frozenset[int], dict[str, object]] = {}

    for component in connected_components(flagged):
        shape = describe_component(component, flagged)
        shapes[component] = shape
        if not shape["is_validated_shape"]:
            continue
        nodes = sorted(component)
        sub_data = data[:, nodes]
        m = len(nodes)
        for local_i, local_j in combinations(range(m), 2):
            conditioning = [k for k in range(m) if k not in (local_i, local_j)]
            retained = prune_pair(sub_data, local_i, local_j, conditioning, alpha)
            final[nodes[local_i], nodes[local_j]] = retained
            final[nodes[local_j], nodes[local_i]] = retained

    return final, shapes
