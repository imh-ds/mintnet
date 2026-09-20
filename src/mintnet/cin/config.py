"""Validated configuration for the forthcoming CIN estimator."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from collections import Counter
from dataclasses import dataclass, fields
from numbers import Integral, Real
from typing import Any, Literal

import numpy as np
import pandas as pd


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


def _category_key(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (bool, np.bool_)):
        return ("bool", bool(value))
    if isinstance(value, Real):
        return ("number", float(value))
    try:
        hash(value)
    except TypeError as exc:
        raise ValueError("categorical levels must be hashable") from exc
    return ("value", type(value).__module__, type(value).__qualname__, value)


def _is_missing_scalar(value: Any) -> bool:
    result = pd.isna(value)
    return isinstance(result, (bool, np.bool_)) and bool(result)


@dataclass(frozen=True)
class VariableSpec:
    name: str
    kind: Literal["continuous", "categorical"]
    levels: tuple[Any, ...] | None = None
    ordered: bool = False


def parse_schema(schema: Mapping[str, Mapping[str, Any]]) -> tuple[VariableSpec, ...]:
    """Validate a declared schema and preserve its insertion order."""

    if not isinstance(schema, Mapping):
        raise ValueError("schema must be a mapping")

    specs: list[VariableSpec] = []
    for name, raw_spec in schema.items():
        if not isinstance(name, str):
            raise ValueError("schema variable names must be strings")
        if not isinstance(raw_spec, Mapping):
            raise ValueError(f"{name}: variable specification must be a mapping")
        allowed_keys = {"kind", "levels", "ordered"}
        unknown_keys = set(raw_spec) - allowed_keys
        if unknown_keys:
            raise ValueError(f"{name}: unknown schema keys {sorted(unknown_keys)!r}")

        kind = raw_spec.get("kind")
        if kind == "continuous":
            if "levels" in raw_spec or "ordered" in raw_spec:
                raise ValueError(f"{name}: continuous variables cannot declare levels or ordered")
            specs.append(VariableSpec(name=name, kind="continuous"))
            continue
        if kind != "categorical":
            raise ValueError(f"{name}: kind must be 'continuous' or 'categorical'")
        if "levels" not in raw_spec:
            raise ValueError(f"{name}: categorical variables require levels")
        raw_levels = raw_spec["levels"]
        if not isinstance(raw_levels, (list, tuple)):
            raise ValueError(f"{name}: levels must be a list or tuple")
        levels = tuple(raw_levels)
        if not 2 <= len(levels) <= 10:
            raise ValueError(f"{name}: categorical levels must contain 2 to 10 unique values")
        keys: list[tuple[Any, ...]] = []
        for level in levels:
            if _is_missing_scalar(level):
                raise ValueError(f"{name}: categorical levels cannot contain missing values")
            key = _category_key(level)
            if key in keys:
                raise ValueError(f"{name}: categorical levels must be unique")
            keys.append(key)
        ordered = raw_spec.get("ordered", False)
        if not isinstance(ordered, bool):
            raise ValueError(f"{name}: ordered must be a boolean")
        specs.append(VariableSpec(name=name, kind="categorical", levels=levels, ordered=ordered))
    return tuple(specs)


@dataclass(frozen=True)
class DataDiagnostics:
    few_unique_continuous: tuple[str, ...]
    rare_levels: tuple[tuple[str, Any, int], ...]
    p_ge_n: bool
    extra_columns: tuple[str, ...]
    q_estimate: int
    q_limit: int


@dataclass(frozen=True)
class PreparedData:
    names: tuple[str, ...]
    specs: tuple[VariableSpec, ...]
    kinds: np.ndarray
    values: np.ndarray
    codes: np.ndarray
    index: pd.Index
    n_input: int
    n_retained: int
    n_excluded: int
    excluded_labels_digest: str | None
    excluded_labels: tuple[Any, ...] | None
    data_digest: str
    row_identity_digest: str
    diagnostics: DataDiagnostics


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"value {value!r} is not JSON serializable")


def _index_blob(labels: Any) -> str:
    return "\x1f".join(repr(label) for label in labels)


def _digest_index(labels: Any) -> str:
    return hashlib.sha256(_index_blob(labels).encode("utf-8")).hexdigest()


def _update_framed(hasher: Any, payload: bytes) -> None:
    hasher.update(len(payload).to_bytes(8, byteorder="little", signed=False))
    hasher.update(payload)


def _schema_json(specs: tuple[VariableSpec, ...]) -> bytes:
    payload = [
        {
            "kind": spec.kind,
            "levels": list(spec.levels) if spec.levels is not None else None,
            "name": spec.name,
            "ordered": spec.ordered,
        }
        for spec in specs
    ]
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")


def _data_digest(
    specs: tuple[VariableSpec, ...],
    index: pd.Index,
    values: np.ndarray,
    codes: np.ndarray,
) -> str:
    hasher = hashlib.sha256()
    _update_framed(hasher, _schema_json(specs))
    _update_framed(hasher, _index_blob(index).encode("utf-8"))
    for column, spec in enumerate(specs):
        hasher.update(b"c" if spec.kind == "continuous" else b"k")
        if spec.kind == "continuous":
            payload = np.asarray(values[:, column], dtype="<f8").tobytes(order="C")
        else:
            payload = np.asarray(codes[:, column], dtype="<i2").tobytes(order="C")
        _update_framed(hasher, payload)
    return hasher.hexdigest()


def prepare_data(
    frame: pd.DataFrame,
    schema: Mapping[str, Mapping[str, Any]],
    config: CINConfig,
) -> PreparedData:
    """Validate a frame and materialize the immutable CIN input contract."""

    if not isinstance(frame, pd.DataFrame):
        raise ValueError("frame must be a pandas DataFrame")
    if not isinstance(config, CINConfig):
        raise ValueError("config must be a CINConfig")
    if not frame.index.is_unique:
        raise ValueError("frame index must be unique")
    if not frame.columns.is_unique:
        raise ValueError("frame columns must be unique; duplicate columns are not allowed")

    specs = parse_schema(schema)
    names = tuple(spec.name for spec in specs)
    if not 2 <= len(names) <= config.max_variables:
        raise ValueError(f"schema must contain between 2 and {config.max_variables} variables")
    missing_columns = [name for name in names if name not in frame.columns]
    if missing_columns:
        raise ValueError(f"schema columns missing from frame: {missing_columns!r}")

    selected = frame.loc[:, list(names)]
    missing_counts = selected.isna().sum()
    missing_names = [name for name in names if int(missing_counts[name]) > 0]
    n_input = len(selected)
    excluded_all: tuple[Any, ...] | None = None
    if missing_names and config.missing == "error":
        details = ", ".join(
            f"{name}={int(missing_counts[name])}" for name in missing_names
        )
        offending = []
        for label, row in selected.iterrows():
            if bool(row.isna().any()):
                offending.append(repr(label))
                if len(offending) == 5:
                    break
        raise ValueError(
            f"missing values in declared columns ({details}); "
            f"first offending index labels: {offending!r}"
        )
    if missing_names:
        keep = ~selected.isna().any(axis=1)
        excluded_all = tuple(selected.index[~keep].tolist())
        retained = selected.loc[keep].copy()
    else:
        retained = selected.copy()

    n_retained = len(retained)
    n_excluded = n_input - n_retained
    if n_retained < config.min_rows:
        raise ValueError(
            f"retained rows {n_retained} are below min_rows {config.min_rows} "
            f"(input rows: {n_input})"
        )

    q_estimate = 3 * sum(spec.kind == "continuous" for spec in specs) + sum(
        len(spec.levels or ()) for spec in specs if spec.kind == "categorical"
    )
    if q_estimate > config.max_expanded_features:
        raise ValueError(
            f"expanded feature estimate {q_estimate} exceeds "
            f"max_expanded_features {config.max_expanded_features}"
        )

    kinds = np.asarray([spec.kind == "categorical" for spec in specs], dtype=bool)
    values = np.zeros((n_retained, len(specs)), dtype=np.float64, order="C")
    codes = np.full((n_retained, len(specs)), -1, dtype=np.int16, order="C")
    few_unique: list[str] = []
    rare_levels: list[tuple[str, Any, int]] = []

    for column, spec in enumerate(specs):
        series = retained[spec.name]
        raw_values = series.to_numpy(dtype=object, copy=False)
        if spec.kind == "continuous":
            if pd.api.types.is_bool_dtype(series.dtype) or all(
                isinstance(value, (bool, np.bool_)) for value in raw_values
            ):
                raise ValueError(f"{spec.name}: boolean data must be declared categorical")
            try:
                numeric = pd.to_numeric(series, errors="raise").to_numpy(dtype=np.float64)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{spec.name}: continuous data must be numeric") from exc
            for raw_value, converted_value in zip(raw_values, numeric):
                if isinstance(raw_value, Integral) and not isinstance(raw_value, bool):
                    if int(converted_value) != int(raw_value):
                        raise ValueError(
                            f"{spec.name}: continuous data cannot be converted to float64 without loss"
                        )
            if not np.isfinite(numeric).all():
                raise ValueError(f"{spec.name}: continuous data must be finite")
            if np.std(numeric, ddof=0) == 0:
                raise ValueError(f"{spec.name}: continuous variable is constant")
            values[:, column] = numeric
            if np.unique(numeric).size <= 7:
                few_unique.append(spec.name)
            continue

        assert spec.levels is not None
        level_map = {_category_key(level): code for code, level in enumerate(spec.levels)}
        mapped: list[int] = []
        unknown: list[Any] = []
        for value in raw_values:
            key = _category_key(value)
            if key not in level_map:
                unknown.append(value)
            else:
                mapped.append(level_map[key])
        if unknown:
            counts = Counter(repr(value) for value in unknown)
            raise ValueError(f"{spec.name}: unknown categorical values {dict(counts)!r}")
        categorical_codes = np.asarray(mapped, dtype=np.int16)
        if np.unique(categorical_codes).size <= 1:
            raise ValueError(f"{spec.name}: categorical variable has one observed level")
        codes[:, column] = categorical_codes
        counts = np.bincount(categorical_codes, minlength=len(spec.levels))
        rare_levels.extend(
            (spec.name, level, int(counts[level_code]))
            for level_code, level in enumerate(spec.levels)
            if counts[level_code] < 5
        )

    diagnostics = DataDiagnostics(
        few_unique_continuous=tuple(few_unique),
        rare_levels=tuple(rare_levels),
        p_ge_n=len(specs) >= n_retained,
        extra_columns=tuple(column for column in frame.columns if column not in names),
        q_estimate=q_estimate,
        q_limit=config.max_expanded_features,
    )
    retained_index = pd.Index(retained.index)
    excluded_digest = _digest_index(excluded_all) if excluded_all is not None else None
    excluded_labels = excluded_all if excluded_all is not None and len(excluded_all) <= 1000 else None
    kinds.setflags(write=False)
    values.setflags(write=False)
    codes.setflags(write=False)
    row_identity_digest = _digest_index(retained_index)
    return PreparedData(
        names=names,
        specs=specs,
        kinds=kinds,
        values=values,
        codes=codes,
        index=retained_index,
        n_input=n_input,
        n_retained=n_retained,
        n_excluded=n_excluded,
        excluded_labels_digest=excluded_digest,
        excluded_labels=excluded_labels,
        data_digest=_data_digest(specs, retained_index, values, codes),
        row_identity_digest=row_identity_digest,
        diagnostics=diagnostics,
    )


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
        if not isinstance(self.missing, str) or self.missing not in {"error", "complete_case"}:
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
