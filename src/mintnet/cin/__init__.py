"""Public entry points for the forthcoming CIN estimator."""

from __future__ import annotations

from .config import CINConfig
from .fit import fit_network
from .result import NetworkFit, load_fit
from .stability import StabilityResult, estimate_stability, load_stability, stability_for_rule
from .views import NetworkView, make_view

__all__ = [
    "CINConfig",
    "NetworkFit",
    "NetworkView",
    "StabilityResult",
    "estimate_stability",
    "fit_network",
    "load_fit",
    "load_stability",
    "make_view",
    "stability_for_rule",
]



