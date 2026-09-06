"""Structured conditional-density plug-in estimator for MI/CMI -- an
alternative to CMIknn's fully nonparametric, density-free kNN
estimation. See docs/stage7d_charter.md.

Rather than estimating `p(x,y,z)` from local neighbor geometry alone
(CMIknn), this estimator fits an explicit, deliberately *constrained*
conditional-density model -- a low-degree polynomial basis with a
homoscedastic Gaussian residual, ridge-regularized -- and computes
MI/CMI as a difference of fitted log predictive densities:

    I(X;Y)   = E[ log p(Y|X)   - log p(Y)   ]
    I(X;Y|Z) = E[ log p(Y|X,Z) - log p(Y|Z) ]

Both expectations are estimated **out-of-sample via K-fold
cross-fitting**, not on the same data the models were trained on --
evaluating a model's own fit on its own training data would
systematically overstate dependence (the model can always "explain"
noise it has already seen), especially at the small `N` this
estimator's whole motivation is to help with. `M0` (`p(Y|Z)`, or
`p(Y)` in the bivariate case) and `M1` (`p(Y|X,Z)`, or `p(Y|X)`) are
evaluated on **identical fold splits**, so the difference is a paired
comparison, not two independently noisy quantities.

**The reported quantity is always MI/CMI in nats** -- never a
regression coefficient, a polynomial-term significance, or a model
`R^2` -- matching this project's own standing distinction between the
network edge quantity (MI) and any incidental byproduct of how it was
estimated.

**Basis complexity (`degree`) is a parameter to be calibrated by a
future charter's own evidence, not a hand-picked default here** --
matching the treatment `k_CMI` received in Stage 7c. This module only
implements the estimator itself; Stage 7d's own calibration sweep and
head-to-head comparison against CMIknn is separate, later work.

**Known asymmetry, disclosed rather than hidden**: population MI/CMI
is symmetric in `X` and `Y`, but this plug-in construction is not,
in general, symmetric at any finite `N` -- swapping which variable
plays "the modeled outcome" (`Y`) versus "the added predictor" (`X`)
can change the finite-sample estimate. This mirrors the asymmetry
already present in the proposal this charter is testing; a future
wrapper may choose to symmetrize (e.g. averaging both orderings, in
the spirit of the Generalized Covariance Measure test) but that is a
decision for the significance-test/evidence-runner layer, not this
module, which implements the formula exactly as specified.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.preprocessing import PolynomialFeatures

from mintnet.mi.local_permutation import restricted_permutation, z_neighbors

ArrayLike = Sequence[float] | np.ndarray

_RESIDUAL_VARIANCE_FLOOR = 1e-8


def _as_finite_vector(values: ArrayLike, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _as_conditioning_matrix(z: ArrayLike | None, n: int) -> np.ndarray:
    if z is None:
        return np.empty((n, 0))
    array = np.asarray(z, dtype=float)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2 or array.shape[0] != n:
        raise ValueError("z must be a 1D or 2D array with n rows, or None")
    if not np.isfinite(array).all():
        raise ValueError("z must contain only finite values")
    return array


def _standardize_columns(array: np.ndarray) -> np.ndarray:
    if array.shape[1] == 0:
        return array
    std = array.std(axis=0, ddof=1)
    if np.any(std == 0.0):
        raise ValueError("a conditioning column has zero variance; standardization is undefined")
    return (array - array.mean(axis=0)) / std


def _design_matrix(columns: np.ndarray, degree: int) -> np.ndarray:
    """Low-degree polynomial basis (with interactions, no intercept
    column -- the fitted `Ridge` model supplies its own intercept) over
    already-standardized `columns`. Zero input columns (the
    intercept-only case, e.g. `M0` in the bivariate/`z=None` case)
    yields a zero-column design, handled by `_cross_fitted_log_density`
    as a plain intercept-only Gaussian fit."""
    if columns.shape[1] == 0:
        return columns
    basis = PolynomialFeatures(degree=degree, include_bias=False)
    return basis.fit_transform(columns)


def _cross_fitted_log_density(
    design: np.ndarray, y: np.ndarray, folds: list[tuple[np.ndarray, np.ndarray]], ridge_lambda: float
) -> np.ndarray:
    """Fit a ridge-regularized (or, with a zero-column design,
    intercept-only) homoscedastic Gaussian conditional-density model on
    each fold's training split, and return the out-of-sample log
    density of every point under its own held-out fold's fit. Every
    point is scored exactly once, by a model that never saw it."""
    n = y.shape[0]
    log_density = np.empty(n)
    for train_idx, test_idx in folds:
        if design.shape[1] == 0:
            mean = y[train_idx].mean()
            residual_train = y[train_idx] - mean
            predicted_test = np.full(test_idx.shape[0], mean)
        else:
            model = Ridge(alpha=ridge_lambda, fit_intercept=True)
            model.fit(design[train_idx], y[train_idx])
            residual_train = y[train_idx] - model.predict(design[train_idx])
            predicted_test = model.predict(design[test_idx])
        variance = max(float(residual_train.var(ddof=1)), _RESIDUAL_VARIANCE_FLOOR)
        residual_test = y[test_idx] - predicted_test
        log_density[test_idx] = -0.5 * np.log(2.0 * np.pi * variance) - residual_test**2 / (2.0 * variance)
    return log_density


def estimate_structured_cmi(
    x: ArrayLike,
    y: ArrayLike,
    z: ArrayLike | None = None,
    *,
    degree: int = 2,
    ridge_lambda: float = 1.0,
    cv_folds: int = 5,
    rng: np.random.Generator,
) -> float:
    """Estimate `I(X;Y|Z)` in nats (or `I(X;Y)` when `z=None`) via
    cross-fitted structured conditional-density plug-in estimation --
    see this module's own docstring for the full construction.

    `x`, `y`, and any columns of `z` are standardized before fitting
    (matching `mintnet.mi.cmiknn.estimate_cmiknn`'s own convention);
    this is exact and lossless for the reported MI/CMI, since
    standardization is an invertible affine transform applied
    identically to `M0` and `M1`'s own evaluation of `y` -- the
    resulting constant log-Jacobian term cancels exactly in the
    `log p(y|x,z) - log p(y|z)` difference.
    """
    x_array = _as_finite_vector(x, "x")
    y_array = _as_finite_vector(y, "y")
    if x_array.size != y_array.size:
        raise ValueError("x and y must have the same length")
    n = x_array.size

    if not isinstance(degree, int) or degree < 1:
        raise ValueError("degree must be a positive integer")
    if not np.isfinite(ridge_lambda) or ridge_lambda < 0.0:
        raise ValueError("ridge_lambda must be a non-negative, finite number")
    if not isinstance(cv_folds, int) or not 2 <= cv_folds <= n:
        raise ValueError("cv_folds must be an integer satisfying 2 <= cv_folds <= n")
    if np.std(x_array, ddof=1) == 0.0:
        raise ValueError("x must have nonzero variance")
    if np.std(y_array, ddof=1) == 0.0:
        raise ValueError("y must have nonzero variance")

    z_array = _as_conditioning_matrix(z, n)

    x_s = ((x_array - x_array.mean()) / x_array.std(ddof=1))[:, None]
    y_s = (y_array - y_array.mean()) / y_array.std(ddof=1)
    z_s = _standardize_columns(z_array)

    design_m0 = _design_matrix(z_s, degree)
    design_m1 = _design_matrix(np.column_stack([x_s, z_s]), degree)

    fold_seed = int(rng.integers(0, 2**31 - 1))
    folds = list(KFold(n_splits=cv_folds, shuffle=True, random_state=fold_seed).split(np.arange(n)))

    log_density_m0 = _cross_fitted_log_density(design_m0, y_s, folds, ridge_lambda)
    log_density_m1 = _cross_fitted_log_density(design_m1, y_s, folds, ridge_lambda)
    return float(np.mean(log_density_m1 - log_density_m0))


@dataclass(frozen=True)
class StructuredLocalPermutationResult:
    statistic: float
    p_value: float
    null_distribution: tuple[float, ...]


def _fold_seed(rng: np.random.Generator) -> int:
    return int(rng.integers(0, 2**31 - 1))


def local_permutation_test(
    x: ArrayLike,
    y: ArrayLike,
    z: ArrayLike | None = None,
    *,
    degree: int = 2,
    ridge_lambda: float = 1.0,
    cv_folds: int = 5,
    k_perm: int = 3,
    permutations: int = 199,
    symmetrize: bool = True,
    rng: np.random.Generator,
) -> StructuredLocalPermutationResult:
    """Test X independent-of Y given Z via `estimate_structured_cmi` and
    the same local-permutation null (`mintnet.mi.local_permutation`)
    already validated for CMIknn -- reusing, not re-deriving, the null
    construction isolates a head-to-head comparison against CMIknn to
    the estimator itself. `z=None`: ordinary (global) permutation,
    valid for the unconditional case, matching
    `mintnet.mi.cmiknn.local_permutation_test`'s own convention.

    **Symmetrization** (`symmetrize=True`, the default): population
    MI/CMI is symmetric in X and Y, but `estimate_structured_cmi`'s own
    plug-in construction is not, in general, symmetric at any finite
    `N` (see that function's own docstring) -- fitting Y as the
    modeled outcome and X as the added predictor is not guaranteed to
    give the same finite-sample estimate as the reverse. Rather than
    make an arbitrary, undisclosed choice of which variable plays which
    role, the reported statistic here is the average of both
    orderings' own CMI estimates, in the spirit of the Generalized
    Covariance Measure test's own symmetric construction. This is still
    a valid permutation-test statistic (validity requires only that the
    same statistic function is applied consistently to the observed and
    every permuted dataset, not that the statistic itself be symmetric)
    -- it costs roughly double the model fits per replicate, disclosed
    here since it directly affects a future evidence runner's own
    compute-cost measurement. Pass `symmetrize=False` for the cheaper,
    single-orientation statistic if a future charter's own timing
    measurement makes that tradeoff necessary.

    **Fixed cross-fitting folds across the whole test**: the K-fold
    split for each orientation is derived once, from `rng`, before the
    observed statistic or any permutation replicate is computed, and
    reused identically (via a freshly re-seeded `np.random.Generator`
    per call) for the observed statistic and every null replicate. This
    isolates the null distribution's own variability to the actual
    Y-permutation, rather than mixing in fold-assignment randomness as
    a second, uncontrolled noise source.
    """
    x_array = _as_finite_vector(x, "x")
    y_array = _as_finite_vector(y, "y")
    if x_array.size != y_array.size:
        raise ValueError("x and y must have the same length")
    n = y_array.size

    forward_seed = _fold_seed(rng)
    backward_seed = _fold_seed(rng) if symmetrize else None

    def statistic(y_values: np.ndarray) -> float:
        forward = estimate_structured_cmi(
            x_array, y_values, z, degree=degree, ridge_lambda=ridge_lambda, cv_folds=cv_folds,
            rng=np.random.default_rng(forward_seed),
        )
        if not symmetrize:
            return forward
        backward = estimate_structured_cmi(
            y_values, x_array, z, degree=degree, ridge_lambda=ridge_lambda, cv_folds=cv_folds,
            rng=np.random.default_rng(backward_seed),
        )
        return 0.5 * (forward + backward)

    observed = statistic(y_array)
    null = np.empty(permutations)

    if z is None:
        for b in range(permutations):
            null[b] = statistic(rng.permutation(y_array))
    else:
        z_array = _as_conditioning_matrix(z, n)
        z_s = _standardize_columns(z_array)
        neighbors = z_neighbors(z_s, k_perm)
        for b in range(permutations):
            perm = restricted_permutation(neighbors, rng)
            null[b] = statistic(y_array[perm])

    p_value = (float(np.sum(null >= observed)) + 1.0) / (permutations + 1.0)
    return StructuredLocalPermutationResult(statistic=observed, p_value=p_value, null_distribution=tuple(null.tolist()))
