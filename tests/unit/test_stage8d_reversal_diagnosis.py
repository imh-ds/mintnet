import numpy as np
import pandas as pd

from mintnet.experiments.stage8d_reversal_diagnosis import (
    evaluate_h1,
    evaluate_h2,
    h1_cap_reached_table,
    h2_conditioning_size_bins,
)


def _false_edge_rows(dgp, n, count, margin_range, cap_reached, accuracy, rng, conditioning_size=None):
    margins = rng.uniform(*margin_range, size=count)
    correct = (rng.uniform(size=count) < accuracy).astype(float)
    if conditioning_size is None:
        conditioning_size = 4 if cap_reached else 1
    return pd.DataFrame(
        {
            "dgp": dgp, "n": n, "replicate": np.arange(count), "i": 0, "j": 1,
            "is_true_edge": False, "margin": margins, "correct": correct, "status": "ok",
            "cap_reached": cap_reached, "conditioning_size_used": conditioning_size,
        }
    )


def test_h1_cap_reached_table_reports_lower_accuracy_for_cap_reached_in_top_bin() -> None:
    rng = np.random.default_rng(0)
    # Top bin (margin 0.9-1.0): cap_reached=True is unreliable (0.5), cap_reached=False is reliable (0.95).
    exploded = pd.concat(
        [
            _false_edge_rows("chain_fork_hub", 750, 500, (0.9, 1.0), True, 0.5, rng),
            _false_edge_rows("chain_fork_hub", 750, 500, (0.9, 1.0), False, 0.95, rng),
        ],
        ignore_index=True,
    )
    table = h1_cap_reached_table(exploded, bin_count=10)
    row_true = table.loc[(table.dgp == "chain_fork_hub") & (table.n == 750) & (table.cap_reached == True)].iloc[0]  # noqa: E712
    row_false = table.loc[(table.dgp == "chain_fork_hub") & (table.n == 750) & (table.cap_reached == False)].iloc[0]  # noqa: E712

    assert row_true["accuracy"] < row_false["accuracy"]
    assert row_true["count"] == 500 and row_false["count"] == 500


def test_evaluate_h1_confirms_when_cap_reached_is_consistently_less_accurate() -> None:
    rng = np.random.default_rng(1)
    exploded = pd.concat(
        [
            _false_edge_rows("chain_fork_hub", 750, 500, (0.9, 1.0), True, 0.4, rng),
            _false_edge_rows("chain_fork_hub", 750, 500, (0.9, 1.0), False, 0.95, rng),
            _false_edge_rows("overlap", 1500, 500, (0.9, 1.0), True, 0.4, rng),
            _false_edge_rows("overlap", 1500, 500, (0.9, 1.0), False, 0.95, rng),
        ],
        ignore_index=True,
    )
    table = h1_cap_reached_table(exploded, bin_count=10)
    verdict = evaluate_h1(table)

    assert verdict.status == "CONFIRMED"
    assert len(verdict.cells_supporting) == 2
    assert not verdict.cells_contradicting


def test_evaluate_h1_not_confirmed_when_cap_reached_does_not_predict_accuracy() -> None:
    rng = np.random.default_rng(2)
    exploded = pd.concat(
        [
            _false_edge_rows("chain_fork_hub", 750, 500, (0.9, 1.0), True, 0.9, rng),
            _false_edge_rows("chain_fork_hub", 750, 500, (0.9, 1.0), False, 0.9, rng),
        ],
        ignore_index=True,
    )
    table = h1_cap_reached_table(exploded, bin_count=10)
    verdict = evaluate_h1(table)

    assert verdict.status == "INCONCLUSIVE"  # near-identical accuracy -> overlapping CIs


def test_evaluate_h1_inconclusive_when_too_few_cap_reached_cases() -> None:
    rng = np.random.default_rng(3)
    exploded = pd.concat(
        [
            _false_edge_rows("chain_fork_hub", 750, 5, (0.9, 1.0), True, 0.4, rng),  # below min_count
            _false_edge_rows("chain_fork_hub", 750, 500, (0.9, 1.0), False, 0.95, rng),
        ],
        ignore_index=True,
    )
    table = h1_cap_reached_table(exploded, bin_count=10)
    verdict = evaluate_h1(table)

    assert verdict.status == "INCONCLUSIVE"
    assert verdict.cells_inconclusive == [["chain_fork_hub", 750]]


def test_h2_confirms_reversal_concentrated_at_large_conditioning_sizes() -> None:
    rng = np.random.default_rng(4)
    rows = []
    for size in (0, 1):  # small sizes: well-calibrated
        margins = rng.uniform(0.0, 1.0, size=1000)
        correct = (rng.uniform(size=1000) < margins).astype(float)
        rows.append(pd.DataFrame({
            "dgp": "chain_fork_hub", "n": 750, "replicate": np.arange(1000), "i": 0, "j": 1,
            "is_true_edge": False, "margin": margins, "correct": correct, "status": "ok",
            "cap_reached": False, "conditioning_size_used": size,
        }))
    for size in (3, 4):  # large sizes: flat/reversed -- top bin worse than middle
        margins = rng.uniform(0.0, 1.0, size=1000)
        correct = np.where(margins >= 0.9, (rng.uniform(size=1000) < 0.5).astype(float), (rng.uniform(size=1000) < 0.9).astype(float))
        rows.append(pd.DataFrame({
            "dgp": "chain_fork_hub", "n": 750, "replicate": np.arange(1000), "i": 0, "j": 1,
            "is_true_edge": False, "margin": margins, "correct": correct, "status": "ok",
            "cap_reached": True, "conditioning_size_used": size,
        }))
    exploded = pd.concat(rows, ignore_index=True)

    bins = h2_conditioning_size_bins(exploded, bin_count=10)
    verdict = evaluate_h2(bins)

    assert verdict.status == "CONFIRMED"
