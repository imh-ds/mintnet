"""Local-permutation null construction (Runge, 2018), shared by every
conditional-independence significance test in this project that has no
closed-form null distribution -- originally built and calibrated for
`mintnet.mi.cmiknn`'s own CMIknn estimator (see that module's own
docstring for D-055's fix history), and reused as-is by
`mintnet.mi.structured_density`'s own estimator.

The construction itself does not depend on which CMI/MI point estimator
is plugged in downstream -- it is purely a resampling scheme over
indices, built to preserve each point's own local Z-neighborhood
structure under the null. Factoring it out here means two estimators
being compared head-to-head (Stage 7d's own purpose) share the *same*
validated null construction, isolating any difference in results to
the estimator itself, not to a second, independently-built permutation
scheme.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def z_neighbors(z_standardized: np.ndarray, k_perm: int) -> np.ndarray:
    """Each point's `k_perm` nearest Z-neighbors, self-inclusive,
    Chebyshev/max-norm distance -- matches Runge/tigramite's own
    `CMIknn.get_shuffle_significance` exactly (see
    `mintnet.mi.cmiknn`'s own docstring, points 1 and 3). Computed once
    per significance test, not once per permutation replicate, since Z
    is fixed throughout."""
    n = z_standardized.shape[0]
    k = min(k_perm, n)
    tree = cKDTree(z_standardized)
    _, neighbor_idx = tree.query(z_standardized, k=k, p=np.inf)
    if k == 1:
        neighbor_idx = neighbor_idx[:, None]
    return neighbor_idx.astype(int)


def restricted_permutation(neighbors: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Runge/tigramite's own `get_restricted_permutation`: shuffle each
    point's own (self-inclusive) neighbor list, then visit points in a
    random order and assign each one the first not-yet-used neighbor
    from its own shuffled list. If every one of a point's `k_perm`
    neighbors is already claimed, reuse the last one anyway (an
    accepted, rare collision) rather than reaching outside the local
    neighborhood -- see `mintnet.mi.cmiknn`'s own docstring, D-055's
    fix point 2."""
    n, k = neighbors.shape
    shuffled = neighbors.copy()
    for row in shuffled:
        rng.shuffle(row)

    order = rng.permutation(n)
    used = np.zeros(n, dtype=bool)
    perm = np.empty(n, dtype=int)
    for i in order:
        m = 0
        use = int(shuffled[i, m])
        while used[use] and m < k - 1:
            m += 1
            use = int(shuffled[i, m])
        perm[i] = use
        used[use] = True
    return perm
