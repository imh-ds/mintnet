"""A known-ground-truth network for Stage 2 candidate-edge screening.

Embeds Stage 1's validated chain, measured fork, and triangle motifs
(columns 0-8) among independent Gaussian noise columns, per
docs/stage2_charter.md. Ground truth is about nonzero vs. zero pairwise
correlation, not direct vs. indirect edges -- a chain's indirect
endpoints (columns 0, 2) have genuine nonzero population correlation and
are a true candidate pair here.
"""

from __future__ import annotations

import numpy as np

from .motifs import sample_chain, sample_measured_fork, sample_precision_triangle

TRUE_PAIR_INDICES: frozenset[tuple[int, int]] = frozenset(
    {(0, 1), (0, 2), (1, 2), (3, 4), (3, 5), (4, 5), (6, 7), (6, 8), (7, 8)}
)


def sample_screening_network(
    n: int, strength: float, triangle_family: str, noise_count: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw a p = 9 + noise_count column network with known candidate-edge ground truth."""
    if noise_count < 0:
        raise ValueError("noise_count must be non-negative")
    chain = sample_chain(n, strength, rng)
    fork = sample_measured_fork(n, strength, rng)
    triangle = sample_precision_triangle(triangle_family, n, rng)
    noise = rng.normal(size=(n, noise_count))
    return np.column_stack([chain, fork, triangle, noise])
