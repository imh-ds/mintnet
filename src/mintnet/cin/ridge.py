"""Shared multiresponse ridge solves and exact omitted-block predictions.

For centered training matrices ``B`` and ``T`` with ``m`` rows, this module
solves

    min_beta ||T - B beta||_F^2 / (2m) + lam ||beta||_F^2 / 2

by forming ``A = B.T @ B + m * lam * I`` and using Cholesky triangular
solves for ``beta = A^-1 @ B.T @ T``.  When ``H = A^-1`` is needed, it is
obtained by solving against the identity, never by calling a generic inverse.

For an omitted column set ``S``, the exact restricted solution is
``beta_minus_S = beta - H[:, S] @ solve(H[S, S], beta[S, :])`` with the
omitted rows set to zero.  Predictions use the same correction on ``X @ H``.
The direct restricted solver is intentionally slow and exists only as an
independent test reference and an explicitly logged numerical fallback.
"""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Real
from typing import Any

import numpy as np
from scipy.linalg import LinAlgError, cho_factor, cho_solve

from .config import CINConfig

__all__ = [
    "OmissionWorkspace",
    "RidgeNumericalFailure",
    "RidgeSolution",
    "direct_restricted_ridge",
]


class RidgeNumericalFailure(RuntimeError):
    """Raised when numerical omission fallbacks exceed the allowed rate."""


def _matrix(values: Any, name: str) -> np.ndarray:
    try:
        result = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a numeric two-dimensional array") from exc
    if result.ndim != 2:
        raise ValueError(f"{name} must be a numeric two-dimensional array")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    result = np.ascontiguousarray(result, dtype=np.float64)
    result.setflags(write=False)
    return result


