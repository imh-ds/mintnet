from __future__ import annotations

from dataclasses import fields

import numpy as np
import pandas as pd
import pytest

from mintnet.cin import CINConfig
from mintnet.cin.config import PreparedData, prepare_data
from mintnet.cin.features import FeatureSpace, fit_feature_space


def _config(**changes: object) -> CINConfig:
    values: dict[str, object] = {
        "seed": 17,
        "max_curvature_rank": 2,
        "n_knots": 5,
        "max_variables": 100,
        "min_rows": 30,
    }
    values.update(changes)
    return CINConfig(**values)


def _schema() -> dict[str, dict[str, object]]:
    return {
        "linear": {"kind": "continuous"},
        "u_shape": {"kind": "continuous"},
        "constant_partition": {"kind": "continuous"},
        "two_value": {"kind": "continuous"},
        "ties": {"kind": "continuous"},
        "response": {"kind": "continuous"},
        "category": {"kind": "categorical", "levels": [0, 1, 2, 3, 4]},
        "single_category": {"kind": "categorical", "levels": [0, 1, 2]},
    }


def _frame() -> pd.DataFrame:
    z = np.linspace(-2.0, 2.0, 30)
    u_axis = np.r_[np.linspace(-2.0, 2.0, 20), np.linspace(-3.0, 3.0, 10)]
    return pd.DataFrame(
        {
            "linear": z,
            "u_shape": u_axis,
            "constant_partition": np.r_[np.ones(20), np.arange(10, dtype=float) + 2.0],
            "two_value": np.r_[np.tile([-1.0, 1.0], 10), np.arange(10, dtype=float)],
            "ties": np.r_[np.repeat([0.0, 1.0, 2.0], [10, 8, 2]), np.linspace(3.0, 5.0, 10)],
            "response": 1.5 * z + 0.25,
            "category": np.r_[np.tile([0, 1, 2, 3], 5), np.repeat(4, 10)],
            "single_category": np.r_[np.zeros(20, dtype=int), np.tile([1, 2], 5)],
        }
    )


def _prepared(frame: pd.DataFrame | None = None, *, schema: dict[str, dict[str, object]] | None = None) -> PreparedData:
    return prepare_data(frame if frame is not None else _frame(), schema or _schema(), _config())


def _fit(frame: pd.DataFrame | None = None, *, schema: dict[str, dict[str, object]] | None = None, **changes: object) -> FeatureSpace:
    prepared = prepare_data(frame if frame is not None else _frame(), schema or _schema(), _config(**changes))
    return fit_feature_space(prepared, np.arange(20, dtype=np.int64), _config(**changes))


def _block(space: FeatureSpace, name: str):
    return space.blocks[space.prepared.names.index(name)]


def _response_slice(space: FeatureSpace, name: str) -> slice:
    start, stop = space.R[space.prepared.names.index(name)]
    return slice(int(start), int(stop))


def _assert_fit_equal(left: FeatureSpace, right: FeatureSpace) -> None:
    assert left.q == right.q
    assert left.t == right.t
    np.testing.assert_array_equal(left.S, right.S)
    np.testing.assert_array_equal(left.R, right.R)
    np.testing.assert_array_equal(left.col_means, right.col_means)
    for left_block, right_block in zip(left.blocks, right.blocks, strict=True):
        assert type(left_block) is type(right_block)
        for field in fields(left_block):
            if field.name in {"spline_model"}:
                continue
            left_value = getattr(left_block, field.name)
            right_value = getattr(right_block, field.name)
            if isinstance(left_value, np.ndarray):
                np.testing.assert_array_equal(left_value, right_value)
            else:
                assert left_value == right_value


def test_training_only_fit_is_invariant_to_evaluation_values() -> None:
    original = _frame()
    perturbed = original.copy()
    for name in ["linear", "u_shape", "constant_partition", "two_value", "ties", "response"]:
        perturbed.loc[20:, name] = np.linspace(100.0, 200.0, 10)

    left = _fit(original)
    right = _fit(perturbed)

    _assert_fit_equal(left, right)
    np.testing.assert_array_equal(left.design(np.arange(20)), right.design(np.arange(20)))
    np.testing.assert_array_equal(left.responses(np.arange(20)), right.responses(np.arange(20)))


