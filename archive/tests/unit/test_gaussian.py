import math

import numpy as np
import pytest

from mintnet.simulation.gaussian import gaussian_mi, sample_bivariate_gaussian


def test_gaussian_mi_matches_known_analytic_values() -> None:
    """Changing the reference formula would invalidate known Gaussian truth."""
    assert gaussian_mi(0.0) == 0.0
    assert gaussian_mi(0.5) == pytest.approx(0.1438410362)
    assert gaussian_mi(0.9) == pytest.approx(0.8303656034)


@pytest.mark.parametrize("rho", [-1.0, 1.0, 1.1])
def test_gaussian_mi_rejects_nonpositive_definite_correlations(rho: float) -> None:
    """Accepting |rho| >= 1 would claim finite MI for a singular covariance."""
    with pytest.raises(ValueError, match="-1 < rho < 1"):
        gaussian_mi(rho)


def test_bivariate_gaussian_is_seeded_and_has_requested_correlation() -> None:
    """Changing the DGP covariance or RNG handling would break reproducibility/truth."""
    first = sample_bivariate_gaussian(20_000, 0.7, np.random.default_rng(91))
    second = sample_bivariate_gaussian(20_000, 0.7, np.random.default_rng(91))

    assert first.shape == (20_000, 2)
    assert np.array_equal(first, second)
    assert np.isfinite(first).all()
    assert math.isclose(np.corrcoef(first.T)[0, 1], 0.7, abs_tol=0.02)
