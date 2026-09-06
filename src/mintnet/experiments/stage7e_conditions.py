"""Shared DGP-condition definitions for Stage 7e's calibration-transfer
check. See docs/stage7e_charter.md.

Two condition kinds, both drawn directly from Stage 7's own isolation-
tier fixtures (not re-derived from Stage 7d's `weak_edge_triangle`
family, since the whole point of this check is to test transfer onto
the *actual* gate fixtures):

- `chain`/`fork`, one per strength `{.3,.5,.7}`: each has exactly one
  genuine null pair -- `(0, 2) | 1` -- the indirect edge a correctly
  calibrated test must NOT reject at the nominal rate. This is the
  decisive calibration-filter check.
- `triangle`, one per family `{balanced,moderate,strong}`: no null
  pair exists (all three edges are real dependencies), so this is a
  descriptive power check, not a Type-I check -- included because the
  charter's own calibration-transfer section asks for "the triangle
  families' own null-adjacent behavior" as supplementary context for
  choosing `degree`, not as a pass/fail criterion.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from mintnet.simulation.motifs import sample_chain, sample_measured_fork, sample_precision_triangle

CHAIN_FORK_STRENGTHS: tuple[float, ...] = (0.3, 0.5, 0.7)
TRIANGLE_FAMILIES: tuple[str, ...] = ("balanced", "moderate", "strong")


def condition_label(motif: str, param: float | str) -> str:
    return f"{motif}_{param}"


def parse_condition(condition: str) -> tuple[str, str]:
    motif, _, param = condition.partition("_")
    if not motif or not param:
        raise ValueError(f"malformed condition label: {condition!r}")
    return motif, param


def all_conditions() -> tuple[str, ...]:
    labels = [condition_label("chain", s) for s in CHAIN_FORK_STRENGTHS]
    labels += [condition_label("fork", s) for s in CHAIN_FORK_STRENGTHS]
    labels += [condition_label("triangle", f) for f in TRIANGLE_FAMILIES]
    return tuple(labels)


def condition_pairs(condition: str) -> tuple[tuple[int, int], ...]:
    """The `(i, j)` column pairs to test for this condition -- for
    `chain`/`fork`, only the one genuine null pair `(0, 2)`; for
    `triangle`, all three pairs (no null pair exists)."""
    motif, _ = parse_condition(condition)
    if motif in ("chain", "fork"):
        return ((0, 2),)
    if motif == "triangle":
        return tuple(combinations(range(3), 2))
    raise ValueError(f"unknown condition motif: {motif!r}")


def sample_condition(condition: str, n: int, rng: np.random.Generator) -> np.ndarray:
    motif, param = parse_condition(condition)
    if motif == "chain":
        return sample_chain(n, float(param), rng)
    if motif == "fork":
        return sample_measured_fork(n, float(param), rng)
    if motif == "triangle":
        return sample_precision_triangle(param, n, rng)
    raise ValueError(f"unknown condition motif: {motif!r}")
