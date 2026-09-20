"""Public entry points for the forthcoming CIN estimator."""

from __future__ import annotations

from .config import CINConfig

__all__ = ["CINConfig", "estimate_stability", "fit_network", "make_view"]


def fit_network(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("CIN fitting is implemented in a later build task")


def estimate_stability(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("CIN stability is implemented in a later build task")


def make_view(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("CIN views are implemented in a later build task")
