import numpy as np
import pytest

from mintnet.mi.structured_density import estimate_structured_cmi
from mintnet.simulation.motifs import (
    sample_monotonic_curvature_triangle,
    sample_ushape_triangle,
    sample_weak_edge_triangle,
)


def _closed_form_gaussian_cmi(rho: float) -> float:
    return -0.5 * np.log(1.0 - rho**2)


@pytest.mark.parametrize("target_rho", [0.08, 0.15, 0.3])
def test_recovers_closed_form_gaussian_cmi_on_the_linear_fixture(target_rho):
    """The estimator's whole purpose is to be efficient on exactly this
    kind of data -- it must track the known closed-form Gaussian CMI
    reasonably closely, not just be "positive and roughly plausible"."""
    data = sample_weak_edge_triangle(target_rho, 4000, np.random.default_rng(1))
    estimate = estimate_structured_cmi(
        data[:, 1], data[:, 2], data[:, 0], degree=2, rng=np.random.default_rng(2)
    )
    true_cmi = _closed_form_gaussian_cmi(target_rho)
    assert abs(estimate - true_cmi) < 0.015


def test_near_zero_under_the_null():
    data = sample_weak_edge_triangle(0.0, 4000, np.random.default_rng(1))
    estimate = estimate_structured_cmi(
        data[:, 1], data[:, 2], data[:, 0], degree=2, rng=np.random.default_rng(2)
    )
    assert abs(estimate) < 0.01


@pytest.mark.parametrize("curvature", [0.3, 0.6])
def test_detects_real_dependence_on_the_ushape_fixture_only_at_degree_two(curvature):
    """The diagnostic case: a `degree=1` (linear-only) basis cannot
    represent a quadratic relationship at all, so it must report
    near-zero CMI despite genuine, strong dependence -- while
    `degree=2` must clearly detect it. A structured estimator that
    reports near-zero here regardless of degree would indicate a
    bug (or a collapse to linear behavior), not a calibration issue."""
    data = sample_ushape_triangle(curvature, 4000, np.random.default_rng(1))
    degree_two = estimate_structured_cmi(
        data[:, 1], data[:, 2], data[:, 0], degree=2, rng=np.random.default_rng(2)
    )
    degree_one = estimate_structured_cmi(
        data[:, 1], data[:, 2], data[:, 0], degree=1, rng=np.random.default_rng(2)
    )
    assert degree_two > 0.05
    assert abs(degree_one) < 0.01
    assert degree_two > degree_one + 0.05


def test_ushape_fixture_curvature_zero_is_near_zero_even_at_degree_two():
    """`degree=2` has the *capacity* to fit a spurious quadratic term
    from noise alone; confirm it does not do so under the true null."""
    data = sample_ushape_triangle(0.0, 4000, np.random.default_rng(1))
    estimate = estimate_structured_cmi(
        data[:, 1], data[:, 2], data[:, 0], degree=2, rng=np.random.default_rng(2)
    )
    assert abs(estimate) < 0.01


@pytest.mark.parametrize("target_rho", [0.15, 0.3])
def test_detects_positive_dependence_on_the_monotonic_curvature_fixture(target_rho):
    """A low-degree polynomial cannot represent `tanh` exactly, so an
    exact closed-form match is not expected here (unlike the pure
    linear fixture) -- only that real, meaningfully positive dependence
    is detected, scaling with `target_rho` as the linear fixture does."""
    data = sample_monotonic_curvature_triangle(target_rho, 4000, np.random.default_rng(1))
    estimate = estimate_structured_cmi(
        data[:, 1], data[:, 2], data[:, 0], degree=2, rng=np.random.default_rng(2)
    )
    assert estimate > 0.0


def test_bivariate_case_reduces_to_marginal_mi_when_z_is_none():
    rng = np.random.default_rng(5)
    n = 4000
    x = rng.normal(size=n)
    y = 0.4 * x + np.sqrt(1 - 0.4**2) * rng.normal(size=n)
    estimate = estimate_structured_cmi(x, y, None, degree=2, rng=np.random.default_rng(6))
    true_mi = _closed_form_gaussian_cmi(0.4)
    assert abs(estimate - true_mi) < 0.01



def test_is_reproducible_given_the_same_rng_seed():
    data = sample_weak_edge_triangle(0.2, 500, np.random.default_rng(1))
    first = estimate_structured_cmi(data[:, 1], data[:, 2], data[:, 0], rng=np.random.default_rng(9))
    second = estimate_structured_cmi(data[:, 1], data[:, 2], data[:, 0], rng=np.random.default_rng(9))
    assert first == second


def test_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        estimate_structured_cmi(
            np.zeros(10), np.zeros(11), rng=np.random.default_rng(0)
        )


def test_rejects_non_positive_degree():
    with pytest.raises(ValueError, match="degree must be a positive integer"):
        estimate_structured_cmi(
            np.zeros(10), np.zeros(10), degree=0, rng=np.random.default_rng(0)
        )


def test_rejects_negative_ridge_lambda():
    with pytest.raises(ValueError, match="ridge_lambda must be"):
        estimate_structured_cmi(
            np.zeros(10), np.zeros(10), ridge_lambda=-1.0, rng=np.random.default_rng(0)
        )


@pytest.mark.parametrize("cv_folds", [1, 11])
def test_rejects_cv_folds_out_of_range(cv_folds):
    x = np.arange(10, dtype=float)
    with pytest.raises(ValueError, match="cv_folds must be"):
        estimate_structured_cmi(x, x, cv_folds=cv_folds, rng=np.random.default_rng(0))


def test_rejects_zero_variance_input():
    x = np.zeros(10)
    y = np.arange(10, dtype=float)
    with pytest.raises(ValueError, match="x must have nonzero variance"):
        estimate_structured_cmi(x, y, rng=np.random.default_rng(0))
