"""Training-only CIN feature blocks and response assembly."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Any

import numpy as np
from sklearn.preprocessing import SplineTransformer

from .config import CINConfig, PreparedData

__all__ = [
    "CategoricalBlock",
    "ContinuousBlock",
    "FeatureSpace",
    "ResponseSpec",
    "fit_feature_space",
]


def _readonly_array(values: Any, *, dtype: Any = np.float64) -> np.ndarray:
    result = np.ascontiguousarray(values, dtype=dtype)
    result.setflags(write=False)
    return result


def _empty_float(rows: int, columns: int = 0) -> np.ndarray:
    return np.empty((rows, columns), dtype=np.float64, order="C")


def _validate_rows(rows: Any, n_rows: int, *, unique: bool = False) -> np.ndarray:
    result = np.asarray(rows)
    if result.ndim != 1:
        raise ValueError("rows must be a one-dimensional integer array")
    if result.dtype.kind not in "iu" or result.dtype.kind == "b":
        raise ValueError("rows must be a one-dimensional integer array")
    result = np.ascontiguousarray(result, dtype=np.intp)
    if np.any(result < 0) or np.any(result >= n_rows):
        raise ValueError(f"rows must be in [0, {n_rows})")
    if unique and np.unique(result).size != result.size:
        raise ValueError("train_rows must contain unique row positions")
    return result


def _validate_finite_vector(values: Any, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional vector")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return np.ascontiguousarray(result, dtype=np.float64)


def _validate_codes(codes: Any) -> np.ndarray:
    result = np.asarray(codes)
    if result.ndim != 1 or result.dtype.kind not in "iu":
        raise ValueError("categorical codes must be a one-dimensional integer array")
    return np.ascontiguousarray(result, dtype=np.int64)


def _indicator_matrix(codes: np.ndarray, n_levels: int) -> np.ndarray:
    result = np.zeros((codes.size, n_levels), dtype=np.float64, order="C")
    valid = (codes >= 0) & (codes < n_levels)
    valid_rows = np.flatnonzero(valid)
    if valid_rows.size:
        result[valid_rows, codes[valid_rows]] = 1.0
    return result


@dataclass(frozen=True)
class ContinuousBlock:
    """A fitted linear-plus-curvature block for one continuous variable."""

    mean: float
    sd: float
    knots: np.ndarray
    spline_coef: np.ndarray
    directions: np.ndarray
    curv_mean: np.ndarray
    curv_scale: np.ndarray
    width: int
    rank: int
    flags: tuple[str, ...]
    spline_model: SplineTransformer | None
    train_min: float
    train_max: float

    def transform(self, x: np.ndarray) -> np.ndarray:
        values = _validate_finite_vector(x, "x")
        if self.width == 0:
            return _empty_float(values.size)
        linear = (values - self.mean) / self.sd
        if self.rank == 0 or self.spline_model is None:
            return np.ascontiguousarray(linear[:, None], dtype=np.float64)

        phi = np.asarray(self.spline_model.transform(linear[:, None]), dtype=np.float64)
        gram = np.column_stack((np.ones(values.size, dtype=np.float64), linear))
        residual = phi - gram @ self.spline_coef
        projected = residual @ self.directions
        curvature = (projected - self.curv_mean) / self.curv_scale
        result = np.column_stack((linear, curvature))
        if not np.isfinite(result).all():
            raise ValueError("continuous block transformation produced non-finite values")
        return np.ascontiguousarray(result, dtype=np.float64)

    def range_excursion(self, x: np.ndarray) -> float:
        values = _validate_finite_vector(x, "x")
        if values.size == 0 or self.width == 0:
            return 0.0
        outside = (values < self.train_min) | (values > self.train_max)
        return float(np.mean(outside))


def _fit_continuous_block(
    x: np.ndarray,
    train_rows: np.ndarray,
    config: CINConfig,
) -> ContinuousBlock:
    values = _validate_finite_vector(x, "x")
    rows = _validate_rows(train_rows, values.size, unique=True)
    train = values[rows]
    mean = float(np.mean(train))
    sd = float(np.std(train, ddof=0))
    train_min = float(np.min(train))
    train_max = float(np.max(train))
    empty_coef = _readonly_array(np.empty((2, 0), dtype=np.float64))
    empty_directions = _readonly_array(np.empty((0, 0), dtype=np.float64))
    empty_vector = _readonly_array(np.empty(0, dtype=np.float64))

    if sd == 0.0:
        return ContinuousBlock(
            mean=mean,
            sd=sd,
            knots=empty_vector,
            spline_coef=empty_coef,
            directions=empty_directions,
            curv_mean=empty_vector,
            curv_scale=empty_vector,
            width=0,
            rank=0,
            flags=("constant_in_partition",),
            spline_model=None,
            train_min=train_min,
            train_max=train_max,
        )

    linear = (values - mean) / sd
    train_linear = linear[rows]
    knots = np.unique(np.quantile(train_linear, np.linspace(0.0, 1.0, config.n_knots)))
    flags: list[str] = []
    if np.unique(train_linear).size <= 2:
        flags.append("few_distinct_values")
    if knots.size < 2:
        return ContinuousBlock(
            mean=mean,
            sd=sd,
            knots=_readonly_array(knots),
            spline_coef=empty_coef,
            directions=empty_directions,
            curv_mean=empty_vector,
            curv_scale=empty_vector,
            width=1,
            rank=0,
            flags=tuple(flags),
            spline_model=None,
            train_min=train_min,
            train_max=train_max,
        )

    model = SplineTransformer(
        degree=config.spline_degree,
        knots=knots[:, None],
        include_bias=False,
        extrapolation="constant",
    )
    model.fit(train_linear[:, None])
    phi_train = np.asarray(model.transform(train_linear[:, None]), dtype=np.float64)
    if phi_train.ndim != 2 or not np.isfinite(phi_train).all():
        raise ValueError("spline transformation produced invalid values")

    gram = np.column_stack((np.ones(rows.size, dtype=np.float64), train_linear))
    spline_coef, _, _, _ = np.linalg.lstsq(gram, phi_train, rcond=None)
    residual = phi_train - gram @ spline_coef
    directions = np.empty((phi_train.shape[1], 0), dtype=np.float64)
    if config.max_curvature_rank > 0 and residual.size:
        _, singular_values, right_vectors = np.linalg.svd(residual, full_matrices=False)
        sigma_max = float(singular_values[0]) if singular_values.size else 0.0
        if sigma_max > 0.0:
            keep = singular_values > 1e-8 * sigma_max
            keep_count = min(config.max_curvature_rank, int(np.count_nonzero(keep)))
            if keep_count:
                directions = right_vectors[:keep_count].T.copy()
                for column in range(directions.shape[1]):
                    pivot = int(np.argmax(np.abs(directions[:, column])))
                    if directions[pivot, column] < 0.0:
                        directions[:, column] *= -1.0

    projected = residual @ directions
    if projected.shape[1]:
        curv_mean = np.mean(projected, axis=0)
        centered = projected - curv_mean
        raw_sd = np.std(centered, axis=0, ddof=0)
        keep_columns = raw_sd >= 1e-12
        directions = directions[:, keep_columns]
        curv_mean = curv_mean[keep_columns]
        raw_sd = raw_sd[keep_columns]
    else:
        curv_mean = np.empty(0, dtype=np.float64)
        raw_sd = np.empty(0, dtype=np.float64)

    rank = int(directions.shape[1])
    if rank:
        curv_scale = raw_sd * np.sqrt(config.curvature_multiplier * rank)
    else:
        curv_scale = np.empty(0, dtype=np.float64)
    return ContinuousBlock(
        mean=mean,
        sd=sd,
        knots=_readonly_array(knots),
        spline_coef=_readonly_array(spline_coef),
        directions=_readonly_array(directions),
        curv_mean=_readonly_array(curv_mean),
        curv_scale=_readonly_array(curv_scale),
        width=1 + rank,
        rank=rank,
        flags=tuple(flags),
        spline_model=model,
        train_min=train_min,
        train_max=train_max,
    )


@dataclass(frozen=True)
class CategoricalBlock:
    """A fitted centered indicator block for one categorical variable."""

    prevalence: np.ndarray
    scale: float
    width: int
    flags: tuple[str, ...]

    def transform(self, codes: np.ndarray) -> np.ndarray:
        values = _validate_codes(codes)
        if self.width == 0:
            return _empty_float(values.size)
        indicators = _indicator_matrix(values, self.prevalence.size)
        result = (indicators - self.prevalence) / self.scale
        return np.ascontiguousarray(result, dtype=np.float64)


def _fit_categorical_block(
    codes: np.ndarray,
    n_levels: int,
    train_rows: np.ndarray,
) -> CategoricalBlock:
    values = _validate_codes(codes)
    if not isinstance(n_levels, Integral) or isinstance(n_levels, bool) or n_levels < 1:
        raise ValueError("n_levels must be a positive integer")
    rows = _validate_rows(train_rows, values.size, unique=True)
    training_indicators = _indicator_matrix(values[rows], int(n_levels))
    prevalence = np.mean(training_indicators, axis=0)
    scale = float(np.sqrt(np.sum(prevalence * (1.0 - prevalence))))
    if scale < 1e-12:
        width = 0
        flags = ("constant_in_partition",)
    else:
        width = int(n_levels)
        flags = ()
    return CategoricalBlock(
        prevalence=_readonly_array(prevalence),
        scale=scale,
        width=width,
        flags=flags,
    )


@dataclass(frozen=True)
class ResponseSpec:
    kind: str
    columns: int
    y_mean: float | None = None
    y_sd: float | None = None
    prevalence: np.ndarray | None = None
    train_counts: np.ndarray | None = None
    flags: tuple[str, ...] = ()


def _fit_response_spec(
    prepared: PreparedData,
    column: int,
    train_rows: np.ndarray,
) -> ResponseSpec:
    spec = prepared.specs[column]
    if spec.kind == "continuous":
        values = _validate_finite_vector(prepared.values[:, column], spec.name)
        train = values[train_rows]
        mean = float(np.mean(train))
        sd = float(np.std(train, ddof=0))
        if sd == 0.0:
            return ResponseSpec(
                kind="continuous",
                columns=0,
                y_mean=mean,
                y_sd=sd,
                flags=("constant_response",),
            )
        return ResponseSpec(kind="continuous", columns=1, y_mean=mean, y_sd=sd)

    assert spec.levels is not None
    codes = _validate_codes(prepared.codes[:, column])
    indicators = _indicator_matrix(codes[train_rows], len(spec.levels))
    counts = np.sum(indicators, axis=0, dtype=np.int64)
    prevalence = np.mean(indicators, axis=0)
    return ResponseSpec(
        kind="categorical",
        columns=len(spec.levels),
        prevalence=_readonly_array(prevalence),
        train_counts=_readonly_array(counts, dtype=np.int64),
    )


def _transform_response(
    prepared: PreparedData,
    column: int,
    response: ResponseSpec,
    rows: np.ndarray,
) -> np.ndarray:
    if response.kind == "continuous":
        if response.columns == 0:
            return _empty_float(rows.size)
        values = np.asarray(prepared.values[rows, column], dtype=np.float64)
        assert response.y_mean is not None and response.y_sd is not None
        result = (values - response.y_mean) / response.y_sd
        return np.ascontiguousarray(result[:, None], dtype=np.float64)

    assert response.prevalence is not None
    values = _validate_codes(prepared.codes[rows, column])
    indicators = _indicator_matrix(values, response.columns)
    result = indicators - response.prevalence
    return np.ascontiguousarray(result, dtype=np.float64)


def _transform_block(
    prepared: PreparedData,
    column: int,
    block: ContinuousBlock | CategoricalBlock,
    rows: np.ndarray,
) -> np.ndarray:
    if isinstance(block, ContinuousBlock):
        return block.transform(prepared.values[rows, column])
    return block.transform(prepared.codes[rows, column])


def _ranges(widths: list[int]) -> np.ndarray:
    result = np.empty((len(widths), 2), dtype=np.intp, order="C")
    start = 0
    for index, width in enumerate(widths):
        result[index] = (start, start + width)
        start += width
    return result


@dataclass(frozen=True)
class FeatureSpace:
    """Fitted predictor and response blocks for one prepared data set."""

    blocks: tuple[ContinuousBlock | CategoricalBlock, ...]
    S: np.ndarray
    R: np.ndarray
    q: int
    t: int
    col_means: np.ndarray
    response_specs: tuple[ResponseSpec, ...]
    prepared: PreparedData

    def design(self, rows: np.ndarray) -> np.ndarray:
        selected = _validate_rows(rows, self.prepared.n_retained)
        parts = [
            _transform_block(self.prepared, column, block, selected)
            for column, block in enumerate(self.blocks)
        ]
        if not parts:
            result = _empty_float(selected.size)
        elif self.q == 0:
            result = _empty_float(selected.size)
        else:
            result = np.concatenate(parts, axis=1)
            result = result - self.col_means
        return np.ascontiguousarray(result, dtype=np.float64)

    def responses(self, rows: np.ndarray) -> np.ndarray:
        selected = _validate_rows(rows, self.prepared.n_retained)
        parts = [
            _transform_response(self.prepared, column, response, selected)
            for column, response in enumerate(self.response_specs)
        ]
        if not parts or self.t == 0:
            return _empty_float(selected.size)
        return np.ascontiguousarray(np.concatenate(parts, axis=1), dtype=np.float64)


def fit_feature_space(
    prepared: PreparedData,
    train_rows: np.ndarray,
    config: CINConfig,
) -> FeatureSpace:
    """Fit every feature and response statistic from the selected rows only."""

    if not isinstance(prepared, PreparedData):
        raise ValueError("prepared must be a PreparedData instance")
    if not isinstance(config, CINConfig):
        raise ValueError("config must be a CINConfig instance")
    selected = _validate_rows(train_rows, prepared.n_retained, unique=True)
    if selected.size == 0:
        raise ValueError("train_rows must not be empty")

    blocks: list[ContinuousBlock | CategoricalBlock] = []
    response_specs: list[ResponseSpec] = []
    for column, spec in enumerate(prepared.specs):
        if spec.kind == "continuous":
            blocks.append(_fit_continuous_block(prepared.values[:, column], selected, config))
        else:
            assert spec.levels is not None
            blocks.append(
                _fit_categorical_block(
                    prepared.codes[:, column],
                    len(spec.levels),
                    selected,
                )
            )
        response_specs.append(_fit_response_spec(prepared, column, selected))

    predictor_parts = [
        _transform_block(prepared, column, block, selected)
        for column, block in enumerate(blocks)
    ]
    q = int(sum(part.shape[1] for part in predictor_parts))
    t = int(sum(response.columns for response in response_specs))
    if q > config.max_expanded_features:
        categorical_response_width = sum(
            response.columns
            for response in response_specs
            if response.kind == "categorical"
        )
        raise ValueError(
            f"q={q} exceeds max_expanded_features={config.max_expanded_features}; "
            f"response_width={t}, categorical_response_width={categorical_response_width}"
        )

    if q:
        assembled = np.concatenate(predictor_parts, axis=1)
        col_means = _readonly_array(np.mean(assembled, axis=0))
    else:
        col_means = _readonly_array(np.empty(0, dtype=np.float64))
    widths = [part.shape[1] for part in predictor_parts]
    S = _readonly_array(_ranges(widths), dtype=np.intp)
    R = _readonly_array(_ranges([response.columns for response in response_specs]), dtype=np.intp)
    return FeatureSpace(
        blocks=tuple(blocks),
        S=S,
        R=R,
        q=q,
        t=t,
        col_means=col_means,
        response_specs=tuple(response_specs),
        prepared=prepared,
    )
