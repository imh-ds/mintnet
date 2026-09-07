"""Confidence diagnostics for DPI edge decisions. See docs/stage8a_charter.md."""

from .margin import edge_margin, edge_margins
from .recalibration import (
    IsotonicCurve,
    calibrated_margin,
    evaluate_recalibrated_ece,
    fit_calibration_curves,
    fit_isotonic_curve,
    load_curves,
    save_curves,
)

__all__ = [
    "edge_margin",
    "edge_margins",
    "IsotonicCurve",
    "calibrated_margin",
    "evaluate_recalibrated_ece",
    "fit_calibration_curves",
    "fit_isotonic_curve",
    "load_curves",
    "save_curves",
]
