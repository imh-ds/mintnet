"""Shared DGP-condition definitions for Stage 8a's Tier-0 confidence-
score calibration check. See docs/stage8a_charter.md.

Reuses this project's own already-chartered fixtures unchanged, so any
calibration claim this charter produces is scoped to conditions the
project can already stand behind independently: chain/fork (indirect
edge to prune), the three named triangle families (all edges genuine,
including the historically weak one), and a continuous target_rho
sweep on `weak_edge_triangle` -- including `target_rho=0.0`, a genuine
null for the (1, 2) pair, giving margin scores a continuous range of
"should be pruned" difficulty too, not just "should be retained."
"""

from __future__ import annotations

import numpy as np

from mintnet.simulation.motifs import (
    sample_chain,
    sample_measured_fork,
    sample_precision_triangle,
    sample_weak_edge_triangle,
)

CHAIN_FORK_STRENGTHS: tuple[float, ...] = (0.3, 0.5, 0.7)
TRIANGLE_FAMILIES: tuple[str, ...] = ("balanced", "moderate", "strong")
WEAK_EDGE_RHOS: tuple[float, ...] = (0.0, 0.08, 0.12, 0.15, 0.20)


def condition_label(family: str, param: float | str) -> str:
    return f"{family}_{param}"


def parse_condition(condition: str) -> tuple[str, str]:
    family, _, param = condition.rpartition("_")
    if not family:
        raise ValueError(f"malformed condition label: {condition!r}")
    return family, param


def all_conditions() -> tuple[str, ...]:
    labels = [condition_label("chain", s) for s in CHAIN_FORK_STRENGTHS]
    labels += [condition_label("fork", s) for s in CHAIN_FORK_STRENGTHS]
    labels += [condition_label("triangle", f) for f in TRIANGLE_FAMILIES]
    labels += [condition_label("weak_edge_triangle", r) for r in WEAK_EDGE_RHOS]
    return tuple(labels)


def true_edges_for(condition: str) -> dict[tuple[int, int], bool]:
    """Ground-truth ((i, j) -> should this edge survive) for a condition."""
    family, param = parse_condition(condition)
    if family in ("chain", "fork"):
        return {(0, 1): True, (0, 2): False, (1, 2): True}
    if family == "triangle":
        return {(0, 1): True, (0, 2): True, (1, 2): True}
    if family == "weak_edge_triangle":
        return {(0, 1): True, (0, 2): True, (1, 2): float(param) != 0.0}
    raise ValueError(f"unknown condition family: {family!r}")


def sample_condition(condition: str, n: int, rng: np.random.Generator) -> np.ndarray:
    family, param = parse_condition(condition)
    if family == "chain":
        return sample_chain(n, float(param), rng)
    if family == "fork":
        return sample_measured_fork(n, float(param), rng)
    if family == "triangle":
        return sample_precision_triangle(param, n, rng)
    if family == "weak_edge_triangle":
        return sample_weak_edge_triangle(float(param), n, rng)
    raise ValueError(f"unknown condition family: {family!r}")