def _lambda(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("lam must be a finite positive number")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError("lam must be a finite positive number")
    return result


def _columns(values: Any, n_columns: int, name: str) -> np.ndarray:
    result = np.asarray(values)
    if result.ndim != 1 or result.dtype.kind not in "iu":
        raise ValueError(f"{name} must be a one-dimensional integer array")
    result = np.ascontiguousarray(result, dtype=np.intp)
    if np.unique(result).size != result.size:
        raise ValueError(f"{name} must not contain duplicate columns")
    if np.any(result < 0) or np.any(result >= n_columns):
        raise ValueError(f"{name} must contain columns in [0, {n_columns})")
    return result


def _complement(omit_cols: np.ndarray, n_columns: int) -> np.ndarray:
    return np.setdiff1d(np.arange(n_columns, dtype=np.intp), omit_cols, assume_unique=True)


def direct_restricted_ridge(
    B: np.ndarray,
    T: np.ndarray,
    lam: float,
    keep_cols: np.ndarray,
    m: int,
) -> np.ndarray:
    """Solve a restricted ridge system directly for test/reference use."""

    design = _matrix(B, "B")
    responses = _matrix(T, "T")
    if design.shape[0] != responses.shape[0]:
        raise ValueError("B and T must have the same number of rows")
    if not isinstance(m, (int, np.integer)) or isinstance(m, bool) or m != design.shape[0]:
        raise ValueError("m must equal the number of rows in B")
    penalty = _lambda(lam)
    keep = _columns(keep_cols, design.shape[1], "keep_cols")
    if keep.size == 0:
        return np.empty((0, responses.shape[1]), dtype=np.float64, order="C")
    restricted = design[:, keep]
    normal = restricted.T @ restricted
    normal = (normal + normal.T) / 2.0
    normal += float(m) * penalty * np.eye(keep.size, dtype=np.float64)
    result = np.linalg.solve(normal, restricted.T @ responses)
    if not np.isfinite(result).all():
        raise RidgeNumericalFailure("direct restricted ridge produced non-finite coefficients")
    return np.ascontiguousarray(result, dtype=np.float64)


class RidgeSolution:
    """One shared Cholesky-factored multiresponse ridge system."""

    def __init__(self, B: np.ndarray, T: np.ndarray, lam: float, config: CINConfig):
        if not isinstance(config, CINConfig):
            raise ValueError("config must be a CINConfig instance")
        design = _matrix(B, "B")
        responses = _matrix(T, "T")
        if design.shape[0] != responses.shape[0]:
            raise ValueError("B and T must have the same number of rows")
        if design.shape[0] < 1:
            raise ValueError("B and T must contain at least one row")

        self._B = design
        self._T = responses
        self.config = config
        self.m, self.q = design.shape
        self.t = responses.shape[1]
        self.lam = _lambda(lam)
        self._cross = np.ascontiguousarray(design.T @ responses, dtype=np.float64)
        self._cross.setflags(write=False)
        self._normal = np.ascontiguousarray(design.T @ design, dtype=np.float64)
        self._normal = (self._normal + self._normal.T) / 2.0
        if self.q:
            self._normal += float(self.m) * self.lam * np.eye(self.q, dtype=np.float64)
            self._normal = np.ascontiguousarray(self._normal, dtype=np.float64)
            self._chol = cho_factor(self._normal, lower=True, check_finite=True)
            beta = cho_solve(self._chol, self._cross, check_finite=True)
            self.beta = np.ascontiguousarray(beta, dtype=np.float64)
        else:
            self._normal = np.empty((0, 0), dtype=np.float64, order="C")
            self._chol = None
            self.beta = np.empty((0, self.t), dtype=np.float64, order="C")
        self.beta.setflags(write=False)
        self._h_cache: np.ndarray | None = None

    def H(self) -> np.ndarray:
        """Return the cached symmetrized inverse-normal solve matrix."""

        if self._h_cache is None:
            if self.q == 0:
                hessian_inverse = np.empty((0, 0), dtype=np.float64, order="C")
            else:
                identity = np.eye(self.q, dtype=np.float64)
                hessian_inverse = cho_solve(self._chol, identity, check_finite=True)
                hessian_inverse = (hessian_inverse + hessian_inverse.T) / 2.0
                hessian_inverse = np.ascontiguousarray(hessian_inverse, dtype=np.float64)
            hessian_inverse.setflags(write=False)
            self._h_cache = hessian_inverse
        return self._h_cache

    def scaled_normal_residual(self) -> float:
        """Return the scaled residual of the normal equations."""

        if self.q == 0:
            return 0.0
        residual = self._normal @ self.beta - self._cross
        denominator = max(float(np.linalg.norm(self._cross, ord="fro")), np.finfo(float).tiny)
        return float(np.linalg.norm(residual, ord="fro") / denominator)


class OmissionWorkspace:
    """Cache matrix-H products for exact fixed-penalty block omissions."""

    def __init__(self, solution: RidgeSolution, matrices: Mapping[str, np.ndarray]):
        if not isinstance(solution, RidgeSolution):
            raise ValueError("solution must be a RidgeSolution instance")
        if not isinstance(matrices, Mapping) or not matrices:
            raise ValueError("matrices must be a non-empty mapping")
        self.solution = solution
        self._matrices: dict[str, np.ndarray] = {}
        for name, matrix in matrices.items():
            if not isinstance(name, str) or not name:
                raise ValueError("matrix names must be non-empty strings")
            checked = _matrix(matrix, f"matrix {name!r}")
            if checked.shape[1] != solution.q:
                raise ValueError(f"matrix {name!r} must have {solution.q} columns")
            self._matrices[name] = checked
        self._xh_cache: dict[str, np.ndarray] | None = None
        self.fallback_count = 0
        self.requested_omissions = 0
        self.fallback_events: list[tuple[str, tuple[int, ...], tuple[int, ...]]] = []

    def _matrix_for(self, name: str) -> np.ndarray:
        try:
            return self._matrices[name]
        except KeyError as exc:
            raise KeyError(f"unknown workspace matrix {name!r}") from exc

    def _xh_for(self, name: str) -> np.ndarray:
        if self._xh_cache is None:
            hessian_inverse = self.solution.H()
            self._xh_cache = {
                matrix_name: np.ascontiguousarray(matrix @ hessian_inverse, dtype=np.float64)
                for matrix_name, matrix in self._matrices.items()
            }
        return self._xh_cache[name]

    def predict_full(self, name: str, response_cols: np.ndarray) -> np.ndarray:
        matrix = self._matrix_for(name)
        responses = _columns(response_cols, self.solution.t, "response_cols")
        prediction = matrix @ self.solution.beta[:, responses]
        return np.ascontiguousarray(prediction, dtype=np.float64)

    def _direct_fallback(
        self,
        name: str,
        omit_cols: np.ndarray,
        response_cols: np.ndarray,
        *,
        event_name: str | None = None,
    ) -> np.ndarray:
        keep_cols = _complement(omit_cols, self.solution.q)
        beta_keep = direct_restricted_ridge(
            self.solution._B,
            self.solution._T,
            self.solution.lam,
            keep_cols,
            self.solution.m,
        )
        matrix = self._matrix_for(name) if event_name is None else self.solution._B
        prediction = matrix[:, keep_cols] @ beta_keep[:, response_cols]
        if not np.isfinite(prediction).all():
            raise RidgeNumericalFailure("direct restricted ridge fallback produced non-finite predictions")
        self.fallback_count += 1
        self.fallback_events.append(
            (
                name if event_name is None else event_name,
                tuple(int(value) for value in omit_cols),
                tuple(int(value) for value in response_cols),
            )
        )
        return np.ascontiguousarray(prediction, dtype=np.float64)

    def predict_omit(
        self,
        name: str,
        omit_cols: np.ndarray,
        response_cols: np.ndarray,
    ) -> tuple[np.ndarray, str]:
        matrix = self._matrix_for(name)
        omit = _columns(omit_cols, self.solution.q, "omit_cols")
        responses = _columns(response_cols, self.solution.t, "response_cols")
        full = np.ascontiguousarray(matrix @ self.solution.beta[:, responses], dtype=np.float64)
        if omit.size == 0:
            return full, "degenerate"
        self.requested_omissions += 1
        if omit.size == self.solution.q:
            return np.zeros_like(full), "ok"

        try:
            hessian_inverse = self.solution.H()
            hss = hessian_inverse[np.ix_(omit, omit)]
            small_chol = cho_factor(hss, lower=True, check_finite=True)
            correction_weights = cho_solve(
                small_chol,
                self.solution.beta[np.ix_(omit, responses)],
                check_finite=True,
            )
            prediction = full - self._xh_for(name)[:, omit] @ correction_weights
            if not np.isfinite(prediction).all():
                raise FloatingPointError("omitted prediction is non-finite")
            return np.ascontiguousarray(prediction, dtype=np.float64), "ok"
        except (FloatingPointError, LinAlgError):
            prediction = self._direct_fallback(name, omit, responses)
            return prediction, "fallback"

    def omitted_coefficients(
        self,
        omit_cols: np.ndarray,
        response_cols: np.ndarray,
    ) -> np.ndarray:
        omit = _columns(omit_cols, self.solution.q, "omit_cols")
        responses = _columns(response_cols, self.solution.t, "response_cols")
        coefficients = np.ascontiguousarray(self.solution.beta[:, responses].copy(), dtype=np.float64)
        if omit.size == 0:
            return coefficients
        self.requested_omissions += 1
        if omit.size == self.solution.q:
            coefficients.fill(0.0)
            return coefficients

        try:
            hessian_inverse = self.solution.H()
            keep = _complement(omit, self.solution.q)
            hss = hessian_inverse[np.ix_(omit, omit)]
            small_chol = cho_factor(hss, lower=True, check_finite=True)
            correction_weights = cho_solve(
                small_chol,
                self.solution.beta[np.ix_(omit, responses)],
                check_finite=True,
            )
            coefficients[omit, :] = 0.0
            coefficients[keep, :] -= hessian_inverse[np.ix_(keep, omit)] @ correction_weights
            if not np.isfinite(coefficients).all():
                raise FloatingPointError("omitted coefficients are non-finite")
            return coefficients
        except (FloatingPointError, LinAlgError):
            keep = _complement(omit, self.solution.q)
            beta_keep = direct_restricted_ridge(
                self.solution._B,
                self.solution._T,
                self.solution.lam,
                keep,
                self.solution.m,
            )
            coefficients.fill(0.0)
            coefficients[keep, :] = beta_keep[:, responses]
            if not np.isfinite(coefficients).all():
                raise RidgeNumericalFailure("direct restricted ridge fallback produced non-finite coefficients")
            self.fallback_count += 1
            self.fallback_events.append(
                (
                    "<coefficients>",
                    tuple(int(value) for value in omit),
                    tuple(int(value) for value in responses),
                )
            )
            return coefficients

    def check_fallback_rate(self, limit: float = 0.01) -> None:
        if isinstance(limit, bool) or not isinstance(limit, Real) or not np.isfinite(float(limit)):
            raise ValueError("fallback limit must be a finite nonnegative number")
        limit_value = float(limit)
        if limit_value < 0.0:
            raise ValueError("fallback limit must be a finite nonnegative number")
        if self.requested_omissions and self.fallback_count / self.requested_omissions > limit_value:
            raise RidgeNumericalFailure(
                f"ridge omission fallback rate {self.fallback_count / self.requested_omissions:.6g} "
                f"exceeds limit {limit_value:.6g} ({self.fallback_count}/"
                f"{self.requested_omissions} fallbacks)"
            )
