import numpy as np
import pytest

from mintnet.mi.matrix import estimate_pairwise_mi


def test_pairwise_mi_is_symmetric_with_zero_diagonal():
    rng = np.random.default_rng(4)
    data = rng.normal(size=(80, 3))
    matrix = estimate_pairwise_mi(data, k=3)
    assert matrix.shape == (3, 3)
    assert np.array_equal(matrix, matrix.T)
    assert np.array_equal(np.diag(matrix), np.zeros(3))
    assert np.isfinite(matrix).all()


def test_pairwise_mi_rejects_non_three_column_data():
    with pytest.raises(ValueError):
        estimate_pairwise_mi(np.ones((20, 2)), k=3)
