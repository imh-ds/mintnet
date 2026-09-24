from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from mintnet.cin.scores import (
    categorical_logscore,
    choose_lambda,
    gaussian_logscore,
    intercept_scores,
)


def _gaussian_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    y_std = np.array([-0.75, 0.25, 1.5, -1.25], dtype=np.float64)
    pred = np.array([-0.5, 0.1, 1.1, -0.8], dtype=np.float64)
    r_train = np.array([0.5, -0.25, 0.75, -1.0, 0.25], dtype=np.float64)
    return y_std, pred, r_train, 2.5


def _categorical_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    codes = np.array([0, 1, 2, 1, 0], dtype=np.intp)
    ridge_out = np.array(
        [
            [0.5, -0.5, 0.0],
            [-0.25, 0.25, 0.0],
            [-1.0, -1.0, -1.0],
            [0.0, 0.0, 0.0],
            [0.1, -0.1, 0.0],
        ],
        dtype=np.float64,
    )
    prevalence = np.array([0.4, 0.4, 0.2], dtype=np.float64)
    train_counts = np.array([2, 2, 1], dtype=np.int64)
    return codes, ridge_out, prevalence, train_counts, 5


def test_gaussian_closed_form_in_original_response_units() -> None:
    y_std, pred, r_train, sd_y = _gaussian_inputs()

    logq, info = gaussian_logscore(y_std, pred, r_train, sd_y, 0.0025)

    variance = float(np.mean(r_train**2))
    expected = stats.norm.logpdf(
        y_std * sd_y,
        loc=pred * sd_y,
        scale=np.sqrt(variance) * sd_y,
    )
    np.testing.assert_allclose(logq, expected, rtol=1e-12, atol=1e-12)
    assert logq.flags.c_contiguous
    assert logq.dtype == np.float64
    assert info["variance"] == pytest.approx(variance)
    assert info["variance_floor_hit"] is False
    assert info["training_mse"] == pytest.approx(variance)
    assert info["evaluation_mse"] == pytest.approx(np.mean((y_std - pred) ** 2))


def test_gaussian_partial_correlation_analytic_oracle() -> None:
    rho = 0.6
    residual_variance = 1.0 - rho**2
    nodes, weights = np.polynomial.hermite.hermgauss(40)
    standard = np.sqrt(2.0) * nodes
    probabilities = weights / np.sqrt(np.pi)
    x, z = np.meshgrid(standard, standard, indexing="ij")
    joint_weights = probabilities[:, None] * probabilities[None, :]
    y = rho * x + np.sqrt(residual_variance) * z
    full_pred = rho * x
    full_train_residuals = np.array(
        [-np.sqrt(residual_variance), np.sqrt(residual_variance)],
        dtype=np.float64,
    )
    reduced_train_residuals = np.array([-1.0, 1.0], dtype=np.float64)

    full, _ = gaussian_logscore(
        y.ravel(), full_pred.ravel(), full_train_residuals, 1.0, 0.0025
    )
    reduced, _ = gaussian_logscore(
        y.ravel(), np.zeros(y.size), reduced_train_residuals, 1.0, 0.0025
    )
    expected = -0.5 * np.log(1.0 - rho**2)
    observed = float(np.sum(joint_weights.ravel() * (full - reduced)))

    assert observed == pytest.approx(expected, abs=2e-4)


def test_gaussian_floor_and_training_variance_rule() -> None:
    y_std = np.array([-1.0, 0.0, 1.0], dtype=np.float64)
    pred = np.zeros(3, dtype=np.float64)

    logq, info = gaussian_logscore(
        y_std, pred, np.zeros(4, dtype=np.float64), 3.0, 0.0025
    )

    assert np.isfinite(logq).all()
    assert info["variance"] == pytest.approx(0.0025)
    assert info["variance_floor_hit"] is True


def test_scores_use_training_statistics_only() -> None:
    y_std, pred, r_train, sd_y = _gaussian_inputs()
    changed_y = np.array([100.0, -100.0, 50.0, -50.0], dtype=np.float64)
    changed_pred = np.array([-20.0, 20.0, -10.0, 10.0], dtype=np.float64)

    _, original_info = gaussian_logscore(y_std, pred, r_train, sd_y, 0.0025)
    _, changed_info = gaussian_logscore(
        changed_y, changed_pred, r_train, sd_y, 0.0025
    )

    assert changed_info["variance"] == original_info["variance"]
    assert changed_info["training_mse"] == original_info["training_mse"]
    assert changed_info["evaluation_mse"] != original_info["evaluation_mse"]

    codes, ridge_out, prevalence, train_counts, m = _categorical_inputs()
    changed_codes = np.array([2, 2, 1, 0, 2], dtype=np.intp)
    changed_ridge = ridge_out[::-1].copy()
    _, original_cat_info = categorical_logscore(
        codes, ridge_out, prevalence, train_counts, m, 0.01, 0.5
    )
    _, changed_cat_info = categorical_logscore(
        changed_codes, changed_ridge, prevalence, train_counts, m, 0.01, 0.5
    )
    np.testing.assert_array_equal(
        changed_cat_info["prior"], original_cat_info["prior"]
    )


