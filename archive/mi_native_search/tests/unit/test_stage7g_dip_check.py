import numpy as np
import pandas as pd

from mintnet.experiments.stage7g_dip_check import run_step1


def _raw_for_frontier_confidence(n_to_p12: dict[int, np.ndarray]) -> pd.DataFrame:
    """Build a minimal raw_metrics-shaped frame with only the frontier
    condition (triangle_0) populated -- run_step1 only reads that one."""
    rows = []
    for n, p12_values in n_to_p12.items():
        for replicate, p12 in enumerate(p12_values):
            rows.append(
                {
                    "condition": "triangle_0", "motif": "triangle", "index": 0, "n": n, "replicate": replicate,
                    "seed": 0, "decisive_p_value_01": 0.001, "decisive_p_value_02": 0.001,
                    "decisive_p_value_12": p12, "n_significance_tests": 3, "elapsed_seconds": 0.1,
                    "status": "ok", "error": "",
                }
            )
    return pd.DataFrame(rows)


def test_proceeds_when_dip_is_small_and_overall_trend_is_strong():
    """A real, clean, monotonic-ish improvement in detectability (p12
    shrinking) with one tiny reversal -- mirrors D-083's own reported
    shape (46% overall climb, one ~1% dip)."""
    rng = np.random.default_rng(0)
    # Every mean stays below alpha=0.10 (always "retained"): confidence =
    # (alpha - p) / alpha increases as p shrinks toward 0 -- shrink p
    # steadily as N grows, with a deliberately tiny, noise-scale bump at
    # N=600 (p ticks up very slightly instead of down).
    n_to_mean_p = {400: 0.090, 500: 0.085, 600: 0.087, 700: 0.060, 750: 0.055, 1000: 0.030, 1500: 0.010}
    n_to_p12 = {
        n: np.clip(rng.normal(loc=mean, scale=0.01, size=400), 0.0005, 0.099) for n, mean in n_to_mean_p.items()
    }
    raw = _raw_for_frontier_confidence(n_to_p12)

    result = run_step1(raw)

    assert result.significant_positive_trend
    assert result.status in ("PROCEED", "AMBIGUOUS")


def test_reassesses_when_there_is_no_overall_trend():
    rng = np.random.default_rng(1)
    n_to_p12 = {n: np.clip(rng.normal(loc=0.20, scale=0.05, size=200), 0.001, 0.999) for n in (400, 500, 600, 700, 750, 1000, 1500)}
    raw = _raw_for_frontier_confidence(n_to_p12)

    result = run_step1(raw)

    assert not result.significant_positive_trend
    assert result.status == "REASSESS"


def test_reassesses_when_the_dip_is_a_large_clear_reversal():
    rng = np.random.default_rng(2)
    n_to_mean_p = {400: 0.30, 500: 0.05, 600: 0.45, 700: 0.20, 750: 0.19, 1000: 0.12, 1500: 0.05}
    n_to_p12 = {
        n: np.clip(rng.normal(loc=mean, scale=0.02, size=400), 0.001, 0.999) for n, mean in n_to_mean_p.items()
    }
    raw = _raw_for_frontier_confidence(n_to_p12)

    result = run_step1(raw)

    assert not result.dip_consistent_with_noise
    assert result.status == "REASSESS"
