import warnings

import numpy as np
import pytest

from mintnet.mi.ksg import estimate_ksg_mi
from mintnet.simulation.gaussian import gaussian_mi, sample_bivariate_gaussian


def test_ksg_is_symmetric_and_deterministic() -> None:
    """Changing joint/marginal counting asymmetrically would change the estimate."""
    sample = sample_bivariate_gaussian(500, 0.5, np.random.default_rng(17))
    forward = estimate_ksg_mi(sample[:, 0], sample[:, 1], k=5)
    reverse = estimate_ksg_mi(sample[:, 1], sample[:, 0], k=5)

    assert forward == pytest.approx(reverse)
    assert forward == estimate_ksg_mi(sample[:, 0], sample[:, 1], k=5)


@pytest.mark.parametrize(
    ("x", "y", "k", "message"),
    [
        ([1.0, 2.0], [1.0], 1, "same length"),
        ([1.0, np.nan, 3.0], [1.0, 2.0, 3.0], 1, "finite"),
        ([1.0, 1.0, 1.0], [1.0, 2.0, 3.0], 1, "nonzero variance"),
        ([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], 0, "1 <= k < n"),
        ([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], 3, "1 <= k < n"),
    ],
)
def test_ksg_rejects_invalid_bivariate_inputs(
    x: list[float], y: list[float], k: int, message: str
) -> None:
    """Removing input checks would produce invalid nearest-neighbor estimates."""
    with pytest.raises(ValueError, match=message):
        estimate_ksg_mi(x, y, k=k)


def test_ksg_rejects_mismatched_lengths_without_numeric_warning() -> None:
    """Validating variance before length would emit an avoidable numeric warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(ValueError, match="same length"):
            estimate_ksg_mi([1.0, 2.0], [1.0], k=1)


def test_ksg_recovers_a_fixed_gaussian_reference_within_tolerance() -> None:
    """Using the wrong KSG formula should fail against independent analytic truth."""
    sample = sample_bivariate_gaussian(2_000, 0.7, np.random.default_rng(2026))

    estimate = estimate_ksg_mi(sample[:, 0], sample[:, 1], k=5)

    assert estimate == pytest.approx(gaussian_mi(0.7), abs=0.10)
