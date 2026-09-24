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
    aggregate,
    make_splits,
    score_partition,
    target_supported,
    tune_lambdas,
)
from mintnet.cin import fit_network
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


def test_score_partition_omits_diagonal_and_scores_each_direction_once() -> None:
    frame, schema, config = _continuous_fixture()
    prepared = prepare_data(frame, schema, config)
    outer = make_splits(prepared.n_retained, config).outer[0]
    feature_space = fit_feature_space(prepared, outer.train_rows, config)

    result = score_partition(
        prepared,
        feature_space,
        outer.train_rows,
        outer.eval_rows,
        np.full(len(schema), 0.1),
        config,
        Budget(time.monotonic() + 30),
        CostCounters(),
        0,
    )

    assert np.all(result.directional_sum.diagonal() == 0.0)
    assert not np.any(np.diag(result.directional_started))
    for source in range(len(schema)):
        for target in range(len(schema)):
            if source != target:
                assert result.directional_rows[source, target] == len(outer.eval_rows)
                assert result.directional_started[source, target]


def test_score_partition_matches_direct_restricted_ridge_reference() -> None:
    from mintnet.cin.ridge import direct_restricted_ridge
    from mintnet.cin.scores import gaussian_logscore

    frame, schema, config = _continuous_fixture()
    prepared = prepare_data(frame, schema, config)
    outer = make_splits(prepared.n_retained, config).outer[0]
    feature_space = fit_feature_space(prepared, outer.train_rows, config)
    result = score_partition(
        prepared,
        feature_space,
        outer.train_rows,
        outer.eval_rows,
        np.full(len(schema), 0.1),
        config,
        Budget(time.monotonic() + 30),
        CostCounters(),
        0,
    )

    design_train = feature_space.design(outer.train_rows)
    design_eval = feature_space.design(outer.eval_rows)
    responses_train = feature_space.responses(outer.train_rows)
    responses_eval = feature_space.responses(outer.eval_rows)
    target = 1
    source = 0
    response_start = int(feature_space.R[target, 0])
    target_columns = np.arange(*feature_space.S[target], dtype=np.intp)
    source_columns = np.arange(*feature_space.S[source], dtype=np.intp)
    full_keep = np.setdiff1d(np.arange(feature_space.q), target_columns, assume_unique=True)
    reduced_keep = np.setdiff1d(
        np.arange(feature_space.q),
        np.union1d(target_columns, source_columns),
        assume_unique=True,
    )
    full_beta = direct_restricted_ridge(
        design_train, responses_train, 0.1, full_keep, len(outer.train_rows)
    )
    reduced_beta = direct_restricted_ridge(
        design_train, responses_train, 0.1, reduced_keep, len(outer.train_rows)
    )
    full_train = design_train[:, full_keep] @ full_beta[:, response_start : response_start + 1]
    full_eval = design_eval[:, full_keep] @ full_beta[:, response_start : response_start + 1]
    reduced_train = design_train[:, reduced_keep] @ reduced_beta[:, response_start : response_start + 1]
    reduced_eval = design_eval[:, reduced_keep] @ reduced_beta[:, response_start : response_start + 1]
    full_logq, _ = gaussian_logscore(
        responses_eval[:, response_start],
        full_eval[:, 0],
        responses_train[:, response_start] - full_train[:, 0],
        float(feature_space.response_specs[target].y_sd),
        config.variance_floor,
    )
    reduced_logq, _ = gaussian_logscore(
        responses_eval[:, response_start],
        reduced_eval[:, 0],
        responses_train[:, response_start] - reduced_train[:, 0],
        float(feature_space.response_specs[target].y_sd),
        config.variance_floor,
    )

    expected = float(np.mean(full_logq - reduced_logq))
    assert result.directional_sum[source, target] / result.directional_rows[source, target] == pytest.approx(
        expected, rel=1e-7
    )


