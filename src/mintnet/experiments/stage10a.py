"""DGP definition for docs/stage10a_charter.md -- a single, densely-
interconnected 14-node organic-shaped network (one connected component
with cycles, hubs, a broker, and dense local clusters) plus 4 noise
columns, unlike every prior DGP's disjoint small motifs (`chain_fork_
hub`, `overlap`, the triangle variants). See the charter for the full
topology rationale; `mintnet.simulation.motifs.sample_organic_network`
holds the actual precision matrix, verified positive definite at
import time.
"""

from __future__ import annotations

import numpy as np

from mintnet.simulation.motifs import ORGANIC_NETWORK_TRUE_EDGES, sample_organic_network

TRUE_DIRECT_EDGES: frozenset[tuple[int, int]] = frozenset(ORGANIC_NETWORK_TRUE_EDGES)
NOISE_COUNT = 4
P = 14 + NOISE_COUNT


def _sample_network(n: int, _strength: float, rng: np.random.Generator) -> np.ndarray:
    structural = sample_organic_network(n, rng)
    noise = rng.normal(size=(n, NOISE_COUNT))
    return np.column_stack([structural, noise])
