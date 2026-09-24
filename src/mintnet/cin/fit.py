"""Cross-fitting and fit orchestration for CIN."""

from __future__ import annotations

import time
import hashlib
import json
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from importlib import metadata as importlib_metadata
from typing import Any

import numpy as np
import pandas as pd

from .config import CINConfig
from .result import NetworkFit

__all__ = [
    "Budget",
    "BudgetExceeded",
    "CostCounters",
    "FoldScore",
    "InnerSplit",
    "NetworkFit",
    "OuterSplit",
    "SplitPlan",
    "TuningResult",
    "aggregate",
    "fit_network",
    "make_splits",
    "score_partition",
    "target_supported",
    "tune_lambdas",
]


def _readonly(values: Any, *, dtype: Any = np.intp) -> np.ndarray:
    result = np.ascontiguousarray(values, dtype=dtype)
    result.setflags(write=False)
    return result


def _partition(rows: np.ndarray, n_folds: int) -> tuple[np.ndarray, ...]:
    if rows.ndim != 1 or rows.size < n_folds:
        raise ValueError("n_rows must be at least the number of folds")
    sizes = np.full(n_folds, rows.size // n_folds, dtype=np.intp)
    sizes[: rows.size % n_folds] += 1
    result: list[np.ndarray] = []
    start = 0
    for size in sizes:
        result.append(_readonly(rows[start : start + int(size)]))
        start += int(size)
    return tuple(result)


@dataclass(frozen=True)
class InnerSplit:
    train_rows: np.ndarray
    eval_rows: np.ndarray


@dataclass(frozen=True)
class OuterSplit:
    train_rows: np.ndarray
    eval_rows: np.ndarray
    inner: tuple[InnerSplit, ...]


@dataclass(frozen=True)
class SplitPlan:
    outer: tuple[OuterSplit, ...]
    seed_metadata: dict[str, Any]


def _seed_record(sequence: np.random.SeedSequence) -> dict[str, Any]:
    entropy = sequence.entropy
    if isinstance(entropy, np.ndarray):
        entropy = entropy.tolist()
    elif isinstance(entropy, tuple):
        entropy = list(entropy)
    return {"entropy": entropy, "spawn_key": list(sequence.spawn_key)}


def make_splits(n_rows: int, config: CINConfig) -> SplitPlan:
    """Make one shared deterministic outer/inner split plan."""

    if isinstance(n_rows, bool) or not isinstance(n_rows, (int, np.integer)) or n_rows < 1:
        raise ValueError("n_rows must be a positive integer")
    if not isinstance(config, CINConfig):
        raise ValueError("config must be a CINConfig instance")

    root = np.random.SeedSequence(config.seed)
    outer_sequence = root.spawn(1)[0]
    inner_sequences = root.spawn(config.outer_folds)
    permutation = np.random.default_rng(outer_sequence).permutation(int(n_rows))
    outer_eval_parts = _partition(permutation, config.outer_folds)
    all_rows = np.arange(int(n_rows), dtype=np.intp)
    outer_splits: list[OuterSplit] = []
    seed_metadata: dict[str, Any] = {
        "root_entropy": int(config.seed),
        "outer": _seed_record(outer_sequence),
        "inner": [_seed_record(sequence) for sequence in inner_sequences],
    }
    for fold_index, eval_rows in enumerate(outer_eval_parts):
        train_rows = _readonly(np.setdiff1d(all_rows, eval_rows, assume_unique=True))
        inner_permutation = np.random.default_rng(inner_sequences[fold_index]).permutation(train_rows)
        inner_eval_parts = _partition(inner_permutation, config.inner_folds)
        inner_splits: list[InnerSplit] = []
        for inner_eval in inner_eval_parts:
            inner_train = _readonly(np.setdiff1d(train_rows, inner_eval, assume_unique=True))
            inner_splits.append(InnerSplit(train_rows=inner_train, eval_rows=inner_eval))
        outer_splits.append(
            OuterSplit(train_rows=train_rows, eval_rows=eval_rows, inner=tuple(inner_splits))
        )
    return SplitPlan(outer=tuple(outer_splits), seed_metadata=seed_metadata)


class BudgetExceeded(RuntimeError):
    """Raised when an absolute fit deadline has elapsed."""


@dataclass
class Budget:
    deadline: float

    def check(self, phase: str) -> None:
        if not isinstance(phase, str) or not phase:
            raise ValueError("phase must be a non-empty string")
        if not np.isfinite(float(self.deadline)):
            raise ValueError("deadline must be finite")
        if time.monotonic() >= float(self.deadline):
            raise BudgetExceeded(f"CIN fit deadline exceeded during {phase}")


@dataclass
class CostCounters:
    n_large_factorizations: int = 0
    q: int = 0
    t: int = 0
    n_fallbacks: int = 0
    phase_seconds: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TuningResult:
    lambda_by_fold: np.ndarray
    supported_by_fold: np.ndarray
    diagnostics: tuple[dict[str, Any], ...]


def target_supported(prepared: Any, feature_space: Any, target: int, rows: np.ndarray) -> bool:
    """Return whether a target has a usable response in one training partition."""

    response = feature_space.response_specs[target]
    if response.columns == 0:
        return False
    if response.kind == "categorical":
        return np.unique(prepared.codes[rows, target]).size > 1
    return bool(np.std(prepared.values[rows, target], ddof=0) > 0.0)


def _score_target(
    prepared: Any,
    feature_space: Any,
    target: int,
    train_rows: np.ndarray,
    eval_rows: np.ndarray,
    train_responses: np.ndarray,
    train_prediction: np.ndarray,
    eval_prediction: np.ndarray,
    config: CINConfig,
) -> tuple[np.ndarray, dict[str, Any]]:
    from .scores import categorical_logscore, gaussian_logscore

    response = feature_space.response_specs[target]
    start, stop = (int(value) for value in feature_space.R[target])
    if response.kind == "continuous":
        y_train = train_responses[:, start]
        y_eval = feature_space.responses(eval_rows)[:, start]
        return gaussian_logscore(
            y_eval,
            eval_prediction[:, 0],
            y_train - train_prediction[:, 0],
            float(response.y_sd),
            config.variance_floor,
        )
    assert response.prevalence is not None
    assert response.train_counts is not None
    return categorical_logscore(
        prepared.codes[eval_rows, target],
        eval_prediction[:, : stop - start],
        response.prevalence,
        response.train_counts,
        len(train_rows),
        config.probability_mixture,
        config.count_pseudocount,
    )


def tune_lambdas(
    prepared: Any,
    split_plan: SplitPlan,
    config: CINConfig,
    budget: Budget,
    counters: CostCounters,
) -> TuningResult:
    """Select one penalty per target and outer fold from inner held-out scores."""

    from .features import fit_feature_space
    from .ridge import OmissionWorkspace, RidgeSolution
    from .scores import choose_lambda

    n_targets = len(prepared.specs)
    n_lambdas = len(config.lambda_grid)
    selected = np.full((len(split_plan.outer), n_targets), np.nan, dtype=np.float64)
    supported = np.zeros((len(split_plan.outer), n_targets), dtype=bool)
    diagnostics: list[dict[str, Any]] = []
    phase_start = time.perf_counter()

    for fold_index, outer in enumerate(split_plan.outer):
        budget.check(f"tuning fold {fold_index}")
        score_sums = np.zeros((n_targets, n_lambdas), dtype=np.float64)
        score_rows = np.zeros((n_targets, n_lambdas), dtype=np.intp)
        fold_supported = np.ones(n_targets, dtype=bool)
        fold_diagnostics: dict[str, Any] = {
            "fold": fold_index,
            "tiny_partition": len(outer.inner[0].train_rows) < config.min_rows,
            "inner_factorizations": 0,
        }
        for inner_index, inner in enumerate(outer.inner):
            budget.check(f"tuning fold {fold_index} inner {inner_index}")
            feature_space = fit_feature_space(prepared, inner.train_rows, config)
            train_design = feature_space.design(inner.train_rows)
            eval_design = feature_space.design(inner.eval_rows)
            train_responses = feature_space.responses(inner.train_rows)
            inner_support = np.asarray(
                [target_supported(prepared, feature_space, target, inner.train_rows) for target in range(n_targets)],
                dtype=bool,
            )
            fold_supported &= inner_support
            for lambda_index, lam in enumerate(config.lambda_grid):
                budget.check(f"tuning fold {fold_index} lambda {lambda_index}")
                solution = RidgeSolution(train_design, train_responses, lam, config)
                counters.n_large_factorizations += 1
                fold_diagnostics["inner_factorizations"] += 1
                counters.q = max(counters.q, solution.q)
                counters.t = max(counters.t, solution.t)
                workspace = OmissionWorkspace(
                    solution,
                    {"train": train_design, "eval": eval_design},
                )
                for target in range(n_targets):
                    if not inner_support[target]:
                        continue
                    start, stop = (int(value) for value in feature_space.S[target])
                    response_start, response_stop = (
                        int(value) for value in feature_space.R[target]
                    )
                    train_prediction, _ = workspace.predict_omit(
                        "train",
                        np.arange(start, stop, dtype=np.intp),
                        np.arange(response_start, response_stop, dtype=np.intp),
                    )
                    eval_prediction, _ = workspace.predict_omit(
                        "eval",
                        np.arange(start, stop, dtype=np.intp),
                        np.arange(response_start, response_stop, dtype=np.intp),
                    )
                    logq, _ = _score_target(
                        prepared,
                        feature_space,
                        target,
                        inner.train_rows,
                        inner.eval_rows,
                        train_responses,
                        train_prediction,
                        eval_prediction,
                        config,
                    )
                    if not np.isfinite(logq).all():
                        fold_supported[target] = False
                        continue
                    score_sums[target, lambda_index] += float(np.sum(logq))
                    score_rows[target, lambda_index] += logq.size
                counters.n_fallbacks += workspace.fallback_count
                workspace.check_fallback_rate(config.fallback_stop_fraction)

        for target in range(n_targets):
            if not fold_supported[target] or np.any(score_rows[target] == 0):
                fold_diagnostics.setdefault("unsupported_targets", []).append(target)
                continue
            lambda_value, _ = choose_lambda(
                score_sums[target],
                int(score_rows[target, 0]),
                config.lambda_grid,
                config.tie_tolerance,
            )
            selected[fold_index, target] = lambda_value
            supported[fold_index, target] = True
        diagnostics.append(fold_diagnostics)
    counters.phase_seconds["tuning"] = counters.phase_seconds.get("tuning", 0.0) + (
        time.perf_counter() - phase_start
    )
    return TuningResult(
        lambda_by_fold=np.ascontiguousarray(selected),
        supported_by_fold=np.ascontiguousarray(supported),
        diagnostics=tuple(diagnostics),
    )


@dataclass
class FoldScore:
    directional_sum: np.ndarray
    directional_rows: np.ndarray
    directional_started: np.ndarray
    directional_failure: np.ndarray
    node_score_sum: np.ndarray
    node_score_rows: np.ndarray
    node_diagnostics: tuple[dict[str, Any], ...]
    fold_diagnostics: dict[str, Any]
    unsupported_targets: frozenset[int] = frozenset()
    pair_flags: dict[tuple[int, int], set[str]] = field(default_factory=dict)


def _intercept_score(
    prepared: Any,
    feature_space: Any,
    target: int,
    eval_rows: np.ndarray,
    config: CINConfig,
) -> tuple[np.ndarray, dict[str, Any]]:
    from .scores import intercept_scores

    response = feature_space.response_specs[target]
    start, _ = (int(value) for value in feature_space.R[target])
    if response.kind == "continuous":
        return intercept_scores(
            "continuous",
            feature_space.responses(eval_rows)[:, start],
            sd_y=float(response.y_sd),
            variance_floor=config.variance_floor,
        )
    assert response.prevalence is not None
    assert response.train_counts is not None
    return intercept_scores(
        "categorical",
        prepared.codes[eval_rows, target],
        prevalence=response.prevalence,
        train_counts=response.train_counts,
        m=int(np.sum(response.train_counts, dtype=np.int64)),
        mixture=config.probability_mixture,
        pseudocount=config.count_pseudocount,
    )


def _mark_target_failure(
    failure: np.ndarray,
    target: int,
) -> None:
    for source in range(failure.shape[0]):
        if source != target:
            failure[source, target] = True


def score_partition(
    prepared: Any,
    feature_space: Any,
    train_rows: np.ndarray,
    eval_rows: np.ndarray,
    chosen_lambdas: np.ndarray,
    config: CINConfig,
    budget: Budget,
    counters: CostCounters,
    fold_index: int,
) -> FoldScore:
    """Score all ordered predictor-to-target directions for one outer fold."""

    from .ridge import OmissionWorkspace, RidgeNumericalFailure, RidgeSolution

    n_targets = len(prepared.specs)
    lambdas = np.asarray(chosen_lambdas, dtype=np.float64)
    if lambdas.shape != (n_targets,):
        raise ValueError("chosen_lambdas must contain one value per target")
    directional_sum = np.zeros((n_targets, n_targets), dtype=np.float64)
    directional_rows = np.zeros((n_targets, n_targets), dtype=np.intp)
    directional_started = np.zeros((n_targets, n_targets), dtype=bool)
    directional_failure = np.zeros((n_targets, n_targets), dtype=bool)
    node_score_sum = np.zeros((n_targets, 2), dtype=np.float64)
    node_score_rows = np.zeros(n_targets, dtype=np.intp)
    node_diagnostics: list[dict[str, Any]] = []
    unsupported_targets: set[int] = set()
    pair_flags: dict[tuple[int, int], set[str]] = {}
    fold_diagnostics: dict[str, Any] = {
        "fold": int(fold_index),
        "train_rows": int(len(train_rows)),
        "eval_rows": int(len(eval_rows)),
        "factorizations": 0,
        "fallbacks": 0,
        "status": "complete",
    }
    train_design = feature_space.design(train_rows)
    eval_design = feature_space.design(eval_rows)
    train_responses = feature_space.responses(train_rows)
    distinct_lambdas = sorted({float(value) for value in lambdas if np.isfinite(value)})
    phase_start = time.perf_counter()

    for lambda_index, lam in enumerate(distinct_lambdas):
        budget.check(f"outer fold {fold_index} lambda {lambda_index}")
        solution = RidgeSolution(train_design, train_responses, lam, config)
        counters.n_large_factorizations += 1
        fold_diagnostics["factorizations"] += 1
        counters.q = max(counters.q, solution.q)
        counters.t = max(counters.t, solution.t)
        workspace = OmissionWorkspace(
            solution,
            {"train": train_design, "eval": eval_design},
        )
        target_indices = [
            target for target, target_lambda in enumerate(lambdas) if np.isfinite(target_lambda) and target_lambda == lam
        ]
        for target in target_indices:
            budget.check(f"outer fold {fold_index} target {target}")
            if not target_supported(prepared, feature_space, target, train_rows):
                unsupported_targets.add(target)
                continue
            s_start, s_stop = (int(value) for value in feature_space.S[target])
            r_start, r_stop = (int(value) for value in feature_space.R[target])
            self_columns = np.arange(s_start, s_stop, dtype=np.intp)
            response_columns = np.arange(r_start, r_stop, dtype=np.intp)
            try:
                full_train, _ = workspace.predict_omit("train", self_columns, response_columns)
                full_eval, _ = workspace.predict_omit("eval", self_columns, response_columns)
                full_logq, full_info = _score_target(
                    prepared,
                    feature_space,
                    target,
                    train_rows,
                    eval_rows,
                    train_responses,
                    full_train,
                    full_eval,
                    config,
                )
                intercept_logq, intercept_info = _intercept_score(
                    prepared,
                    feature_space,
                    target,
                    eval_rows,
                    config,
                )
                if not np.isfinite(full_logq).all() or not np.isfinite(intercept_logq).all():
                    raise RidgeNumericalFailure("non-finite full or intercept score")
                node_score_sum[target] = (float(np.sum(full_logq)), float(np.sum(intercept_logq)))
                node_score_rows[target] = full_logq.size
                node_diagnostics.append(
                    {
                        "node": prepared.names[target],
                        "fold": int(fold_index),
                        "lambda": float(lam),
                        "full_score_sum": float(np.sum(full_logq)),
                        "intercept_score_sum": float(np.sum(intercept_logq)),
                        "n_rows": int(full_logq.size),
                        "full_info": full_info,
                        "intercept_info": intercept_info,
                    }
                )
            except (RidgeNumericalFailure, ValueError, FloatingPointError):
                _mark_target_failure(directional_failure, target)
                continue

            predictor_indices = [source for source in range(n_targets) if source != target]
            for batch_start in range(0, len(predictor_indices), config.pair_batch_size):
                budget.check(f"outer fold {fold_index} target {target} batch {batch_start}")
                batch = predictor_indices[batch_start : batch_start + config.pair_batch_size]
                for source in batch:
                    directional_started[source, target] = True
                    p_start, p_stop = (int(value) for value in feature_space.S[source])
                    if p_start == p_stop:
                        directional_rows[source, target] += len(eval_rows)
                        key = (min(source, target), max(source, target))
                        pair_flags.setdefault(key, set()).add(
                            f"degenerate_predictor_fold_{fold_index}"
                        )
                        continue
                    omit_columns = np.unique(
                        np.concatenate((self_columns, np.arange(p_start, p_stop, dtype=np.intp)))
                    )
                    try:
                        reduced_train, _ = workspace.predict_omit(
                            "train", omit_columns, response_columns
                        )
                        reduced_eval, _ = workspace.predict_omit(
                            "eval", omit_columns, response_columns
                        )
                        reduced_logq, _ = _score_target(
                            prepared,
                            feature_space,
                            target,
                            train_rows,
                            eval_rows,
                            train_responses,
                            reduced_train,
                            reduced_eval,
                            config,
                        )
                        if not np.isfinite(reduced_logq).all():
                            raise RidgeNumericalFailure("non-finite reduced score")
                        directional_sum[source, target] += float(
                            np.sum(full_logq - reduced_logq)
                        )
                        directional_rows[source, target] += reduced_logq.size
                    except (RidgeNumericalFailure, ValueError, FloatingPointError):
                        directional_failure[source, target] = True
        counters.n_fallbacks += workspace.fallback_count
        fold_diagnostics["fallbacks"] += workspace.fallback_count
        workspace.check_fallback_rate(config.fallback_stop_fraction)

    counters.phase_seconds["outer_scoring"] = counters.phase_seconds.get("outer_scoring", 0.0) + (
        time.perf_counter() - phase_start
    )
    return FoldScore(
        directional_sum=directional_sum,
        directional_rows=directional_rows,
        directional_started=directional_started,
        directional_failure=directional_failure,
        node_score_sum=node_score_sum,
        node_score_rows=node_score_rows,
        node_diagnostics=tuple(node_diagnostics),
        fold_diagnostics=fold_diagnostics,
        unsupported_targets=frozenset(unsupported_targets),
        pair_flags=pair_flags,
    )


def _plain(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def aggregate(
    prepared: Any,
    directional_sum: np.ndarray,
    directional_rows: np.ndarray,
    directional_folds: np.ndarray,
    directional_started: np.ndarray,
    directional_failure: np.ndarray,
    unsupported_targets: set[int],
    pair_flags: dict[tuple[int, int], set[str]],
    node_records: list[dict[str, Any]],
    fold_records: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    expected_folds: int,
) -> NetworkFit:
    """Publish complete pair weights and explicit statuses."""

    from .result import PAIR_COLUMNS

    n_targets = len(prepared.names)
    n_rows = int(prepared.n_retained)
    pair_records: list[dict[str, Any]] = []
    for left in range(n_targets):
        for right in range(left + 1, n_targets):
            key = (left, right)
            flags = set(pair_flags.get(key, set()))
            if left in unsupported_targets or right in unsupported_targets:
                status = "unsupported"
            elif directional_failure[left, right] or directional_failure[right, left]:
                status = "numerical_failure"
            else:
                complete = bool(
                    directional_rows[left, right] == n_rows
                    and directional_rows[right, left] == n_rows
                    and directional_folds[left, right] == expected_folds
                    and directional_folds[right, left] == expected_folds
                )
                if complete:
                    status = "complete"
                elif directional_started[left, right] or directional_started[right, left]:
                    status = "budget_exceeded"
                else:
                    status = "not_started"
            if status == "complete":
                gain_left = float(directional_sum[left, right] / directional_rows[left, right])
                gain_right = float(directional_sum[right, left] / directional_rows[right, left])
                weight = (gain_left + gain_right) / 2.0
                display = max(weight, 0.0)
                gaussian = float(np.sqrt(-np.expm1(-2.0 * display)))
                orientation = abs(gain_left - gain_right)
                n_scored = n_rows
                folds_complete = expected_folds
            else:
                gain_left = gain_right = weight = display = gaussian = orientation = float("nan")
                n_scored = 0
                folds_complete = int(min(directional_folds[left, right], directional_folds[right, left]))
            pair_records.append(
                {
                    "node_i": prepared.names[left],
                    "node_j": prepared.names[right],
                    "gain_i_to_j": gain_left,
                    "gain_j_to_i": gain_right,
                    "weight_nats_raw": weight,
                    "display_magnitude_nats": display,
                    "gaussian_equivalent_magnitude": gaussian,
                    "orientation_gap": orientation,
                    "n_scored": n_scored,
                    "folds_complete": folds_complete,
                    "status": status,
                    "diagnostic_flags": ";".join(sorted(flags)),
                }
            )

    pair_frame = pd.DataFrame(pair_records, columns=PAIR_COLUMNS)
    node_rows: list[dict[str, Any]] = []
    for target, name in enumerate(prepared.names):
        records = [record for record in node_records if record.get("node") == name]
        full_total = sum(float(record.get("full_score_sum", 0.0)) for record in records)
        intercept_total = sum(float(record.get("intercept_score_sum", 0.0)) for record in records)
        scored_rows = sum(int(record.get("n_rows", 0)) for record in records)
        row: dict[str, Any] = {
            "node": name,
            "full_score_mean": full_total / scored_rows if scored_rows else float("nan"),
            "intercept_score_mean": intercept_total / scored_rows if scored_rows else float("nan"),
            "full_minus_intercept": (
                (full_total - intercept_total) / scored_rows if scored_rows else float("nan")
            ),
            "n_predictions_full": scored_rows,
            "n_predictions_intercept": scored_rows,
            "diagnostic_flags": "",
            "variance_floor_hits": 0,
            "training_mse_mean": float("nan"),
            "evaluation_mse_mean": float("nan"),
            "clipped_fraction_mean": float("nan"),
            "zero_sum_fallbacks": 0,
            "min_probability": float("nan"),
            "rare_training_levels": 0,
            "absent_training_levels": 0,
        }
        continuous_infos = [
            record["full_info"]
            for record in records
            if isinstance(record.get("full_info"), dict)
            and "variance_floor_hit" in record["full_info"]
        ]
        categorical_infos = [
            record["full_info"]
            for record in records
            if isinstance(record.get("full_info"), dict)
            and "clipped_fraction" in record["full_info"]
        ]
        if continuous_infos:
            row["variance_floor_hits"] = int(
                sum(bool(info["variance_floor_hit"]) for info in continuous_infos)
            )
            row["training_mse_mean"] = float(
                np.mean([float(info["training_mse"]) for info in continuous_infos])
            )
            row["evaluation_mse_mean"] = float(
                np.mean([float(info["evaluation_mse"]) for info in continuous_infos])
            )
        if categorical_infos:
            row["clipped_fraction_mean"] = float(
                np.mean([float(info["clipped_fraction"]) for info in categorical_infos])
            )
            row["zero_sum_fallbacks"] = int(
                sum(int(info["zero_sum_count"]) for info in categorical_infos)
            )
            row["min_probability"] = float(
                min(float(info["min_probability"]) for info in categorical_infos)
            )
            row["rare_training_levels"] = int(
                sum(int(info["rare_training_levels"]) for info in categorical_infos)
            )
            row["absent_training_levels"] = int(
                sum(int(info["absent_training_levels"]) for info in categorical_infos)
            )
        for fold in range(expected_folds):
            values = [record["lambda"] for record in records if record.get("fold") == fold]
            row[f"lambda_fold_{fold + 1}"] = values[0] if values else float("nan")
        node_rows.append(row)

    node_frame = pd.DataFrame(node_rows)
    fold_frame = pd.DataFrame(fold_records)
    result_metadata = dict(metadata)
    result_metadata["complete"] = bool(
        result_metadata.get("complete", False)
        and all(record["status"] == "complete" for record in pair_records)
    )
    return NetworkFit(pairs=pair_frame, nodes=node_frame, folds=fold_frame, metadata=result_metadata)


def _metadata_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_metadata_value(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _metadata_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_metadata_value(item) for item in value]
    return value


def _dependency_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": platform.python_version()}
    for package in ("numpy", "scipy", "scikit-learn", "pandas"):
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _git_revision() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and revision else None


def _fit_metadata(prepared: Any, schema: Any, config: CINConfig, split_plan: SplitPlan) -> dict[str, Any]:
    config_payload = _metadata_value(asdict(config))
    schema_payload = _metadata_value(schema)
    schema_json = json.dumps(schema_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    code_revision = _git_revision()
    digest_input = "\x1f".join(
        (
            config.config_hash(),
            schema_json,
            prepared.data_digest,
            code_revision or "",
        )
    ).encode("utf-8")
    fit_id = hashlib.sha256(digest_input).hexdigest()[:16]
    return {
        "config": config_payload,
        "config_hash": config.config_hash(),
        "schema": schema_payload,
        "retained_count": int(prepared.n_retained),
        "excluded_count": int(prepared.n_excluded),
        "digests": {
            "data_digest": prepared.data_digest,
            "row_identity_digest": prepared.row_identity_digest,
            "excluded_labels_digest": prepared.excluded_labels_digest,
        },
        "dependencies": _dependency_versions(),
        "split_seeds": _metadata_value(split_plan.seed_metadata),
        "git_revision": code_revision,
        "fit_id": fit_id,
        "complete": True,
        "runtime": {
            "status": "running",
            "deadline_exceeded": False,
        },
        "cost": {
            "n_large_factorizations": 0,
            "q": 0,
            "t": 0,
            "phase_seconds": {},
            "peak_rss_mb": None,
            "n_fallbacks": 0,
        },
    }


def _empty_accumulators(n_targets: int) -> tuple[np.ndarray, ...]:
    shape = (n_targets, n_targets)
    return (
        np.zeros(shape, dtype=np.float64),
        np.zeros(shape, dtype=np.intp),
        np.zeros(shape, dtype=np.intp),
        np.zeros(shape, dtype=bool),
        np.zeros(shape, dtype=bool),
    )


def _mark_all_started(started: np.ndarray) -> None:
    started[:] = True
    np.fill_diagonal(started, False)


def fit_network(
    frame: Any = None,
    schema: Any = None,
    config: CINConfig | None = None,
    *,
    deadline: float | None = None,
) -> NetworkFit:
    """Fit a cross-validated CIN network using shared fold orchestration."""

    if config is None:
        raise NotImplementedError("fit_network requires frame, schema, and config")

    from .config import prepare_data
    from .features import fit_feature_space
    from .ridge import RidgeNumericalFailure

    started_at = time.monotonic()
    prepared = prepare_data(frame, schema, config)
    split_plan = make_splits(prepared.n_retained, config)
    actual_deadline = (
        float(deadline) if deadline is not None else started_at + float(config.max_seconds)
    )
    budget = Budget(actual_deadline)
    metadata = _fit_metadata(prepared, schema, config, split_plan)
    counters = CostCounters()
    n_targets = len(prepared.names)
    (
        directional_sum,
        directional_rows,
        directional_folds,
        directional_started,
        directional_failure,
    ) = _empty_accumulators(n_targets)
    unsupported_targets: set[int] = set()
    pair_flags: dict[tuple[int, int], set[str]] = {}
    node_records: list[dict[str, Any]] = []
    fold_records: list[dict[str, Any]] = []
    complete = True
    tuning_started = False
    outer_started = False

    try:
        budget.check("fit setup")
        tuning_started = True
        tuning = tune_lambdas(prepared, split_plan, config, budget, counters)
        unsupported_targets.update(
            int(target)
            for target in np.flatnonzero(~np.all(tuning.supported_by_fold, axis=0))
        )
        for fold_index, outer in enumerate(split_plan.outer):
            budget.check(f"outer fold {fold_index}")
            outer_started = True
            feature_space = fit_feature_space(prepared, outer.train_rows, config)
            fold_score = score_partition(
                prepared,
                feature_space,
                outer.train_rows,
                outer.eval_rows,
                tuning.lambda_by_fold[fold_index],
                config,
                budget,
                counters,
                fold_index,
            )
            directional_sum += fold_score.directional_sum
            directional_rows += fold_score.directional_rows
            directional_started |= fold_score.directional_started
            directional_failure |= fold_score.directional_failure
            completed_direction = (
                fold_score.directional_rows > 0
            ) & ~fold_score.directional_failure
            directional_folds += completed_direction.astype(np.intp)
            unsupported_targets.update(fold_score.unsupported_targets)
            for key, flags in fold_score.pair_flags.items():
                pair_flags.setdefault(key, set()).update(flags)
            node_records.extend(fold_score.node_diagnostics)
            fold_record = dict(fold_score.fold_diagnostics)
            fold_record["lambda_values"] = _metadata_value(tuning.lambda_by_fold[fold_index])
            fold_records.append(fold_record)
    except BudgetExceeded:
        complete = False
        metadata["runtime"]["deadline_exceeded"] = True
        if tuning_started or outer_started or counters.n_large_factorizations:
            _mark_all_started(directional_started)
    except RidgeNumericalFailure:
        complete = False
        directional_failure[:] = True
        np.fill_diagonal(directional_failure, False)

    metadata["complete"] = complete
    metadata["runtime"]["status"] = "complete" if complete else "incomplete"
    metadata["runtime"]["elapsed_seconds"] = float(time.monotonic() - started_at)
    metadata["cost"] = {
        "n_large_factorizations": int(counters.n_large_factorizations),
        "q": int(counters.q),
        "t": int(counters.t),
        "phase_seconds": _metadata_value(counters.phase_seconds),
        "peak_rss_mb": None,
        "n_fallbacks": int(counters.n_fallbacks),
    }
    return aggregate(
        prepared,
        directional_sum,
        directional_rows,
        directional_folds,
        directional_started,
        directional_failure,
        unsupported_targets,
        pair_flags,
        node_records,
        fold_records,
        metadata,
        expected_folds=config.outer_folds,
    )
