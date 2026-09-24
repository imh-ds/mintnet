"""Pure CIN log-score adapters and inner-fold penalty selection.

Continuous scores are Gaussian log densities in nats per observation. Their
variance is the model's own training residual RSS divided by the number of
training rows, floored at the configured value; evaluation rows never update
that variance. Categorical scores use clipped additive class scores and a
smoothed empirical prior, with the observed level receiving the log score.

These scores are model-based predictive quantities. In a correctly specified
population, the expected full-minus-reduced score has the decomposition
``CMI - E KL_full + E KL_reduced``; finite-sample scores are not asserted to
equal true CMI. The module deliberately has no fitting, randomness, or ridge
dependency so full, reduced, and intercept-only callers share one adapter.
"""

from __future__ import annotations

from numbers import Integral, Real
from typing import Any, Literal

import numpy as np

__all__ = [
    "categorical_logscore",
    "choose_lambda",
    "gaussian_logscore",
    "intercept_scores",
]


def _vector(values: Any, name: str) -> np.ndarray:
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite one-dimensional vector") from exc
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{name} must be a finite one-dimensional vector")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return np.ascontiguousarray(result, dtype=np.float64)


def _matrix(values: Any, name: str) -> np.ndarray:
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite two-dimensional array") from exc
    if result.ndim != 2 or result.shape[0] == 0 or result.shape[1] == 0:
        raise ValueError(f"{name} must be a finite two-dimensional array")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return np.ascontiguousarray(result, dtype=np.float64)


def _positive_scalar(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite positive number")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a finite positive number")
    return result