def test_continuous_block_algebra_and_curvature() -> None:
    space = _fit()
    block = _block(space, "u_shape")
    train = np.arange(20)
    transformed = block.transform(space.prepared.values[train, space.prepared.names.index("u_shape")])
    linear = transformed[:, 0]

    assert np.var(linear) == pytest.approx(1.0, rel=1e-10)
    assert block.rank >= 1
    assert transformed.shape[1] == block.width
    for column in transformed[:, 1:].T:
        assert abs(np.sum(column)) < 1e-10
        assert abs(np.dot(linear, column)) < 1e-10
    assert np.sum(np.var(transformed[:, 1:], axis=0)) == pytest.approx(
        1.0 / _config().curvature_multiplier,
        rel=1e-10,
    )
    assert abs(np.corrcoef(transformed[:, 1], linear**2 - 1.0)[0, 1]) > 0.5

    no_curvature = _fit(max_curvature_rank=0)
    assert _block(no_curvature, "u_shape").width == 1


def test_continuous_edge_cases_keep_actual_widths() -> None:
    space = _fit()

    constant = _block(space, "constant_partition")
    assert constant.width == 0
    assert "constant_in_partition" in constant.flags
    assert constant.transform(np.array([1.0, 2.0])).shape == (2, 0)

    two_value = _block(space, "two_value")
    assert two_value.width == 1
    assert two_value.rank == 0
    assert "few_distinct_values" in two_value.flags

    tied = _block(space, "ties")
    assert tied.width == 1 + tied.rank
    assert np.isfinite(tied.transform(space.prepared.values[:20, 4])).all()


def test_categorical_block_is_centered_and_level_stable() -> None:
    space = _fit()
    block = _block(space, "category")
    train = np.arange(20)
    transformed = block.transform(space.prepared.codes[train, 6])

    assert block.width == 5
    assert block.prevalence[-1] == 0.0
    np.testing.assert_allclose(np.mean(transformed, axis=0), 0.0, atol=1e-15)
    assert np.sum(np.var(transformed, axis=0)) == pytest.approx(1.0, rel=1e-12)
    assert _block(space, "single_category").width == 0
    assert "constant_in_partition" in _block(space, "single_category").flags

    relabeled_schema = _schema()
    relabeled_schema["category"] = {"kind": "categorical", "levels": [4, 3, 2, 1, 0]}
    relabeled = _frame()
    relabeled_space = _fit(relabeled, schema=relabeled_schema)
    np.testing.assert_allclose(
        _block(relabeled_space, "category").transform(relabeled_space.prepared.codes[train, 6]),
        transformed[:, ::-1],
        atol=1e-12,
    )


def test_responses_use_training_statistics() -> None:
    space = _fit()
    train = np.arange(20)
    continuous_response = space.responses(train)[:, _response_slice(space, "response")]
    assert np.mean(continuous_response) == pytest.approx(0.0, abs=1e-12)
    assert np.std(continuous_response, ddof=0) == pytest.approx(1.0, rel=1e-12)

    categorical_response = space.responses(train)[:, _response_slice(space, "category")]
    np.testing.assert_allclose(np.sum(categorical_response, axis=1), 0.0, atol=1e-12)
    response_spec = space.response_specs[space.prepared.names.index("category")]
    np.testing.assert_array_equal(response_spec.train_counts, np.array([5, 5, 5, 5, 0]))
    np.testing.assert_array_equal(response_spec.prevalence, np.array([0.25, 0.25, 0.25, 0.25, 0.0]))


def test_expanded_feature_cap_uses_actual_predictor_width() -> None:
    frame = pd.DataFrame({f"v{column}": np.tile(np.arange(5), 6) for column in range(100)})
    schema = {name: {"kind": "categorical", "levels": list(range(5))} for name in frame.columns}
    config = _config(max_expanded_features=1000)
    prepared = prepare_data(frame, schema, config)
    space = fit_feature_space(prepared, np.arange(20), config)
    assert space.q == 500
    assert space.t == 500

    ten_frame = pd.DataFrame({f"v{column}": np.tile(np.arange(10), 3) for column in range(100)})
    ten_schema = {name: {"kind": "categorical", "levels": list(range(10))} for name in ten_frame.columns}
    ten_prepared = prepare_data(ten_frame, ten_schema, config)
    ten_space = fit_feature_space(ten_prepared, np.arange(20), config)
    assert ten_space.q == 1000
    assert ten_space.t == 1000

    with pytest.raises(ValueError, match=r"q=500"):
        fit_feature_space(prepared, np.arange(20), _config(max_expanded_features=499))


def test_extrapolation_is_finite_and_reports_range_excursion() -> None:
    space = _fit()
    block = _block(space, "linear")
    evaluation = space.prepared.values[20:, 0]

    assert block.range_excursion(evaluation) > 0.0
    assert np.isfinite(block.transform(evaluation)).all()
