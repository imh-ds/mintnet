"""Fits the frozen alpha(N) candidate forms per docs/stage1j_charter.md.

Pure computation on the six already-validated (N, alpha) points from
D-008 through D-010 -- no simulation. This module is deterministic and
reproducible from those six points alone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# The six validated points (pair midpoints), frozen from
# docs/decision_log.md D-008, D-009, D-010.
FITTING_POINTS: tuple[tuple[float, float], ...] = (
    (700.0, 0.15),
    (750.0, 0.15),
    (1000.0, 0.13),
    (1500.0, 0.11),
    (2000.0, 0.09),
    (3000.0, 0.07),
)


@dataclass(frozen=True)
class FittedForm:
    name: str
    parameters: tuple[float, ...]
    r_squared: float
    n_parameters: int

    def predict(self, n: float) -> float:
        if self.name == "linear_n":
            a, b = self.parameters
            return a + b * n
        if self.name == "linear_log_n":
            a, b = self.parameters
            return a + b * math.log(n)
        if self.name == "power_law":
            a, b = self.parameters
            return a * n**b
        if self.name == "inverse_sqrt":
            a, b = self.parameters
            return a + b / math.sqrt(n)
        raise ValueError(f"unknown form: {self.name}")


def _r_squared(y: np.ndarray, y_hat: np.ndarray) -> float:
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - ss_res / ss_tot


def fit_candidate_forms(points: tuple[tuple[float, float], ...] = FITTING_POINTS) -> tuple[FittedForm, ...]:
    """Fit the four predeclared candidate forms via least squares."""
    n = np.array([p[0] for p in points], dtype=float)
    alpha = np.array([p[1] for p in points], dtype=float)

    linear_n = np.polyfit(n, alpha, 1)
    linear_n_form = FittedForm(
        "linear_n", (float(linear_n[1]), float(linear_n[0])), _r_squared(alpha, np.polyval(linear_n, n)), 2
    )

    linear_log_n = np.polyfit(np.log(n), alpha, 1)
    linear_log_n_form = FittedForm(
        "linear_log_n",
        (float(linear_log_n[1]), float(linear_log_n[0])),
        _r_squared(alpha, np.polyval(linear_log_n, np.log(n))),
        2,
    )

    power_law = np.polyfit(np.log(n), np.log(alpha), 1)
    power_law_form = FittedForm(
        "power_law",
        (float(math.exp(power_law[1])), float(power_law[0])),
        _r_squared(alpha, np.exp(np.polyval(power_law, np.log(n)))),
        2,
    )

    inverse_sqrt = np.polyfit(1.0 / np.sqrt(n), alpha, 1)
    inverse_sqrt_form = FittedForm(
        "inverse_sqrt",
        (float(inverse_sqrt[1]), float(inverse_sqrt[0])),
        _r_squared(alpha, np.polyval(inverse_sqrt, 1.0 / np.sqrt(n))),
        2,
    )

    return (linear_n_form, linear_log_n_form, power_law_form, inverse_sqrt_form)


def select_form(forms: tuple[FittedForm, ...]) -> FittedForm:
    """Select the best-fitting form, per docs/stage1j_charter.md's rule.

    Highest R^2 wins outright. If any form is within 0.005 R^2 of the
    best, prefer inverse_sqrt among the near-tied set (theoretical
    motivation from the mechanism's own Fisher-z sqrt(N-4) scaling);
    otherwise prefer the simplest (fewest-parameter) near-tied form.
    """
    best = max(forms, key=lambda form: form.r_squared)
    near_tied = tuple(form for form in forms if best.r_squared - form.r_squared <= 0.005)
    if len(near_tied) == 1:
        return best
    inverse_sqrt = next((form for form in near_tied if form.name == "inverse_sqrt"), None)
    if inverse_sqrt is not None:
        return inverse_sqrt
    return min(near_tied, key=lambda form: form.n_parameters)
