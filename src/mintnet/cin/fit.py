"""Cross-fitting and fit orchestration for CIN."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import CINConfig
from .result import NetworkFit

__all__ = [
    "Budget",
    "BudgetExceeded",
    "InnerSplit",
    "NetworkFit",
    "OuterSplit",
    "SplitPlan",
    "fit_network",
    "make_splits",
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


def fit_network(*args: object, **kwargs: object) -> NetworkFit:
    raise NotImplementedError("CIN fit orchestration is implemented in later steps")
