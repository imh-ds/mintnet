"""Cross-fitting and fit orchestration for CIN."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import CINConfig
from .result import NetworkFit

__all__ = [
    "Budget",
    "BudgetExceeded",
    "CostCounters",
    "InnerSplit",
    "NetworkFit",
    "OuterSplit",
    "SplitPlan",
    "TuningResult",
    "fit_network",
    "make_splits",
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


def fit_network(*args: object, **kwargs: object) -> NetworkFit:
    raise NotImplementedError("CIN fit orchestration is implemented in later steps")
