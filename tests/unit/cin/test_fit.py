from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from mintnet.cin.config import CINConfig
from mintnet.cin.fit import Budget, BudgetExceeded, make_splits
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
