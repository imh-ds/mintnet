"""Validated configuration for the forthcoming CIN estimator."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from numbers import Integral, Real
from typing import Any


def _as_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{field_name} must be an integer")
    return int(value)


def _as_finite_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be a finite number")
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class CINConfig:
    """Initial engineering settings for the CIN estimator."""

    seed: int
    missing: str = "error"
    max_seconds: float = 300.0
    outer_folds: int = 3
    inner_folds: int = 2
    lambda_grid: tuple[float, ...] = (0.001, 0.01, 0.1, 1.0, 10.0)
    curvature_multiplier: float = 10.0
    max_curvature_rank: int = 2
    n_knots: int = 5
    spline_degree: int = 3
    probability_mixture: float = 0.01
    count_pseudocount: float = 0.5
    variance_floor: float = 0.0025
    max_expanded_features: int = 1000
    min_rows: int = 30
    max_variables: int = 100
    tie_tolerance: float = 1e-8
    fallback_stop_fraction: float = 0.01
    pair_batch_size: int = 256

    def __post_init__(self) -> None:
        int_fields = (
            "seed",
            "outer_folds",
            "inner_folds",
            "max_curvature_rank",
            "n_knots",
            "spline_degree",
            "max_expanded_features",
            "min_rows",
            "max_variables",
            "pair_batch_size",
        )
        for field_name in int_fields:
            object.__setattr__(self, field_name, _as_int(getattr(self, field_name), field_name))

        try:
            lambda_grid = tuple(_as_finite_float(value, "lambda_grid") for value in self.lambda_grid)
        except TypeError as exc:
            raise ValueError("lambda_grid must be an iterable of finite numbers") from exc
        object.__setattr__(self, "lambda_grid", lambda_grid)

        float_fields = (
            "max_seconds",
            "curvature_multiplier",
            "probability_mixture",
            "count_pseudocount",
            "variance_floor",
            "tie_tolerance",
            "fallback_stop_fraction",
        )
        for field_name in float_fields:
            object.__setattr__(self, field_name, _as_finite_float(getattr(self, field_name), field_name))

        if self.seed < 0:
            raise ValueError("seed must be >= 0")
        if self.missing not in {"error", "complete_case"}:
            raise ValueError("missing must be 'error' or 'complete_case'")
        if self.max_seconds <= 0:
            raise ValueError("max_seconds must be > 0")
        if self.outer_folds < 2:
            raise ValueError("outer_folds must be >= 2")
        if self.inner_folds < 2:
            raise ValueError("inner_folds must be >= 2")
        if not self.lambda_grid or any(value <= 0 for value in self.lambda_grid):
            raise ValueError("lambda_grid must contain positive values")
        if any(left >= right for left, right in zip(self.lambda_grid, self.lambda_grid[1:])):
            raise ValueError("lambda_grid must be strictly increasing")
        if self.curvature_multiplier <= 0:
            raise ValueError("curvature_multiplier must be > 0")
        if not 0 <= self.max_curvature_rank <= 2:
            raise ValueError("max_curvature_rank must be between 0 and 2")
        if self.n_knots < 3:
            raise ValueError("n_knots must be >= 3")
        if self.spline_degree < 1:
            raise ValueError("spline_degree must be >= 1")
        if not 0 < self.probability_mixture < 1:
            raise ValueError("probability_mixture must be in (0, 1)")
        if self.count_pseudocount <= 0:
            raise ValueError("count_pseudocount must be > 0")
        if self.variance_floor <= 0:
            raise ValueError("variance_floor must be > 0")
        if self.max_expanded_features < 1:
            raise ValueError("max_expanded_features must be >= 1")
        if self.min_rows < 2 * self.outer_folds * self.inner_folds:
            raise ValueError("min_rows must be at least 2 * outer_folds * inner_folds")
        if self.max_variables < 2:
            raise ValueError("max_variables must be >= 2")
        if self.tie_tolerance < 0:
            raise ValueError("tie_tolerance must be >= 0")
        if not 0 <= self.fallback_stop_fraction <= 1:
            raise ValueError("fallback_stop_fraction must be in [0, 1]")
        if self.pair_batch_size < 1:
            raise ValueError("pair_batch_size must be >= 1")

        outer_train = math.ceil(30 * (self.outer_folds - 1) / self.outer_folds)
        largest_inner_validation = math.ceil(outer_train / self.inner_folds)
        inner_train = outer_train - largest_inner_validation
        if inner_train < 2:
            raise ValueError("the configured folds leave fewer than 2 inner-training rows")

    def config_hash(self) -> str:
        """Return the stable hash of fields that define the statistical procedure."""

        excluded = {"pair_batch_size", "max_seconds"}
        payload = {
            field.name: _json_value(getattr(self, field.name))
            for field in fields(self)
            if field.name not in excluded
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
