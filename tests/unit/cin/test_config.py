from __future__ import annotations

import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mintnet.cin import CINConfig, estimate_stability, fit_network, make_view
from mintnet.cin.config import parse_schema, prepare_data


def valid_schema() -> dict[str, dict[str, object]]:
    return {
        "stress": {"kind": "continuous"},
        "sleep_item": {"kind": "categorical", "levels": [1, 2, 3], "ordered": True},
    }


def valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ignored": range(30),
            "sleep_item": [1, 2, 3] * 10,
            "stress": [float(index % 7) + index / 100.0 for index in range(30)],
        },
        index=pd.RangeIndex(30),
    )


def test_config_defaults_are_stable() -> None:
    config = CINConfig(seed=1)

    assert config.seed == 1
    assert config.missing == "error"
    assert config.max_seconds == 300.0
    assert config.outer_folds == 3
    assert config.inner_folds == 2
    assert config.lambda_grid == (0.001, 0.01, 0.1, 1.0, 10.0)
    assert config.curvature_multiplier == 10.0
    assert config.max_curvature_rank == 2
    assert config.n_knots == 5
    assert config.spline_degree == 3
    assert config.probability_mixture == 0.01
    assert config.count_pseudocount == 0.5
    assert config.variance_floor == 0.0025
    assert config.max_expanded_features == 1000
    assert config.min_rows == 30
    assert config.max_variables == 100
    assert config.tie_tolerance == 1e-8
    assert config.fallback_stop_fraction == 0.01
    assert config.pair_batch_size == 256


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": -1},
        {"seed": True},
        {"missing": "drop"},
        {"missing": []},
        {"max_seconds": 0.0},
        {"max_seconds": math.inf},
        {"outer_folds": 1},
        {"inner_folds": 1},
        {"lambda_grid": ()},
        {"lambda_grid": (0.1, 0.01)},
        {"lambda_grid": (0.0, 0.1)},
        {"curvature_multiplier": 0.0},
        {"max_curvature_rank": 3},
        {"n_knots": 2},
        {"spline_degree": 0},
        {"probability_mixture": 0.0},
        {"probability_mixture": 1.0},
        {"count_pseudocount": 0.0},
        {"variance_floor": 0.0},
        {"max_expanded_features": 0},
        {"min_rows": 7},
        {"max_variables": 1},
        {"tie_tolerance": -1.0},
        {"fallback_stop_fraction": -0.1},
        {"fallback_stop_fraction": 1.1},
        {"pair_batch_size": 0},
    ],
)
def test_config_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    kwargs = dict(kwargs)
    seed = kwargs.pop("seed", 1)
    with pytest.raises(ValueError):
        CINConfig(seed=seed, **kwargs)


def test_config_hash_ignores_only_batch_and_timing() -> None:
    config = CINConfig(seed=1)
    assert config.config_hash() == replace(config, pair_batch_size=1).config_hash()
    assert config.config_hash() == replace(config, max_seconds=301.0).config_hash()

    changed = {
        "seed": 2,
        "missing": "complete_case",
        "outer_folds": 4,
        "inner_folds": 3,
        "lambda_grid": (0.001, 0.01, 0.1, 1.0, 20.0),
        "curvature_multiplier": 11.0,
        "max_curvature_rank": 1,
        "n_knots": 6,
        "spline_degree": 2,
        "probability_mixture": 0.02,
        "count_pseudocount": 0.6,
        "variance_floor": 0.003,
        "max_expanded_features": 999,
        "min_rows": 32,
        "max_variables": 99,
        "tie_tolerance": 2e-8,
        "fallback_stop_fraction": 0.02,
    }
    for field, value in changed.items():
        assert replace(config, **{field: value}).config_hash() != config.config_hash(), field


