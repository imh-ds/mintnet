from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from mintnet.cin.config import CINConfig, prepare_data
from mintnet.cin.features import fit_feature_space
from mintnet.cin.fit import (
    Budget,
    BudgetExceeded,
    CostCounters,
    make_splits,
    target_supported,
    tune_lambdas,
)
from mintnet.cin.result import NetworkFit, PAIR_COLUMNS


def test_network_fit_round_trips_json_safe_tables() -> None:
    fit = NetworkFit(
        pairs=pd.DataFrame(columns=PAIR_COLUMNS),
        nodes=pd.DataFrame([{"node": "a", "full_score_mean": 1.0}]),
        folds=pd.DataFrame([{"fold": 0, "train_rows": 2, "eval_rows": 1}]),
        metadata={"complete": True, "config_hash": "abc"},
    )

    restored = NetworkFit.from_dict(fit.to_dict())

    pd.testing.assert_frame_equal(restored.pairs, fit.pairs)
    pd.testing.assert_frame_equal(restored.nodes, fit.nodes)
    pd.testing.assert_frame_equal(restored.folds, fit.folds)
    assert restored.metadata == fit.metadata


def test_make_splits_is_reproducible_and_balanced() -> None:
    config = CINConfig(seed=17, outer_folds=3, inner_folds=2)

    left = make_splits(10, config)
    right = make_splits(10, config)

    assert left.seed_metadata == right.seed_metadata
    assert sorted(len(fold.eval_rows) for fold in left.outer) == [3, 3, 4]
    assert len(np.unique(np.concatenate([fold.eval_rows for fold in left.outer]))) == 10
    for left_fold, right_fold in zip(left.outer, right.outer):
        np.testing.assert_array_equal(left_fold.eval_rows, right_fold.eval_rows)
        inner_sizes = [len(fold.eval_rows) for fold in left_fold.inner]
        assert max(inner_sizes) - min(inner_sizes) <= 1
        assert len(np.unique(np.concatenate([fold.eval_rows for fold in left_fold.inner]))) == len(
            left_fold.train_rows
        )


def test_budget_raises_with_phase() -> None:
    with pytest.raises(BudgetExceeded, match="score"):
        Budget(deadline=time.monotonic() - 1.0).check("score")


def _continuous_fixture() -> tuple[pd.DataFrame, dict[str, dict[str, str]], CINConfig]:
    rows = np.arange(30, dtype=np.float64)
    frame = pd.DataFrame(
        {
            "a": np.sin(rows / 4.0) + rows / 50.0,
            "b": np.cos(rows / 5.0) - rows / 70.0,
            "c": (rows % 7.0) + rows / 80.0,
        }
    )
    schema = {
        "a": {"kind": "continuous"},
        "b": {"kind": "continuous"},
        "c": {"kind": "continuous"},
    }
    config = CINConfig(seed=4, lambda_grid=(0.1, 1.0), pair_batch_size=1)
    return frame, schema, config


def test_tune_lambdas_uses_shared_inner_splits_and_counts_factorizations() -> None:
    frame, schema, config = _continuous_fixture()
    prepared = prepare_data(frame, schema, config)
    split_plan = make_splits(prepared.n_retained, config)
    counters = CostCounters()

    result = tune_lambdas(prepared, split_plan, config, Budget(time.monotonic() + 30), counters)

    assert result.lambda_by_fold.shape == (config.outer_folds, len(schema))
    assert np.isfinite(result.lambda_by_fold).all()
    assert counters.n_large_factorizations == config.outer_folds * config.inner_folds * len(
        config.lambda_grid
    )


def test_target_supported_uses_partition_response_variation() -> None:
    frame, schema, config = _continuous_fixture()
    prepared = prepare_data(frame, schema, config)
    constant_rows = np.arange(10, dtype=np.intp)
    feature_space = fit_feature_space(prepared, constant_rows, config)

    assert target_supported(prepared, feature_space, 0, constant_rows)


def test_tune_lambdas_scores_categorical_targets() -> None:
    rows = np.arange(30, dtype=np.float64)
    frame = pd.DataFrame(
        {
            "a": np.sin(rows / 4.0),
            "b": np.asarray(rows, dtype=np.intp) % 2,
            "c": np.cos(rows / 6.0),
        }
    )
    schema = {
        "a": {"kind": "continuous"},
        "b": {"kind": "categorical", "levels": [0, 1]},
        "c": {"kind": "continuous"},
    }
    config = CINConfig(seed=9, lambda_grid=(0.1, 1.0))
    prepared = prepare_data(frame, schema, config)
    result = tune_lambdas(
        prepared,
        make_splits(prepared.n_retained, config),
        config,
        Budget(time.monotonic() + 30),
        CostCounters(),
    )

    assert np.isfinite(result.lambda_by_fold).all()