def test_aggregate_uses_row_sums_and_preserves_signed_weight() -> None:
    frame, schema, config = _continuous_fixture()
    prepared = prepare_data(frame, schema, config)
    directional_sum = np.zeros((3, 3), dtype=np.float64)
    directional_rows = np.zeros((3, 3), dtype=np.intp)
    directional_folds = np.zeros((3, 3), dtype=np.intp)
    directional_started = np.zeros((3, 3), dtype=bool)
    directional_failure = np.zeros((3, 3), dtype=bool)
    directional_sum[0, 1] = 12.0
    directional_sum[1, 0] = -6.0
    directional_sum[0, 2] = -12.0
    directional_sum[2, 0] = -6.0
    directional_rows[0, 1] = directional_rows[1, 0] = prepared.n_retained
    directional_folds[0, 1] = directional_folds[1, 0] = 2
    directional_started[0, 1] = directional_started[1, 0] = True
    for source in range(3):
        for target in range(3):
            if source != target:
                directional_rows[source, target] = prepared.n_retained
                directional_folds[source, target] = 2
                directional_started[source, target] = True

    fit = aggregate(
        prepared,
        directional_sum,
        directional_rows,
        directional_folds,
        directional_started,
        directional_failure,
        set(),
        {},
        [],
        [],
        {"complete": True},
        expected_folds=2,
    )
    pair = fit.pairs.loc[(fit.pairs.node_i == "a") & (fit.pairs.node_j == "b")].iloc[0]

    assert pair.gain_i_to_j == pytest.approx(0.4)
    assert pair.gain_j_to_i == pytest.approx(-0.2)
    assert pair.weight_nats_raw == pytest.approx(0.1)
    assert pair.display_magnitude_nats == pytest.approx(0.1)
    negative_pair = fit.pairs.loc[
        (fit.pairs.node_i == "a") & (fit.pairs.node_j == "c")
    ].iloc[0]
    assert negative_pair.weight_nats_raw == pytest.approx(-0.3)
    assert negative_pair.display_magnitude_nats == 0.0
    assert negative_pair.gaussian_equivalent_magnitude == 0.0


def test_score_partition_handles_mixed_response_types() -> None:
    rows = np.arange(30, dtype=np.float64)
    frame = pd.DataFrame(
        {
            "a": np.sin(rows / 4.0),
            "b": np.asarray(rows, dtype=np.intp) % 2,
            "c": np.asarray(rows, dtype=np.intp) % 3,
        }
    )
    schema = {
        "a": {"kind": "continuous"},
        "b": {"kind": "categorical", "levels": [0, 1]},
        "c": {"kind": "categorical", "levels": [0, 1, 2]},
    }
    config = CINConfig(seed=12, lambda_grid=(0.1, 1.0))
    prepared = prepare_data(frame, schema, config)
    outer = make_splits(prepared.n_retained, config).outer[0]
    feature_space = fit_feature_space(prepared, outer.train_rows, config)
    result = score_partition(
        prepared,
        feature_space,
        outer.train_rows,
        outer.eval_rows,
        np.full(3, 0.1),
        config,
        Budget(time.monotonic() + 30),
        CostCounters(),
        0,
    )

    assert np.isfinite(result.directional_sum[~np.eye(3, dtype=bool)]).all()


def test_fit_network_is_deterministic_and_keeps_raw_data_out_of_metadata() -> None:
    frame, schema, config = _continuous_fixture()

    left = fit_network(frame, schema, config)
    right = fit_network(frame, schema, config)

    pd.testing.assert_frame_equal(left.pairs, right.pairs)
    pd.testing.assert_frame_equal(left.nodes, right.nodes)
    pd.testing.assert_frame_equal(left.folds, right.folds)
    assert left.metadata["fit_id"] == right.metadata["fit_id"]
    assert left.metadata["split_seeds"] == right.metadata["split_seeds"]
    assert left.metadata["complete"] is True
    assert "values" not in left.to_dict()
    assert "codes" not in left.metadata


