"""Shared DGP-condition definitions for Stage 7d's two evidence
runners (the structured-density estimator's own degree sweep, and the
CMIknn baseline re-run) -- factored out so both runners parse and
sample conditions identically, a prerequisite for a fair head-to-head
comparison built from two otherwise-independent runs. See
docs/stage7d_charter.md.

Three DGP families, matching the charter's own required conditions:

- `linear`: `sample_weak_edge_triangle` -- includes `target_rho=0.0`,
  the shared null used by the structured-density side's own Stage A
  calibration filter.
- `curvature`: `sample_monotonic_curvature_triangle` -- the mild,
  matched-population-MI monotonic nonlinearity condition. Does not
  repeat `target_rho=0.0` (independence there is the same population
  claim as `linear`'s own null, since a monotonic transform of one
  variable cannot create or destroy independence).
- `ushape`: `sample_ushape_triangle` -- the mandatory diagnostic
  condition, including its own `curvature=0.0` null (a *distinct*
  generative construction from `linear`'s null, worth its own check).
"""

from __future__ import annotations

import numpy as np

from mintnet.simulation.motifs import (
    sample_monotonic_curvature_triangle,
    sample_ushape_triangle,
    sample_weak_edge_triangle,
)

LINEAR_RHOS: tuple[float, ...] = (0.0, 0.08, 0.12, 0.15, 0.20)
CURVATURE_RHOS: tuple[float, ...] = (0.08, 0.12, 0.15, 0.20)
USHAPE_CURVATURES: tuple[float, ...] = (0.0, 0.3, 0.45, 0.6)


def condition_label(family: str, param: float) -> str:
    return f"{family}_{param}"


def parse_condition(condition: str) -> tuple[str, float]:
    family, _, param = condition.rpartition("_")
    if not family:
        raise ValueError(f"malformed condition label: {condition!r}")
    return family, float(param)


def all_conditions() -> tuple[str, ...]:
    labels = [condition_label("linear", rho) for rho in LINEAR_RHOS]
    labels += [condition_label("curvature", rho) for rho in CURVATURE_RHOS]
    labels += [condition_label("ushape", c) for c in USHAPE_CURVATURES]
    return tuple(labels)


def sample_condition(condition: str, n: int, rng: np.random.Generator) -> np.ndarray:
    family, param = parse_condition(condition)
    if family == "linear":
        return sample_weak_edge_triangle(param, n, rng)
    if family == "curvature":
        return sample_monotonic_curvature_triangle(param, n, rng)
    if family == "ushape":
        return sample_ushape_triangle(param, n, rng)
    raise ValueError(f"unknown condition family: {family!r}")
