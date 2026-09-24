"""Public entry points for the forthcoming CIN estimator."""

from __future__ import annotations

from .config import CINConfig
from .fit import fit_network
from .result import NetworkFit, load_fit
from .views import NetworkView, make_view

__all__ = [
    "CINConfig",
    "NetworkFit",
    "NetworkView",
    "estimate_stability",
    "fit_network",
    "load_fit",
    "make_view",
]


def estimate_stability(*args: object, **kwargs: object) -> None:
    raise NotImplementedError("CIN stability is implemented in a later build task")


