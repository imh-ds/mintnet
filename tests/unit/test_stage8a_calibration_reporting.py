import numpy as np
import pandas as pd
import pytest

from mintnet.experiments.stage8a_calibration_reporting import (
    Stage8aDecision,
    bin_margins,
    bin_table,
    check_monotonicity,
    compute_ece,
    evaluate_stage8a_gate,
)


class _FakeConfig:
    def __init__(self, ece_tolerance: float = 0.10, bin_count: int = 10) -> None:
        self.ece_tolerance = ece_tolerance
        self.bin_count = bin_count


def _rows(condition: str, n: int, margins: list[float], correct: list[float]) -> list[dict[str, object]]:
    assert len(margins) == len(correct)
    return [
        {
            "condition": condition,
            "n": n,
            "edge": "01",
            "margin": margin,
            "correct": is_correct,
            "status": "ok",
        }
        for margin, is_correct in zip(margins, correct)
    ]


def test_bin_margins_excludes_error_rows_and_nan_margins() -> None:
    raw = pd.DataFrame(
        _rows("chain_0.5", 750, [0.5, np.nan], [1.0, 1.0])
        + [{"condition": "chain_0.5", "n": 750, "edge": "01", "margin": 0.9, "correct": 1.0, "status": "error"}]
    )
    scored = bin_margins(raw, bin_count=10)
    assert len(scored) == 1
    assert scored.iloc[0]["margin"] == 0.5


def test_bin_margins_derives_motif_from_condition_label() -> None:
    raw = pd.DataFrame(_rows("weak_edge_triangle_0.08", 1500, [0.3], [1.0]))
    scored = bin_margins(raw, bin_count=10)
    assert scored.iloc[0]["motif"] == "weak_edge_triangle"


def test_bin_table_reports_perfect_calibration_when_margin_equals_accuracy() -> None:
    """A synthetic well-calibrated setup: within each decile, the
    fraction correct exactly equals the bin's own margin midpoint --
    ECE should come out near zero and monotonicity should hold."""
    rng = np.random.default_rng(0)
    rows = []
    for bin_index in range(10):
        low, high = bin_index / 10, (bin_index + 1) / 10
        target_accuracy = (low + high) / 2
        count = 200
        margins = rng.uniform(low, high, size=count)
        correct = (rng.uniform(size=count) < target_accuracy).astype(float)
        rows.extend(_rows("chain_0.5", 750, list(margins), list(correct)))
    raw = pd.DataFrame(rows)

    scored = bin_margins(raw, bin_count=10)
    bins = bin_table(scored, bin_count=10)
    ece = compute_ece(bins)
    monotonic = check_monotonicity(bins)

    assert ece[("chain", 750)] < 0.10
    assert monotonic[("chain", 750)]


def test_check_monotonicity_flags_a_real_reversal() -> None:
    """High-margin bin scoring worse than a low-margin bin, both with
    enough count for a tight CI, must be flagged as a violation."""
    rows = []
    rows.extend(_rows("chain_0.5", 750, [0.05] * 200, [1.0] * 200))  # low margin, high accuracy
    rows.extend(_rows("chain_0.5", 750, [0.95] * 200, [0.0] * 200))  # high margin, zero accuracy
    raw = pd.DataFrame(rows)

    scored = bin_margins(raw, bin_count=10)
    bins = bin_table(scored, bin_count=10)
    monotonic = check_monotonicity(bins)

    assert not monotonic[("chain", 750)]


def test_evaluate_stage8a_gate_proceeds_on_well_calibrated_evidence() -> None:
    rng = np.random.default_rng(1)
    rows = []
    for bin_index in range(10):
        low, high = bin_index / 10, (bin_index + 1) / 10
        target_accuracy = (low + high) / 2
        count = 200
        margins = rng.uniform(low, high, size=count)
        correct = (rng.uniform(size=count) < target_accuracy).astype(float)
        rows.extend(_rows("chain_0.5", 750, list(margins), list(correct)))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage8a_gate(raw, _FakeConfig())
    assert decision.status == "PROCEED"


def test_evaluate_stage8a_gate_reassesses_defect_over_recalibration_when_both_fail() -> None:
    rows = []
    rows.extend(_rows("chain_0.5", 750, [0.05] * 200, [1.0] * 200))
    rows.extend(_rows("chain_0.5", 750, [0.95] * 200, [0.0] * 200))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage8a_gate(raw, _FakeConfig())
    assert decision.status == "REASSESS_DEFECT"
    assert decision.monotonicity_violations
