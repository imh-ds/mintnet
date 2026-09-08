import numpy as np
import pandas as pd

from mintnet.experiments.stage8f_collider_diagnosis import (
    FIXTURES,
    Stage8fConfig,
    _sample_fixture,
    _sample_step2,
    expected_combinations,
    expected_row_count,
    run_stage8f,
)
from mintnet.experiments.stage8f_collider_diagnosis_reporting import (
    evaluate_h1,
    evaluate_h2,
    rejection_rate_table,
)


def _config(**overrides) -> Stage8fConfig:
    values = dict(
        sample_sizes=(300, 750),
        strengths=(0.3, 0.5),
        replicates=20,
        batch_size=20,
        master_seed=1,
    )
    values.update(overrides)
    return Stage8fConfig(**values)


def test_sample_fixture_step1_parents_are_marginally_independent():
    data = _sample_fixture("step1", 50_000, 0.5, np.random.default_rng(0))
    assert data.shape == (50_000, 3)
    assert abs(np.corrcoef(data.T)[0, 1]) < 0.02


def test_sample_step2_collider_third_column_is_a_true_collider():
    data = _sample_step2(50_000, 0.5, np.random.default_rng(1), collider=True)
    assert data.shape == (50_000, 4)
    corr = np.corrcoef(data.T)
    assert abs(corr[0, 1]) < 0.02  # X1, X2 independent
    assert abs(corr[0, 2]) > 0.1  # X3 depends on X1
    assert abs(corr[1, 2]) > 0.1  # X3 depends on X2
    assert abs(corr[0, 3]) < 0.02  # W independent of everything
    assert abs(corr[2, 3]) < 0.02


def test_sample_step2_control_third_column_is_a_plain_decoy():
    data = _sample_step2(50_000, 0.5, np.random.default_rng(2), collider=False)
    corr = np.corrcoef(data.T)
    assert abs(corr[0, 2]) < 0.02
    assert abs(corr[1, 2]) < 0.02


def test_expected_row_count_matches_the_full_grid():
    config = _config()
    assert expected_row_count(config) == len(FIXTURES) * 2 * 2 * 20
    combos = expected_combinations(config)
    assert ("step1", 300, 0.3, 0) in combos
    assert ("step2_control", 750, 0.5, 19) in combos


def test_run_stage8f_produces_one_row_per_expected_combination(tmp_path):
    config = _config()
    raw = run_stage8f(config, tmp_path / "out", write_report=False)
    assert set(zip(raw["fixture"], raw["n"], raw["strength"], raw["replicate"])) == expected_combinations(config)
    assert (raw["status"] == "ok").all()


def test_run_stage8f_is_deterministic_given_the_same_config_and_seed(tmp_path):
    config = _config()
    first = run_stage8f(config, tmp_path / "a", write_report=False)
    second = run_stage8f(config, tmp_path / "b", write_report=False)
    columns = [c for c in first.columns if c != "elapsed_seconds"]
    pd.testing.assert_frame_equal(first[columns], second[columns])


def test_step1_collider_conditioning_inflates_the_rejection_rate_above_nominal_alpha(tmp_path):
    """The core existence check H1 makes: at a reasonably large N and a
    real collider (strength=0.5), conditioning on the collider alone
    should reject independence far more often than the nominal alpha
    the test targets -- otherwise the whole diagnostic premise is moot."""
    config = _config(sample_sizes=(1000,), strengths=(0.5,), replicates=300, batch_size=300)
    raw = run_stage8f(config, tmp_path / "out", fixtures=("step1",), write_report=False)
    table = rejection_rate_table(raw)
    row = table.iloc[0]
    assert row["rejection_rate"] > row["mean_alpha"] + 0.2


def test_evaluate_h1_confirms_when_every_cell_shows_elevated_rejection():
    table = pd.DataFrame(
        [
            {"fixture": "step1", "n": 300, "strength": 0.5, "count": 500, "rejections": 400,
             "rejection_rate": 0.8, "ci_low": 0.76, "ci_high": 0.83, "mean_alpha": 0.05},
            {"fixture": "step1", "n": 750, "strength": 0.5, "count": 500, "rejections": 420,
             "rejection_rate": 0.84, "ci_low": 0.80, "ci_high": 0.87, "mean_alpha": 0.03},
        ]
    )
    verdict = evaluate_h1(table)
    assert verdict.status == "CONFIRMED"
    assert not verdict.cells_contradicting


def test_evaluate_h1_not_confirmed_when_a_cell_shows_no_elevation():
    table = pd.DataFrame(
        [
            {"fixture": "step1", "n": 300, "strength": 0.5, "count": 500, "rejections": 400,
             "rejection_rate": 0.8, "ci_low": 0.76, "ci_high": 0.83, "mean_alpha": 0.05},
            {"fixture": "step1", "n": 750, "strength": 0.5, "count": 500, "rejections": 20,
             "rejection_rate": 0.04, "ci_low": 0.02, "ci_high": 0.06, "mean_alpha": 0.03},
        ]
    )
    verdict = evaluate_h1(table)
    assert verdict.status == "NOT_CONFIRMED"


def test_evaluate_h1_inconclusive_below_min_count():
    table = pd.DataFrame(
        [{"fixture": "step1", "n": 300, "strength": 0.5, "count": 5, "rejections": 4,
          "rejection_rate": 0.8, "ci_low": 0.3, "ci_high": 0.98, "mean_alpha": 0.05}]
    )
    verdict = evaluate_h1(table, min_count=100)
    assert verdict.status == "INCONCLUSIVE"


def test_evaluate_h2_confirms_when_collider_rate_exceeds_control_at_every_cell():
    table = pd.DataFrame(
        [
            {"fixture": "step2_collider", "n": 300, "strength": 0.5, "count": 500,
             "rejection_rate": 0.85, "ci_low": 0.81, "ci_high": 0.88, "mean_alpha": 0.05},
            {"fixture": "step2_control", "n": 300, "strength": 0.5, "count": 500,
             "rejection_rate": 0.05, "ci_low": 0.03, "ci_high": 0.07, "mean_alpha": 0.05},
        ]
    )
    verdict = evaluate_h2(table)
    assert verdict.status == "CONFIRMED"


def test_evaluate_h2_not_confirmed_when_rates_overlap():
    table = pd.DataFrame(
        [
            {"fixture": "step2_collider", "n": 300, "strength": 0.5, "count": 500,
             "rejection_rate": 0.10, "ci_low": 0.07, "ci_high": 0.13, "mean_alpha": 0.05},
            {"fixture": "step2_control", "n": 300, "strength": 0.5, "count": 500,
             "rejection_rate": 0.06, "ci_low": 0.04, "ci_high": 0.09, "mean_alpha": 0.05},
        ]
    )
    verdict = evaluate_h2(table)
    assert verdict.status == "NOT_CONFIRMED"
