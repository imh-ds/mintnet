import numpy as np
import pytest

from mintnet.dpi import prune_tolerant_dpi


def test_dpi_prunes_only_when_weakest_edge_is_strictly_below_threshold():
    mi = np.array([[0, 0.9, 0.63], [0.9, 0, 0.8], [0.63, 0.8, 0.0]])
    assert not prune_tolerant_dpi(mi, 0.20)[0, 2]

    equal_threshold = (1.0 - 0.20) * 0.8
    equal = np.array(
        [[0, 0.9, equal_threshold], [0.9, 0, 0.8], [equal_threshold, 0.8, 0.0]]
    )
    assert prune_tolerant_dpi(equal, 0.20)[0, 2]


def test_dpi_prunes_one_float_below_threshold():
    threshold = (1.0 - 0.20) * 0.8
    weak = np.nextafter(threshold, -np.inf)
    mi = np.array([[0.0, 0.9, weak], [0.9, 0.0, 0.8], [weak, 0.8, 0.0]])
    assert not prune_tolerant_dpi(mi, 0.20)[0, 2]


def test_dpi_is_invariant_to_simultaneous_node_permutation():
    mi = np.array(
        [
            [0.0, 0.90, 0.70, 0.80],
            [0.90, 0.0, 0.85, 0.60],
            [0.70, 0.85, 0.0, 0.75],
            [0.80, 0.60, 0.75, 0.0],
        ]
    )
    permutation = np.array([2, 0, 3, 1])
    expected = prune_tolerant_dpi(mi, 0.20)
    permuted = prune_tolerant_dpi(mi[np.ix_(permutation, permutation)], 0.20)
    restored = permuted[np.ix_(np.argsort(permutation), np.argsort(permutation))]
    assert np.array_equal(restored, expected)


@pytest.mark.parametrize(
    "mi",
    [
        np.array([[0.0, 0.2, 0.3], [0.2, 0.0, 0.4]]),
        np.array([[0.0, 0.2], [0.3, 0.0]]),
        np.array([[0.0, np.nan], [np.nan, 0.0]]),
    ],
)
def test_dpi_rejects_invalid_mi_matrix(mi):
    with pytest.raises(ValueError):
        prune_tolerant_dpi(mi, 0.2)


@pytest.mark.parametrize("tau", [-0.01, 1.0, np.nan, np.inf])
def test_dpi_rejects_invalid_tolerance(tau):
    mi = np.eye(3)
    with pytest.raises(ValueError):
        prune_tolerant_dpi(mi, tau)
