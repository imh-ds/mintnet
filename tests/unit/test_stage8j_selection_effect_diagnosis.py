import numpy as np
import pandas as pd

from mintnet.experiments.stage8j_selection_effect_diagnosis import (
    CONDITIONS,
    Stage8jConfig,
    _conditioning_for,
    _sample_fixture,
    _selected_decoy_column,
    expected_combinations,
    expected_row_count,
    run_stage8j,
)
from mintnet.experiments.stage8j_selection_effect_diagnosis_reporting import (
    evaluate_h7,
    evaluate_h8,
    rejection_rate_table,
)


def _config(**overrides) -> Stage8jConfig:
    values = dict(
        sample_sizes=(300, 750),
        strengths=(0.3, 0.7),
        pool_sizes=(5, 20),
        replicates=20,
        batch_size=20,
        master_seed=1,
    )
    values.update(overrides)
    return Stage8jConfig(**values)


def test_sample_fixture_decoys_are_independent_of_the_chain():
    data = _sample_fixture(50_000, 0.5, 10, np.random.default_rng(0))
    assert data.shape == (50_000, 13)
    corr = np.corrcoef(data.T)
    for decoy in range(3, 13):
        for chain_col in (0, 1, 2):
            assert abs(corr[decoy, chain_col]) < 0.02


def test_selected_decoy_column_picks_the_largest_max_correlation():
    rng = np.random.default_rng(3)
    n = 5000
    x1 = rng.normal(size=n)
    x2 = 0.5 * x1 + np.sqrt(1 - 0.25) * rng.normal(size=n)
    x3 = 0.5 * x2 + np.sqrt(1 - 0.25) * rng.normal(size=n)
    decoys = rng.normal(size=(n, 5))
    # Force decoy column 2 (global index 5) to be strongly correlated with x1 in-sample.
    decoys[:, 2] = 0.9 * x1 + np.sqrt(1 - 0.81) * decoys[:, 2]
    data = np.column_stack((x1, x2, x3, decoys))

    selected = _selected_decoy_column(data, k=5)
    assert selected == 5  # column 3 + 2


def test_conditioning_for_each_condition():
    data = np.random.default_rng(4).normal(size=(10, 8))
    assert _conditioning_for("baseline", data, k=5) == (1,)
    assert _conditioning_for("random_decoy", data, k=5) == (1, 3)
    selected = _conditioning_for("selected_decoy", data, k=5)
    assert selected[0] == 1
    assert 3 <= selected[1] < 8


def test_expected_row_count_matches_the_full_grid():
    config = _config()
    assert expected_row_count(config) == len(CONDITIONS) * 2 * 2 * 2 * 20
    combos = expected_combinations(config)
    assert ("baseline", 5, 300, 0.3, 0) in combos
    assert ("selected_decoy", 20, 750, 0.7, 19) in combos


def test_run_stage8j_produces_one_row_per_expected_combination(tmp_path):
    config = _config()
    raw = run_stage8j(config, tmp_path / "out", write_report=False)
    combos = set(zip(raw["condition"], raw["k"], raw["n"], raw["strength"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert (raw["status"] == "ok").all()
    assert (raw.loc[raw["condition"] == "baseline", "conditioning_size"] == 1).all()
    assert (raw.loc[raw["condition"] != "baseline", "conditioning_size"] == 2).all()


def test_run_stage8j_is_deterministic_given_the_same_config_and_seed(tmp_path):
    config = _config()
    first = run_stage8j(config, tmp_path / "a", write_report=False)
    second = run_stage8j(config, tmp_path / "b", write_report=False)
    columns = [c for c in first.columns if c != "elapsed_seconds"]
    pd.testing.assert_frame_equal(first[columns], second[columns])


def test_baseline_tracks_nominal_alpha_closely(tmp_path):
    config = _config(sample_sizes=(1000,), strengths=(0.5,), pool_sizes=(10,), replicates=300, batch_size=300)
    raw = run_stage8j(config, tmp_path / "out", conditions=("baseline",), write_report=False)
    table = rejection_rate_table(raw)
    row = table.iloc[0]
    assert abs(row["rejection_rate"] - row["mean_alpha"]) < 0.05


def test_evaluate_h7_confirms_when_selected_beats_random_at_every_cell():
    table = pd.DataFrame(
        [
            {"condition": "random_decoy", "k": 10, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.15, "ci_low": 0.12, "ci_high": 0.18},
            {"condition": "selected_decoy", "k": 10, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.55, "ci_low": 0.51, "ci_high": 0.59},
        ]
    )
    verdict = evaluate_h7(table)
    assert verdict.status == "CONFIRMED"


def test_evaluate_h7_not_confirmed_when_rates_overlap():
    table = pd.DataFrame(
        [
            {"condition": "random_decoy", "k": 10, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.15, "ci_low": 0.12, "ci_high": 0.18},
            {"condition": "selected_decoy", "k": 10, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.16, "ci_low": 0.13, "ci_high": 0.19},
        ]
    )
    verdict = evaluate_h7(table)
    assert verdict.status == "NOT_CONFIRMED"


def test_evaluate_h8_confirms_when_large_k_exceeds_small_k():
    table = pd.DataFrame(
        [
            {"condition": "selected_decoy", "k": 5, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.30, "ci_low": 0.26, "ci_high": 0.34},
            {"condition": "selected_decoy", "k": 20, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.60, "ci_low": 0.56, "ci_high": 0.64},
        ]
    )
    verdict = evaluate_h8(table)
    assert verdict.status == "CONFIRMED"


def test_evaluate_h8_not_confirmed_when_no_scaling():
    table = pd.DataFrame(
        [
            {"condition": "selected_decoy", "k": 5, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.30, "ci_low": 0.26, "ci_high": 0.34},
            {"condition": "selected_decoy", "k": 20, "n": 750, "strength": 0.5, "count": 500, "rejection_rate": 0.31, "ci_low": 0.27, "ci_high": 0.35},
        ]
    )
    verdict = evaluate_h8(table)
    assert verdict.status == "NOT_CONFIRMED"