def test_categorical_normalization_and_diagnostics() -> None:
    codes, ridge_out, prevalence, train_counts, m = _categorical_inputs()

    logq, info = categorical_logscore(
        codes, ridge_out, prevalence, train_counts, m, 0.01, 0.5
    )

    pi = (train_counts.astype(np.float64) + 0.5) / (m + 0.5 * 3)
    raw = prevalence[None, :] + ridge_out
    clipped = np.maximum(raw, 0.0)
    row_sums = clipped.sum(axis=1)
    normalized = np.where(
        row_sums[:, None] > 0.0,
        clipped / np.where(row_sums[:, None] > 0.0, row_sums[:, None], 1.0),
        pi[None, :],
    )
    expected_q = 0.99 * normalized + 0.01 * pi[None, :]

    assert np.isfinite(logq).all()
    np.testing.assert_allclose(logq, np.log(expected_q[np.arange(codes.size), codes]))
    np.testing.assert_allclose(expected_q.sum(axis=1), 1.0, atol=1e-12)
    np.testing.assert_allclose(info["prior"], pi)
    assert info["zero_sum_count"] == 1
    assert info["clipped_fraction"] > 0.0
    assert info["min_probability"] == pytest.approx(np.min(expected_q))
    assert info["absent_training_levels"] == 0
    assert info["rare_training_levels"] == 3


def test_categorical_relabeling_equivariance() -> None:
    codes, ridge_out, prevalence, train_counts, m = _categorical_inputs()
    permutation = np.array([2, 0, 1], dtype=np.intp)
    inverse = np.empty_like(permutation)
    inverse[permutation] = np.arange(permutation.size)

    original, _ = categorical_logscore(
        codes, ridge_out, prevalence, train_counts, m, 0.01, 0.5
    )
    relabeled, _ = categorical_logscore(
        inverse[codes],
        ridge_out[:, permutation],
        prevalence[permutation],
        train_counts[permutation],
        m,
        0.01,
        0.5,
    )

    np.testing.assert_allclose(relabeled, original, rtol=1e-12, atol=1e-12)


def test_categorical_binary_oracle_with_mixture() -> None:
    codes = np.array([0, 0, 0, 0, 1, 0, 1, 1, 1, 1], dtype=np.intp)
    conditional = np.array(
        [[0.8, 0.2]] * 5 + [[0.2, 0.8]] * 5,
        dtype=np.float64,
    )
    prevalence = np.array([0.5, 0.5], dtype=np.float64)
    train_counts = np.array([5, 5], dtype=np.int64)
    ridge_out = conditional - prevalence[None, :]

    full, _ = categorical_logscore(
        codes, ridge_out, prevalence, train_counts, 10, 0.01, 0.5
    )
    reduced, _ = categorical_logscore(
        codes, np.zeros_like(ridge_out), prevalence, train_counts, 10, 0.01, 0.5
    )

    mixture_expected = 0.8 * np.log((0.99 * 0.8 + 0.01 * 0.5) / 0.5)
    mixture_expected += 0.2 * np.log((0.99 * 0.2 + 0.01 * 0.5) / 0.5)
    observed = float(np.mean(full - reduced))
    analytic_cmi = 0.8 * np.log(1.6) + 0.2 * np.log(0.4)

    assert observed == pytest.approx(mixture_expected, abs=1e-12)
    assert abs(observed - analytic_cmi) < 0.01


def test_intercept_baselines_reuse_score_adapters() -> None:
    y_std, _, r_train, sd_y = _gaussian_inputs()
    actual_continuous, actual_continuous_info = intercept_scores(
        "continuous", y_std, sd_y=sd_y, variance_floor=0.0025
    )
    expected_continuous, expected_continuous_info = gaussian_logscore(
        y_std, np.zeros_like(y_std), np.ones(1), sd_y, 0.0025
    )
    np.testing.assert_allclose(actual_continuous, expected_continuous)
    assert actual_continuous_info == expected_continuous_info
    assert not np.array_equal(r_train, np.ones(1))

    codes, _, prevalence, train_counts, m = _categorical_inputs()
    zero_ridge = np.zeros((codes.size, prevalence.size), dtype=np.float64)
    actual_categorical, actual_categorical_info = intercept_scores(
        "categorical",
        codes,
        prevalence=prevalence,
        train_counts=train_counts,
        m=m,
        mixture=0.01,
        pseudocount=0.5,
    )
    expected_categorical, expected_categorical_info = categorical_logscore(
        codes, zero_ridge, prevalence, train_counts, m, 0.01, 0.5
    )
    np.testing.assert_allclose(actual_categorical, expected_categorical)
    assert actual_categorical_info.keys() == expected_categorical_info.keys()
    np.testing.assert_array_equal(
        actual_categorical_info["prior"], expected_categorical_info["prior"]
    )