def _unit_interval_scalar(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be finite and in (0, 1)")
    result = float(value)
    if not np.isfinite(result) or not 0.0 < result < 1.0:
        raise ValueError(f"{name} must be finite and in (0, 1)")
    return result


def _integer_scalar(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be a positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _integer_vector(values: Any, name: str) -> np.ndarray:
    result = np.asarray(values)
    if result.ndim != 1 or result.size == 0 or result.dtype.kind not in "iu":
        raise ValueError(f"{name} must be a non-empty one-dimensional integer array")
    return np.ascontiguousarray(result, dtype=np.intp)


def gaussian_logscore(
    y_std: np.ndarray,
    pred: np.ndarray,
    r_train: np.ndarray,
    sd_y: float,
    variance_floor: float,
) -> tuple[np.ndarray, dict[str, float | bool]]:
    """Return per-row Gaussian log scores and training/evaluation diagnostics."""

    observed = _vector(y_std, "y_std")
    prediction = _vector(pred, "pred")
    training_residual = _vector(r_train, "r_train")
    if observed.size != prediction.size:
        raise ValueError("y_std and pred must have the same number of rows")
    response_sd = _positive_scalar(sd_y, "sd_y")
    floor = _positive_scalar(variance_floor, "variance_floor")

    training_mse = float(np.mean(training_residual * training_residual))
    variance_floor_hit = training_mse < floor
    variance = max(training_mse, floor)
    residual = observed - prediction
    logq = -0.5 * (
        np.log(2.0 * np.pi * variance) + (residual * residual) / variance
    ) - np.log(response_sd)
    logq = np.ascontiguousarray(logq, dtype=np.float64)
    if not np.isfinite(logq).all():
        raise ValueError("Gaussian score produced non-finite values")
    info: dict[str, float | bool] = {
        "variance": float(variance),
        "variance_floor_hit": bool(variance_floor_hit),
        "training_mse": training_mse,
        "evaluation_mse": float(np.mean(residual * residual)),
    }
    return logq, info


def _categorical_inputs(
    codes: Any,
    ridge_out: Any,
    prevalence: Any,
    train_counts: Any,
    m: Any,
    mixture: Any,
    pseudocount: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, float, float]:
    observed = _integer_vector(codes, "codes")
    raw_scores = _matrix(ridge_out, "ridge_out")
    if raw_scores.shape[0] != observed.size:
        raise ValueError("codes and ridge_out must have the same number of rows")
    n_levels = raw_scores.shape[1]

    prior_prevalence = _vector(prevalence, "prevalence")
    if prior_prevalence.size != n_levels:
        raise ValueError("prevalence must have one entry per ridge-output column")
    if np.any(prior_prevalence < 0.0) or not np.isclose(
        np.sum(prior_prevalence), 1.0, rtol=0.0, atol=1e-12
    ):
        raise ValueError("prevalence must be nonnegative and sum to one")
    if np.any(observed < 0) or np.any(observed >= n_levels):
        raise ValueError("codes must identify declared categorical levels")

    counts = _integer_vector(train_counts, "train_counts")
    if counts.size != n_levels or np.any(counts < 0):
        raise ValueError("train_counts must be nonnegative with one entry per level")
    n_train = _integer_scalar(m, "m")
    if int(np.sum(counts, dtype=np.int64)) != n_train:
        raise ValueError("train_counts must sum to m")
    prior_mixture = _unit_interval_scalar(mixture, "mixture")
    prior_pseudocount = _positive_scalar(pseudocount, "pseudocount")
    return (
        observed,
        raw_scores,
        prior_prevalence,
        counts,
        n_train,
        prior_mixture,
        prior_pseudocount,
    )


def categorical_logscore(
    codes: np.ndarray,
    ridge_out: np.ndarray,
    prevalence: np.ndarray,
    train_counts: np.ndarray,
    m: int,
    mixture: float,
    pseudocount: float,
) -> tuple[np.ndarray, dict[str, object]]:
    """Return observed-level categorical log scores and diagnostics."""

    (
        observed,
        raw_ridge,
        empirical_prevalence,
        counts,
        n_train,
        prior_mixture,
        prior_pseudocount,
    ) = _categorical_inputs(
        codes,
        ridge_out,
        prevalence,
        train_counts,
        m,
        mixture,
        pseudocount,
    )
    n_levels = raw_ridge.shape[1]
    prior = (counts.astype(np.float64) + prior_pseudocount) / (
        float(n_train) + prior_pseudocount * n_levels
    )
    raw = empirical_prevalence[None, :] + raw_ridge
    clipped = np.maximum(raw, 0.0)
    row_max = np.max(clipped, axis=1)
    nonzero = row_max > 0.0
    normalized = np.empty_like(clipped)
    normalized[~nonzero] = prior
    if np.any(nonzero):
        scaled = clipped[nonzero] / row_max[nonzero, None]
        scaled_sum = np.sum(scaled, axis=1, keepdims=True)
        normalized[nonzero] = scaled / scaled_sum
    probabilities = (1.0 - prior_mixture) * normalized + prior_mixture * prior[None, :]
    row_sums = np.sum(probabilities, axis=1)
    if (
        not np.isfinite(probabilities).all()
        or np.any(probabilities <= 0.0)
        or np.any(np.abs(row_sums - 1.0) > 1e-12)
    ):
        raise ValueError("categorical score produced invalid probabilities")
    logq = np.ascontiguousarray(
        np.log(probabilities[np.arange(observed.size), observed]),
        dtype=np.float64,
    )
    if not np.isfinite(logq).all():
        raise ValueError("categorical score produced non-finite log scores")
    readonly_prior = np.ascontiguousarray(prior, dtype=np.float64)
    readonly_prior.setflags(write=False)
    info: dict[str, object] = {
        "prior": readonly_prior,
        "clipped_fraction": float(np.mean(raw < 0.0)),
        "zero_sum_count": int(np.count_nonzero(~nonzero)),
        "min_probability": float(np.min(probabilities)),
        "absent_training_levels": int(np.count_nonzero(counts == 0)),
        "rare_training_levels": int(np.count_nonzero(counts < 5)),
    }
    return logq, info


def intercept_scores(
    kind: Literal["continuous", "categorical"],
    observed: np.ndarray,
    *,
    sd_y: float | None = None,
    prevalence: np.ndarray | None = None,
    train_counts: np.ndarray | None = None,
    m: int | None = None,
    variance_floor: float = 0.0025,
    mixture: float = 0.01,
    pseudocount: float = 0.5,
) -> tuple[np.ndarray, dict[str, object]]:
    """Score an intercept-only model through the ordinary score adapters."""

    if kind == "continuous":
        if sd_y is None:
            raise ValueError("sd_y is required for continuous intercept scores")
        prediction = np.zeros_like(_vector(observed, "observed"))
        logq, info = gaussian_logscore(
            observed,
            prediction,
            np.ones(1, dtype=np.float64),
            sd_y,
            variance_floor,
        )
        return logq, info
    if kind == "categorical":
        if prevalence is None or train_counts is None or m is None:
            raise ValueError(
                "prevalence, train_counts, and m are required for categorical intercept scores"
            )
        observed_codes = _integer_vector(observed, "observed")
        prevalence_array = _vector(prevalence, "prevalence")
        zero_ridge = np.zeros((observed_codes.size, prevalence_array.size), dtype=np.float64)
        return categorical_logscore(
            observed_codes,
            zero_ridge,
            prevalence_array,
            train_counts,
            m,
            mixture,
            pseudocount,
        )
    raise ValueError("kind must be 'continuous' or 'categorical'")


def choose_lambda(
    scores_by_lambda: np.ndarray,
    n_rows: int,
    grid: tuple[float, ...],
    tie_tolerance: float,
) -> tuple[float, int]:
    """Choose the largest lambda within tolerance of the best summed score."""

    scores = _vector(scores_by_lambda, "scores_by_lambda")
    n_contributing_rows = _integer_scalar(n_rows, "n_rows")
    del n_contributing_rows
    try:
        candidate_grid = tuple(grid)
    except TypeError as exc:
        raise ValueError("grid must be a non-empty tuple of positive numbers") from exc
    if not candidate_grid or len(candidate_grid) != scores.size:
        raise ValueError("grid and scores_by_lambda must have the same nonzero length")
    grid_values = np.asarray(candidate_grid, dtype=np.float64)
    if (
        not np.isfinite(grid_values).all()
        or np.any(grid_values <= 0.0)
        or np.any(grid_values[1:] <= grid_values[:-1])
    ):
        raise ValueError("grid must be strictly increasing positive finite values")
    if isinstance(tie_tolerance, bool) or not isinstance(tie_tolerance, Real):
        raise ValueError("tie_tolerance must be a finite nonnegative number")
    tolerance = float(tie_tolerance)
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tie_tolerance must be a finite nonnegative number")

    best_score = float(np.max(scores))
    tied = np.flatnonzero(scores >= best_score - tolerance)
    selected_index = int(tied[-1])
    return float(grid_values[selected_index]), selected_index