def test_fit_network_batch_size_does_not_change_pairs() -> None:
    frame, schema, config = _continuous_fixture()

    left = fit_network(frame, schema, config)
    right = fit_network(frame, schema, CINConfig(**{**config.__dict__, "pair_batch_size": 2}))

    pd.testing.assert_frame_equal(left.pairs, right.pairs)
    assert left.metadata["fit_id"] == right.metadata["fit_id"]


def test_fit_network_expired_deadline_marks_pairs_not_started() -> None:
    frame, schema, config = _continuous_fixture()

    result = fit_network(frame, schema, config, deadline=time.monotonic() - 1.0)

    assert result.metadata["complete"] is False
    assert set(result.pairs.status) == {"not_started"}
    assert result.pairs.weight_nats_raw.isna().all()


def test_fit_network_isolates_target_numerical_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import mintnet.cin.fit as fit_module
    from mintnet.cin.ridge import RidgeNumericalFailure

    frame, schema, config = _continuous_fixture()
    original = fit_module._score_target

    def fail_target(*args: object, **kwargs: object) -> tuple[np.ndarray, dict[str, object]]:
        target = int(args[2])
        if target == 0 and len(args[3]) == 20:
            raise RidgeNumericalFailure("injected target failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(fit_module, "_score_target", fail_target)
    result = fit_network(frame, schema, config)

    pair_ab = result.pairs.loc[(result.pairs.node_i == "a") & (result.pairs.node_j == "b")].iloc[0]
    pair_bc = result.pairs.loc[(result.pairs.node_i == "b") & (result.pairs.node_j == "c")].iloc[0]
    assert pair_ab.status == "numerical_failure"
    assert pair_bc.status == "complete"


def test_fit_network_started_budget_stop_does_not_publish_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mintnet.cin.fit as fit_module

    frame, schema, config = _continuous_fixture()
    original = fit_module.Budget.check

    def stop_after_first_target(self: Budget, phase: str) -> None:
        if phase == "outer fold 0 target 1":
            raise BudgetExceeded("injected deadline")
        original(self, phase)

    monkeypatch.setattr(fit_module.Budget, "check", stop_after_first_target)
    result = fit_network(frame, schema, config)

    assert result.metadata["complete"] is False
    assert set(result.pairs.status) == {"budget_exceeded"}
    assert result.pairs.weight_nats_raw.isna().all()


def test_fit_network_reports_type_specific_node_diagnostics() -> None:
    rows = np.arange(30, dtype=np.float64)
    frame = pd.DataFrame(
        {
            "a": np.sin(rows / 4.0),
            "b": np.asarray(rows, dtype=np.intp) % 2,
            "c": np.asarray(rows, dtype=np.intp) % 3,
        }
    )
    schema = {
        "a": {"kind": "continuous"},
        "b": {"kind": "categorical", "levels": [0, 1]},
        "c": {"kind": "categorical", "levels": [0, 1, 2]},
    }
    result = fit_network(frame, schema, CINConfig(seed=12, lambda_grid=(0.1, 1.0)))

    for column in (
        "variance_floor_hits",
        "training_mse_mean",
        "evaluation_mse_mean",
        "clipped_fraction_mean",
        "zero_sum_fallbacks",
        "min_probability",
        "rare_training_levels",
        "absent_training_levels",
    ):
        assert column in result.nodes.columns


def test_fit_network_factorization_count_is_bounded_for_wide_network() -> None:
    rows = np.arange(30, dtype=np.float64)
    frame = pd.DataFrame(
        {f"v{index}": np.sin(rows / (index + 2.0)) + index * rows / 100.0 for index in range(12)}
    )
    schema = {name: {"kind": "continuous"} for name in frame.columns}
    config = CINConfig(seed=15, max_seconds=30.0, pair_batch_size=32)

    result = fit_network(frame, schema, config)

    assert result.metadata["cost"]["n_large_factorizations"] <= 45
