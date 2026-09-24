"""Public entry points for the forthcoming CIN estimator."""

from __future__ import annotations

from .config import CINConfig
from .fit import fit_network
from .result import NetworkFit

__all__ = ["CINConfig", "NetworkFit", "estimate_stability", "fit_network", "make_view"]


def estimate_stability(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("CIN stability is implemented in a later build task")


def make_view(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("CIN views are implemented in a later build task")
