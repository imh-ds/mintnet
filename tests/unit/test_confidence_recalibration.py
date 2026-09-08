import numpy as np
import pandas as pd
import pytest

from mintnet.confidence.recalibration import (
    IsotonicCurve,
    calibrated_margin,
    evaluate_recalibrated_ece,
    fit_calibration_curves,
    fit_isotonic_curve,
    load_curves,
    save_curves,
)


def test_isotonic_curve_predict_matches_fitted_points_and_interpolates_between() -> None:
    curve = IsotonicCurve(x_thresholds=(0.0, 0.5, 1.0), y_values=(0.1, 0.5, 0.9))
    assert curve.predict(0.0) == pytest.approx(0.1)
    assert curve.predict(0.5) == pytest.approx(0.5)
    assert curve.predict(0.25) == pytest.approx(0.3)


def test_fit_isotonic_curve_recovers_a_strong_margin_accuracy_relationship() -> None:
    rng = np.random.default_rng(0)
    margins = rng.uniform(0.0, 1.0, size=2000)
    correct = (rng.uniform(size=2000) < margins).astype(float)

    curve = fit_isotonic_curve(margins, correct)

    assert curve.predict(0.05) < curve.predict(0.5) < curve.predict(0.95)
    assert curve.predict(0.05) < 0.3
    assert curve.predict(0.95) > 0.7


def _synthetic_raw(motif_family: str, n: int, replicates: int, rng: np.random.Generator) -> pd.DataFrame:
    margins = rng.uniform(0.0, 1.0, size=replicates)
    correct = (rng.uniform(size=replicates) < margins).astype(float)
    return pd.DataFrame(
        {
            "condition": f"{motif_family}_0.5",
            "n": n,
            "replicate": np.arange(replicates),
            "margin": margins,
            "correct": correct,
            "status": "ok",
        }
    )


def test_fit_calibration_curves_only_uses_development_replicates() -> None:
    rng = np.random.default_rng(1)
    raw = _synthetic_raw("chain", 750, 1000, rng)
    # Corrupt the validation half so a curve fit on it would look very different.
    raw.loc[raw["replicate"] >= 500, "correct"] = 1.0 - raw.loc[raw["replicate"] >= 500, "correct"]

    curves = fit_calibration_curves(raw, development_replicates=(0, 499))

    dev_only = raw.loc[raw["replicate"] < 500]
    expected = fit_isotonic_curve(dev_only["margin"].to_numpy(), dev_only["correct"].to_numpy())
    assert curves[("chain", 750)].x_thresholds == expected.x_thresholds
    assert curves[("chain", 750)].y_values == expected.y_values


def test_fit_calibration_curves_excludes_error_rows_and_nan_margins() -> None:
    rng = np.random.default_rng(2)
    raw = _synthetic_raw("fork", 300, 100, rng)
    raw.loc[0, "status"] = "error"
    raw.loc[1, "margin"] = np.nan

    curves = fit_calibration_curves(raw, development_replicates=(0, 99))
    assert ("fork", 300) in curves  # still fits from the remaining 98 valid rows


def test_calibrated_margin_snaps_to_nearest_tested_n() -> None:
    curves = {
        ("chain", 300): IsotonicCurve(x_thresholds=(0.0, 1.0), y_values=(0.2, 0.2)),
        ("chain", 3000): IsotonicCurve(x_thresholds=(0.0, 1.0), y_values=(0.9, 0.9)),
    }
    # 1000 is closer to 300 than to 3000? No -- closer to neither exactly,
    # but nearest by absolute distance: |1000-300|=700, |1000-3000|=2000.
    assert calibrated_margin(0.5, 1000, "chain", curves) == pytest.approx(0.2)
    assert calibrated_margin(0.5, 2900, "chain", curves) == pytest.approx(0.9)


def test_calibrated_margin_raises_outside_tested_range() -> None:
    curves = {("chain", 300): IsotonicCurve(x_thresholds=(0.0, 1.0), y_values=(0.2, 0.2))}
    with pytest.raises(ValueError, match="outside the validated range"):
        calibrated_margin(0.5, 100, "chain", curves)
    with pytest.raises(ValueError, match="outside the validated range"):
        calibrated_margin(0.5, 5000, "chain", curves)


def test_calibrated_margin_raises_for_unknown_motif_family() -> None:
    with pytest.raises(ValueError, match="no fitted calibration curve"):
        calibrated_margin(0.5, 300, "nonexistent_motif", {})


def test_evaluate_recalibrated_ece_only_uses_validation_replicates() -> None:
    rng = np.random.default_rng(3)
    raw = _synthetic_raw("chain", 750, 1000, rng)
    curves = fit_calibration_curves(raw, development_replicates=(0, 499))

    bins = evaluate_recalibrated_ece(raw, curves, validation_replicates=(500, 999), bin_count=10)
    assert set(bins["n"]) == {750}
    assert set(bins["motif"]) == {"chain"}
    assert bins["count"].sum() == 500


def test_save_and_load_curves_round_trip() -> None:
    curves = {
        ("chain", 300): IsotonicCurve(x_thresholds=(0.0, 0.5, 1.0), y_values=(0.1, 0.4, 0.9)),
        ("triangle", 3000): IsotonicCurve(x_thresholds=(0.0, 1.0), y_values=(0.95, 0.999)),
    }
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "curves.json"
        save_curves(curves, path)
        loaded = load_curves(path)

    assert loaded == curves


def test_default_curves_merges_isolated_and_composed_fitted_artifacts() -> None:
    from mintnet.confidence.recalibration import default_curves

    curves = default_curves()
    families = {family for family, _ in curves}
    # D-067's own isolated fixtures and D-070's own composed-tier fixtures
    # are disjoint-keyed artifacts merged into one default lookup.
    assert {"chain", "fork", "triangle", "weak_edge_triangle"} <= families
    assert {"chain_fork_hub", "overlap"} <= families
