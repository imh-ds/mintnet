import numpy as np
import pandas as pd

from mintnet.experiments.stage7d_conditions import condition_label
from mintnet.experiments.stage7d_frontier import ALPHAS, family_detection_limit, rejection_curve


def test_rejection_curve_matches_manual_counts():
    p_values = pd.Series([0.001, 0.02, 0.2, 0.4, np.nan])
    curve = rejection_curve(p_values)
    assert curve[0.01] == 0.25  # only 0.001 <= 0.01, out of 4 non-nan
    assert curve[0.5] == 1.0
    assert set(curve) == set(ALPHAS)


def test_rejection_curve_all_nan_returns_nan_everywhere():
    curve = rejection_curve(pd.Series([np.nan, np.nan]))
    assert all(np.isnan(v) for v in curve.values())


def _synthetic_raw(n: int, p_by_condition: dict[str, float]) -> pd.DataFrame:
    """One row per condition, `status='ok'`, with the given p-value --
    enough to exercise the feasibility logic without a real DGP."""
    rows = []
    for condition, p_value in p_by_condition.items():
        rows.append({"condition": condition, "n": n, "status": "ok", "p_value_12": p_value})
    return pd.DataFrame(rows)


def test_family_detection_limit_finds_the_smallest_feasible_param():
    """Null p-value=1 everywhere (never rejects -> pruning rate is
    perfect at every alpha); linear_0.08's own p-value=0 (always
    rejects -> full power at every alpha) should make 0.08 the
    detection limit, since 0.12/0.15/0.20 are absent (treated as
    empty/no-power, but 0.08 already qualifies and is checked first)."""
    raw = _synthetic_raw(
        750,
        {
            condition_label("linear", 0.0): 1.0,
            condition_label("linear", 0.08): 0.0,
            condition_label("ushape", 0.0): 1.0,
            condition_label("ushape", 0.3): 0.0,
        },
    )
    # replicate rows so rejection_curve has more than one point (mirrors real usage)
    raw = pd.concat([raw] * 10, ignore_index=True)

    limits = family_detection_limit(raw, condition_column="condition", p_value_column="p_value_12", n=750)
    assert limits["linear"] == 0.08
    assert limits["curvature"] is None  # only linear_0.0 null present; no curvature_* power cells -> never feasible
    assert limits["ushape"] == 0.3


def test_family_detection_limit_returns_none_when_nothing_is_feasible():
    raw = _synthetic_raw(
        750,
        {
            condition_label("linear", 0.0): 0.5,  # rejects half the time -> pruning rate only .5, fails .80 floor
            condition_label("linear", 0.08): 0.5,  # low power too
        },
    )
    raw = pd.concat([raw] * 10, ignore_index=True)
    limits = family_detection_limit(raw, condition_column="condition", p_value_column="p_value_12", n=750)
    assert limits["linear"] is None
