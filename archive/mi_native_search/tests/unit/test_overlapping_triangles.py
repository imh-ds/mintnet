import numpy as np
import pytest

from mintnet.simulation import sample_overlapping_triangles

WITHIN_PAIRS = ((0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4))
CROSS_PAIRS = ((0, 3), (0, 4), (1, 3), (1, 4))


def test_sample_shape():
    data = sample_overlapping_triangles(500, np.random.default_rng(1))
    assert data.shape == (500, 5)


def test_within_triangle_correlations_are_stronger_than_cross_triangle():
    rng = np.random.default_rng(2)
    data = sample_overlapping_triangles(200000, rng)
    corr = np.corrcoef(data, rowvar=False)

    within = [abs(corr[i, j]) for i, j in WITHIN_PAIRS]
    cross = [abs(corr[i, j]) for i, j in CROSS_PAIRS]

    assert min(within) > max(cross)
    assert max(cross) > 0.05  # cross-branch correlation is real, just weaker


def test_within_triangle_correlations_are_symmetric_and_roughly_equal():
    rng = np.random.default_rng(3)
    data = sample_overlapping_triangles(200000, rng)
    corr = np.corrcoef(data, rowvar=False)

    within = [corr[i, j] for i, j in WITHIN_PAIRS]
    assert max(within) - min(within) < 0.05  # symmetric balanced-style construction
