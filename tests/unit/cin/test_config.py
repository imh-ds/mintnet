from __future__ import annotations

import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from mintnet.cin import CINConfig, estimate_stability, fit_network, make_view


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
