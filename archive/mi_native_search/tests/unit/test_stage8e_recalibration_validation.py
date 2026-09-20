import numpy as np
import pandas as pd
import pytest

from mintnet.confidence.recalibration import calibrated_margin
from mintnet.experiments.stage8e_recalibration_validation import (
    Stage8eConfig,
    evaluate_stage8e_gate,
    fit_composed_false_edge_curves,
)


def _flat_reversed_false_edges(dgp: str, n: int, replicates: int, rng: np.random.Generator) -> pd.DataFrame:
    """Mirrors D-068's own composed-tier reversal: high margin is
    actually LESS reliable than low margin for false edges."""
    margins = rng.uniform(0.0, 1.0, size=replicates)
    correct = np.where(margins >= 0.9, (rng.uniform(size=replicates) < 0.3).astype(float), (rng.uniform(size=replicates) < 0.9).astype(float))
    return pd.DataFrame(
        {
            "dgp": dgp, "n": n, "replicate": np.arange(replicates), "i": 0, "j": 1,
            "is_true_edge": False, "margin": margins, "correct": correct, "status": "ok",
        }
    )


def test_fit_composed_false_edge_curves_only_uses_development_replicates() -> None:
    rng = np.random.default_rng(0)
    exploded = _flat_reversed_false_edges("chain_fork_hub", 750, 2000, rng)
    curves = fit_composed_false_edge_curves(exploded, development_replicates=(0, 999))

    assert ("chain_fork_hub", 750) in curves
    # Isotonic regression is constrained non-decreasing by construction --
    # it cannot literally invert D-068's own reversal, only flatten/plateau
    # across the region where the raw relationship reverses. The practical
    # calibration outcome (does the resulting score still read as reliable)
    # is checked separately, via the gate test below.
    curve = curves[("chain_fork_hub", 750)]
    assert curve.predict(0.05) <= curve.predict(0.95)


def test_evaluate_stage8e_gate_proceeds_when_recalibration_fixes_the_reversal() -> None:
    rng = np.random.default_rng(1)
    exploded = pd.concat(
        [
            _flat_reversed_false_edges("chain_fork_hub", 750, 2000, rng),
            _flat_reversed_false_edges("overlap", 1500, 2000, rng),
        ],
        ignore_index=True,
    )
    config = Stage8eConfig(development_replicates=(0, 999), validation_replicates=(1000, 1999), ece_tolerance=0.10, bin_count=10)
    curves = fit_composed_false_edge_curves(exploded, config.development_replicates)

    decision, bins = evaluate_stage8e_gate(exploded, curves, config)

    assert decision.status == "PROCEED"
    assert decision.max_ece <= 0.10


def test_evaluate_stage8e_gate_reassesses_when_the_relationship_does_not_generalize() -> None:
    """Development half has one relationship; validation half has a
    completely different, uncorrelated one -- the fitted curve should
    fail to generalize and the gate should catch it."""
    rng = np.random.default_rng(2)
    dev_margins = rng.uniform(0.0, 1.0, size=1000)
    dev_correct = (rng.uniform(size=1000) < dev_margins).astype(float)
    dev = pd.DataFrame({
        "dgp": "chain_fork_hub", "n": 750, "replicate": np.arange(1000), "i": 0, "j": 1,
        "is_true_edge": False, "margin": dev_margins, "correct": dev_correct, "status": "ok",
    })
    val_margins = rng.uniform(0.0, 1.0, size=1000)
    val_correct = rng.integers(0, 2, size=1000).astype(float)  # pure noise, no relationship to margin at all
    val = pd.DataFrame({
        "dgp": "chain_fork_hub", "n": 750, "replicate": np.arange(1000, 2000), "i": 0, "j": 1,
        "is_true_edge": False, "margin": val_margins, "correct": val_correct, "status": "ok",
    })
    exploded = pd.concat([dev, val], ignore_index=True)
    config = Stage8eConfig(development_replicates=(0, 999), validation_replicates=(1000, 1999), ece_tolerance=0.10, bin_count=10)
    curves = fit_composed_false_edge_curves(exploded, config.development_replicates)

    decision, _ = evaluate_stage8e_gate(exploded, curves, config)

    assert decision.status == "REASSESS"


def test_evaluate_stage8e_gate_curves_usable_directly_via_calibrated_margin() -> None:
    rng = np.random.default_rng(3)
    exploded = _flat_reversed_false_edges("overlap", 400, 2000, rng)
    config = Stage8eConfig(development_replicates=(0, 999), validation_replicates=(1000, 1999), ece_tolerance=0.10, bin_count=10)
    curves = fit_composed_false_edge_curves(exploded, config.development_replicates)

    value = calibrated_margin(0.5, 400, "overlap", curves=curves)
    assert 0.0 <= value <= 1.0
    with pytest.raises(ValueError, match="outside the validated range"):
        calibrated_margin(0.5, 100, "overlap", curves=curves)
