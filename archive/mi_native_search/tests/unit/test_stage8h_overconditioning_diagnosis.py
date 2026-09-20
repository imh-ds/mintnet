import numpy as np
import pandas as pd

from mintnet.experiments.stage8h_overconditioning_diagnosis import (
    DECOY_COUNTS,
    Stage8hConfig,
    _conditioning_for,
    _sample_fixture,
    expected_combinations,
    expected_row_count,
    run_stage8h,
)
from mintnet.experiments.stage8h_overconditioning_diagnosis_reporting import (
    evaluate_h4,
    evaluate_h5,
    rejection_rate_table,
)


def _config(**overrides) -> Stage8hConfig:
    values = dict(
        sample_sizes=(300, 750),
        strengths=(0.3, 0.7),
        replicates=20,
        batch_size=20,
        master_seed=1,
    )
    values.update(overrides)
    return Stage8hConfig(**values)


def test_conditioning_for_grows_from_the_correct_variable_alone():
    assert _conditioning_for(0) == (1,)
    assert _conditioning_for(1) == (1, 3)
    assert _conditioning_for(2) == (1, 3, 4)
    assert _conditioning_for(3) == (1, 3, 4, 5)


def test_sample_fixture_decoys_are_independent_of_the_chain_and_each_other():
    data = _sample_fixture(50_000, 0.5, np.random.default_rng(0))
    assert data.shape == (50_000, 6)
    corr = np.corrcoef(data.T)
    for decoy in (3, 4, 5):
        for chain_col in (0, 1, 2):
            assert abs(corr[decoy, chain_col]) < 0.02
    assert abs(corr[3, 4]) < 0.02
    assert abs(corr[3, 5]) < 0.02
    assert abs(corr[4, 5]) < 0.02


def test_sample_fixture_x1_x3_are_conditionally_independent_given_x2():
    """The fixture's own ground truth this whole charter rests on:
    X1 (col 0) and X3 (col 2) are exactly conditionally independent
    given X2 (col 1) alone, chain's own already-validated structure."""
    from mintnet.dpi.multi_conditional import compute_partial_correlation_evidence

    data = _sample_fixture(200_000, 0.5, np.random.default_rng(1))
    evidence = compute_partial_correlation_evidence(data, 0, 2, (1,))
    assert abs(evidence.partial_correlation) < 0.01


def test_expected_row_count_matches_the_full_grid():
    config = _config()
    assert expected_row_count(config) == len(DECOY_COUNTS) * 2 * 2 * 20
    combos = expected_combinations(config)
    assert (0, 300, 0.3, 0) in combos
    assert (3, 750, 0.7, 19) in combos


def test_run_stage8h_produces_one_row_per_expected_combination(tmp_path):
    config = _config()
    raw = run_stage8h(config, tmp_path / "out", write_report=False)
    assert set(zip(raw["decoy_count"], raw["n"], raw["strength"], raw["replicate"])) == expected_combinations(config)
    assert (raw["status"] == "ok").all()
    assert (raw["conditioning_size"] == raw["decoy_count"] + 1).all()


def test_run_stage8h_is_deterministic_given_the_same_config_and_seed(tmp_path):
    config = _config()
    first = run_stage8h(config, tmp_path / "a", write_report=False)
    second = run_stage8h(config, tmp_path / "b", write_report=False)
    columns = [c for c in first.columns if c != "elapsed_seconds"]
    pd.testing.assert_frame_equal(first[columns], second[columns])


def test_baseline_conditioning_on_x2_alone_tracks_nominal_alpha_closely(tmp_path):
    """Sanity check on the fixture's own calibration before testing any
    over-conditioning effect: decoy_count=0 (X2 alone, the already-
    validated correct blocker) must show a rejection rate close to
    nominal alpha(N), not already inflated by the fixture itself."""
    config = _config(sample_sizes=(1000,), strengths=(0.5,), replicates=300, batch_size=300)
    raw = run_stage8h(config, tmp_path / "out", decoy_counts=(0,), write_report=False)
    table = rejection_rate_table(raw)
    row = table.iloc[0]
    assert abs(row["rejection_rate"] - row["mean_alpha"]) < 0.05


def test_evaluate_h4_confirms_when_every_cell_shows_elevated_rejection_with_one_decoy():
    table = pd.DataFrame(
        [
            {"decoy_count": 0, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.15, "ci_low": 0.12, "ci_high": 0.18, "mean_alpha": 0.15},
            {"decoy_count": 1, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.45, "ci_low": 0.41, "ci_high": 0.49, "mean_alpha": 0.15},
        ]
    )
    verdict = evaluate_h4(table)
    assert verdict.status == "CONFIRMED"


def test_evaluate_h4_not_confirmed_when_rates_overlap():
    table = pd.DataFrame(
        [
            {"decoy_count": 0, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.15, "ci_low": 0.12, "ci_high": 0.18, "mean_alpha": 0.15},
            {"decoy_count": 1, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.16, "ci_low": 0.13, "ci_high": 0.19, "mean_alpha": 0.15},
        ]
    )
    verdict = evaluate_h4(table)
    assert verdict.status == "NOT_CONFIRMED"


def test_evaluate_h4_inconclusive_below_min_count():
    table = pd.DataFrame(
        [
            {"decoy_count": 0, "n": 300, "strength": 0.5, "count": 5, "rejection_rate": 0.15, "ci_low": 0.02, "ci_high": 0.5, "mean_alpha": 0.15},
            {"decoy_count": 1, "n": 300, "strength": 0.5, "count": 5, "rejection_rate": 0.45, "ci_low": 0.1, "ci_high": 0.8, "mean_alpha": 0.15},
        ]
    )
    verdict = evaluate_h4(table, min_count=100)
    assert verdict.status == "INCONCLUSIVE"


def test_evaluate_h5_confirms_saturation_when_larger_decoy_counts_do_not_climb_further():
    table = pd.DataFrame(
        [
            {"decoy_count": 1, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.80, "ci_low": 0.76, "ci_high": 0.83},
            {"decoy_count": 2, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.82, "ci_low": 0.78, "ci_high": 0.85},
            {"decoy_count": 3, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.79, "ci_low": 0.75, "ci_high": 0.82},
        ]
    )
    verdict = evaluate_h5(table)
    assert verdict.status == "CONFIRMED"


def test_evaluate_h5_not_confirmed_when_rejection_rate_keeps_climbing():
    table = pd.DataFrame(
        [
            {"decoy_count": 1, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.40, "ci_low": 0.36, "ci_high": 0.44},
            {"decoy_count": 2, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.60, "ci_low": 0.56, "ci_high": 0.64},
            {"decoy_count": 3, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.80, "ci_low": 0.76, "ci_high": 0.83},
        ]
    )
    verdict = evaluate_h5(table)
    assert verdict.status == "NOT_CONFIRMED"


def test_evaluate_h5_inconclusive_when_larger_decoy_counts_are_missing():
    table = pd.DataFrame(
        [{"decoy_count": 1, "n": 300, "strength": 0.5, "count": 500, "rejection_rate": 0.40, "ci_low": 0.36, "ci_high": 0.44}]
    )
    verdict = evaluate_h5(table)
    assert verdict.status == "INCONCLUSIVE"