def test_public_import_is_lightweight() -> None:
    source_path = Path(__file__).resolve().parents[3] / "src"
    code = (
        f"import sys; sys.path.insert(0, {str(source_path)!r}); import mintnet.cin; "
        "assert 'sklearn' not in sys.modules; "
        "assert 'matplotlib' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)

    for function in (fit_network, estimate_stability, make_view):
        with pytest.raises(NotImplementedError):
            function(None)


def test_parse_schema_preserves_insertion_order() -> None:
    parsed = parse_schema(valid_schema())

    assert tuple(spec.name for spec in parsed) == ("stress", "sleep_item")
    assert parsed[0].kind == "continuous"
    assert parsed[0].levels is None
    assert parsed[0].ordered is False
    assert parsed[1].levels == (1, 2, 3)
    assert parsed[1].ordered is True


@pytest.mark.parametrize(
    "schema",
    [
        {"x": {"kind": "continuous", "levels": [1, 2]}},
        {"x": {"kind": "continuous", "ordered": True}},
        {"x": {"kind": "categorical"}},
        {"x": {"kind": "categorical", "levels": [1, 2], "typo": True}},
        {"x": {"kind": "other"}},
    ],
)
def test_schema_rejects_unknown_or_missing_keys(schema: dict[object, object]) -> None:
    with pytest.raises(ValueError, match="x"):
        parse_schema(schema)


@pytest.mark.parametrize(
    "levels",
    [
        [1],
        list(range(11)),
        [1, 1.0],
    ],
)
def test_schema_rejects_invalid_levels(levels: list[object]) -> None:
    with pytest.raises(ValueError, match="x"):
        parse_schema({"x": {"kind": "categorical", "levels": levels}})


def test_schema_rejects_non_string_names() -> None:
    with pytest.raises(ValueError):
        parse_schema({1: {"kind": "continuous"}})


def test_prepare_data_enforces_variable_bounds() -> None:
    frame = valid_frame()
    with pytest.raises(ValueError, match="between 2"):
        prepare_data(frame, {"stress": {"kind": "continuous"}}, CINConfig(seed=1))

    wide_schema = {f"x{index}": {"kind": "continuous"} for index in range(101)}
    wide_frame = pd.DataFrame({name: range(30) for name in wide_schema})
    with pytest.raises(ValueError, match="100"):
        prepare_data(wide_frame, wide_schema, CINConfig(seed=1))


def test_prepare_data_rejects_duplicate_frame_columns() -> None:
    frame = valid_frame()
    frame.columns = ["sleep_item", "sleep_item", "stress"]

    with pytest.raises(ValueError, match="duplicate"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_missing_error_reports_counts_and_labels() -> None:
    frame = valid_frame()
    frame.loc[3, "stress"] = np.nan

    with pytest.raises(ValueError, match="stress=1.*3"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_complete_case_drops_declared_columns_once() -> None:
    frame = valid_frame()
    frame.loc[3, "sleep_item"] = pd.NA
    frame.loc[4, "ignored"] = pd.NA

    prepared = prepare_data(
        frame,
        valid_schema(),
        CINConfig(seed=1, missing="complete_case", outer_folds=2, inner_folds=2, min_rows=8),
    )

    assert prepared.n_input == 30
    assert prepared.n_retained == 29
    assert prepared.n_excluded == 1
    assert prepared.excluded_labels == (3,)
    assert prepared.excluded_labels_digest is not None
    assert 3 not in prepared.index
    assert prepared.diagnostics.extra_columns == ("ignored",)


def test_extra_column_missingness_is_ignored() -> None:
    frame = valid_frame()
    frame.loc[4, "ignored"] = pd.NA

    prepared = prepare_data(
        frame,
        valid_schema(),
        CINConfig(seed=1, missing="complete_case"),
    )

    assert prepared.n_retained == 30
    assert prepared.n_excluded == 0
    assert prepared.excluded_labels is None
    assert prepared.excluded_labels_digest is None


def test_retained_rows_guard() -> None:
    frame = valid_frame()
    frame.loc[0, "stress"] = np.nan

    with pytest.raises(ValueError, match="retained rows 29.*min_rows 30"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1, missing="complete_case"))


def test_continuous_rejects_boolean_data() -> None:
    frame = valid_frame()
    frame["stress"] = [index % 2 == 0 for index in range(30)]

    with pytest.raises(ValueError, match="stress.*boolean"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_continuous_rejects_infinite_values() -> None:
    frame = valid_frame()
    frame.loc[0, "stress"] = np.inf

    with pytest.raises(ValueError, match="stress.*finite"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_continuous_rejects_nonnumeric_values() -> None:
    frame = valid_frame()
    frame["stress"] = frame["stress"].astype(object)
    frame.loc[0, "stress"] = "not-numeric"

    with pytest.raises(ValueError, match="stress.*numeric"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_continuous_rejects_lossy_integer_conversion() -> None:
    frame = valid_frame()
    frame["stress"] = [2**53 + (index % 2) for index in range(30)]

    with pytest.raises(ValueError, match="stress.*loss"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_categorical_codes_are_explicit() -> None:
    prepared = prepare_data(valid_frame(), valid_schema(), CINConfig(seed=1))

    assert prepared.kinds.tolist() == [False, True]
    assert prepared.values.dtype == np.float64
    assert prepared.codes.dtype == np.int16
    assert np.all(prepared.codes[:, 0] == -1)
    assert np.all(prepared.values[:, 1] == 0.0)
    assert prepared.codes[:3, 1].tolist() == [0, 1, 2]


def test_numeric_category_equivalence_preserves_boolean_distinction() -> None:
    frame = pd.DataFrame(
        {
            "stress": np.arange(30, dtype=float),
            "item": ([1.0, True, 2] * 10),
        }
    )
    schema = {
        "stress": {"kind": "continuous"},
        "item": {"kind": "categorical", "levels": [1, True, 2]},
    }

    prepared = prepare_data(frame, schema, CINConfig(seed=1))

    assert prepared.codes[:3, 1].tolist() == [0, 1, 2]


def test_unknown_categorical_values_are_rejected() -> None:
    frame = valid_frame()
    frame.loc[0, "sleep_item"] = 9

    with pytest.raises(ValueError, match="sleep_item.*9"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_constant_continuous_variable_is_rejected() -> None:
    frame = valid_frame()
    frame["stress"] = 1.0

    with pytest.raises(ValueError, match="stress.*constant"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_constant_categorical_variable_is_rejected() -> None:
    frame = valid_frame()
    frame["sleep_item"] = 1

    with pytest.raises(ValueError, match="sleep_item.*one observed"):
        prepare_data(frame, valid_schema(), CINConfig(seed=1))


def test_diagnostics_are_recorded_without_type_changes() -> None:
    frame = valid_frame()
    frame["stress"] = [float(index % 7) for index in range(30)]
    frame["sleep_item"] = [1] * 14 + [2] * 16

    prepared = prepare_data(frame, valid_schema(), CINConfig(seed=1))

    assert prepared.diagnostics.few_unique_continuous == ("stress",)
    assert prepared.diagnostics.rare_levels == (("sleep_item", 3, 0),)
    assert prepared.diagnostics.p_ge_n is False
    assert prepared.diagnostics.extra_columns == ("ignored",)
    assert prepared.diagnostics.q_estimate == 6
    assert prepared.specs[0].kind == "continuous"
    assert prepared.specs[1].kind == "categorical"


def test_q_estimate_limit_is_enforced() -> None:
    with pytest.raises(ValueError, match="estimate 6.*5"):
        prepare_data(valid_frame(), valid_schema(), CINConfig(seed=1, max_expanded_features=5))


def test_p_ge_n_diagnostic_is_recorded() -> None:
    schema = {f"x{index}": {"kind": "continuous"} for index in range(8)}
    frame = pd.DataFrame({name: np.arange(8, dtype=float) + index for index, name in enumerate(schema)})
    config = CINConfig(seed=1, outer_folds=2, inner_folds=2, min_rows=8, max_variables=8)

    prepared = prepare_data(frame, schema, config)

    assert prepared.n_retained == 8
    assert prepared.diagnostics.p_ge_n is True


def test_digest_ignores_frame_column_order() -> None:
    frame = valid_frame()
    reordered = frame[["stress", "ignored", "sleep_item"]]

    original = prepare_data(frame, valid_schema(), CINConfig(seed=1))
    changed_order = prepare_data(reordered, valid_schema(), CINConfig(seed=1))

    assert changed_order.data_digest == original.data_digest
    assert changed_order.row_identity_digest == original.row_identity_digest


def test_digest_changes_when_cell_changes() -> None:
    frame = valid_frame()
    changed = frame.copy()
    changed.loc[0, "stress"] += 1.0

    original = prepare_data(frame, valid_schema(), CINConfig(seed=1))
    changed_data = prepare_data(changed, valid_schema(), CINConfig(seed=1))

    assert changed_data.data_digest != original.data_digest


def test_row_identity_digest_changes_when_index_changes() -> None:
    frame = valid_frame()
    changed_index = frame.copy()
    changed_index.index = pd.RangeIndex(start=100, stop=130)

    original = prepare_data(frame, valid_schema(), CINConfig(seed=1))
    changed = prepare_data(changed_index, valid_schema(), CINConfig(seed=1))

    assert changed.row_identity_digest != original.row_identity_digest


def test_prepared_arrays_are_read_only() -> None:
    prepared = prepare_data(valid_frame(), valid_schema(), CINConfig(seed=1))

    with pytest.raises(ValueError):
        prepared.values[0, 0] = 100.0
    with pytest.raises(ValueError):
        prepared.codes[0, 0] = 1
    with pytest.raises(ValueError):
        prepared.kinds[0] = True