def test_choose_lambda_maximizes_sum_and_breaks_ties_by_largest_lambda() -> None:
    scores = np.array([10.0, 10.0 - 5e-9, 9.0], dtype=np.float64)

    selected, index = choose_lambda(scores, 30, (0.001, 0.01, 0.1), 1e-8)

    assert (selected, index) == (0.01, 1)
    selected_worse, index_worse = choose_lambda(
        np.array([10.0, 9.0, 9.0], dtype=np.float64),
        30,
        (0.001, 0.01, 0.1),
        1e-8,
    )
    assert (selected_worse, index_worse) == (0.001, 0)


def test_choose_lambda_uses_only_supplied_inner_scores() -> None:
    scores = np.array([1.0, 2.0, 1.5], dtype=np.float64)
    grid = (0.001, 0.01, 0.1)

    first = choose_lambda(scores, 19, grid, 1e-8)
    second = choose_lambda(scores.copy(), 101, grid, 1e-8)

    assert first == second == (0.01, 1)


def test_choose_lambda_rejects_nonfinite_or_empty_scores() -> None:
    with pytest.raises(ValueError):
        choose_lambda(np.array([], dtype=np.float64), 1, (), 1e-8)
    with pytest.raises(ValueError):
        choose_lambda(np.array([np.nan], dtype=np.float64), 1, (0.1,), 1e-8)
    with pytest.raises(ValueError):
        choose_lambda(np.array([1.0], dtype=np.float64), 0, (0.1,), 1e-8)
    with pytest.raises(ValueError):
        choose_lambda(np.array([1.0, 2.0], dtype=np.float64), 1, (0.1,), 1e-8)


def test_score_validation_rejects_invalid_inputs() -> None:
    y_std, pred, r_train, sd_y = _gaussian_inputs()
    with pytest.raises(ValueError):
        gaussian_logscore(y_std[:-1], pred, r_train, sd_y, 0.0025)
    with pytest.raises(ValueError):
        gaussian_logscore(y_std, pred, np.array([], dtype=np.float64), sd_y, 0.0025)
    with pytest.raises(ValueError):
        gaussian_logscore(y_std, pred, r_train, 0.0, 0.0025)
    with pytest.raises(ValueError):
        gaussian_logscore(y_std, pred, r_train, sd_y, 0.0)

    codes, ridge_out, prevalence, train_counts, m = _categorical_inputs()
    with pytest.raises(ValueError):
        categorical_logscore(codes, ridge_out[:, :-1], prevalence, train_counts, m, 0.01, 0.5)
    with pytest.raises(ValueError):
        categorical_logscore(np.array([3, 0, 1, 2, 1]), ridge_out, prevalence, train_counts, m, 0.01, 0.5)
    with pytest.raises(ValueError):
        categorical_logscore(codes, ridge_out, prevalence, np.array([2, 2, 2]), m, 0.01, 0.5)
    with pytest.raises(ValueError):
        categorical_logscore(codes, ridge_out, prevalence, train_counts, m, 0.0, 0.5)
    with pytest.raises(ValueError):
        categorical_logscore(codes, ridge_out, prevalence, train_counts, m, 0.01, 0.0)


def test_categorical_extreme_finite_scores() -> None:
    codes = np.array([0, 1, 2], dtype=np.intp)
    ridge_out = np.array(
        [
            [np.finfo(np.float64).max / 4.0, 0.0, 0.0],
            [0.0, np.finfo(np.float64).max / 4.0, 0.0],
            [0.0, 0.0, np.finfo(np.float64).max / 4.0],
        ],
        dtype=np.float64,
    )
    prevalence = np.full(3, 1.0 / 3.0, dtype=np.float64)
    train_counts = np.array([1, 1, 1], dtype=np.int64)

    logq, info = categorical_logscore(
        codes, ridge_out, prevalence, train_counts, 3, 0.01, 0.5
    )

    assert np.isfinite(logq).all()
    assert info["min_probability"] > 0.0
