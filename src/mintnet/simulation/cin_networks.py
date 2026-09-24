"""Deterministic CIN simulation cases, exact truth, and cost inputs."""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SimulatedDataset:
    """A generated dataset with observed-variable truth and provenance."""

    frame: pd.DataFrame
    schema: dict[str, dict[str, Any]]
    truth_edges: frozenset[tuple[str, str]]
    population_cmi: dict[tuple[str, str], float] | None
    meta: dict[str, Any]


def _validate_joint(joint: np.ndarray) -> np.ndarray:
    values = np.asarray(joint, dtype=np.float64)
    if values.ndim < 2:
        raise ValueError("joint must have at least two axes")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("joint must contain finite nonnegative probabilities")
    total = float(values.sum())
    if not np.isclose(total, 1.0, atol=1e-12, rtol=0.0):
        raise ValueError("joint probabilities must sum to 1")
    return values


def exact_cmi_from_joint(joint: np.ndarray) -> dict[tuple[int, int], float]:
    """Return exact conditional mutual information for every unordered pair."""

    values = _validate_joint(joint)
    n_variables = values.ndim
    result: dict[tuple[int, int], float] = {}
    for left in range(n_variables):
        for right in range(left + 1, n_variables):
            pair = np.moveaxis(values, (left, right), (0, 1))
            p_left_rest = pair.sum(axis=1, keepdims=True)
            p_right_rest = pair.sum(axis=0, keepdims=True)
            p_rest = pair.sum(axis=(0, 1), keepdims=True)
            denominator = p_left_rest * p_right_rest
            ratio = np.zeros_like(pair)
            np.divide(pair * p_rest, denominator, out=ratio, where=denominator > 0)
            safe_ratio = np.where(pair > 0, ratio, 1.0)
            terms = np.where(pair > 0, pair * np.log(safe_ratio), 0.0)
            value = float(terms.sum())
            result[(left, right)] = max(0.0, value)
    return result


def gaussian_truth(
    omega: np.ndarray,
) -> tuple[frozenset[tuple[int, int]], dict[tuple[int, int], float]]:
    """Return precision support and Gaussian conditional MI for every pair."""

    matrix = np.asarray(omega, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("omega must be a square matrix")
    if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T):
        raise ValueError("omega must be finite and symmetric")
    if matrix.shape[0] < 2:
        raise ValueError("omega must contain at least two variables")
    try:
        np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError("omega must be positive definite") from exc

    truth: set[tuple[int, int]] = set()
    population_cmi: dict[tuple[int, int], float] = {}
    for left in range(matrix.shape[0]):
        if matrix[left, left] <= 0:
            raise ValueError("omega diagonal must be positive")
        for right in range(left + 1, matrix.shape[0]):
            if matrix[right, right] <= 0:
                raise ValueError("omega diagonal must be positive")
            rho = -matrix[left, right] / np.sqrt(matrix[left, left] * matrix[right, right])
            if not -1.0 < rho < 1.0:
                raise ValueError("omega implies an invalid partial correlation")
            population_cmi[(left, right)] = float(-0.5 * np.log1p(-(rho * rho)))
            if matrix[left, right] != 0.0:
                truth.add((left, right))
    return frozenset(truth), population_cmi


def is_connected(edges: Iterable[tuple[int, int]], p: int) -> bool:
    """Return whether an undirected integer graph is connected."""

    if isinstance(p, bool) or not isinstance(p, (int, np.integer)) or p < 1:
        raise ValueError("p must be a positive integer")
    adjacency = [[] for _ in range(int(p))]
    for left, right in edges:
        if not isinstance(left, (int, np.integer)) or not isinstance(right, (int, np.integer)):
            raise ValueError("graph vertices must be integers")
        if not 0 <= left < p or not 0 <= right < p or left == right:
            raise ValueError("graph edge contains an invalid vertex")
        adjacency[left].append(right)
        adjacency[right].append(left)

    seen = {0}
    queue: deque[int] = deque([0])
    while queue:
        vertex = queue.popleft()
        for neighbor in adjacency[vertex]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return len(seen) == p


def _quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"q50": None, "q90": None, "q95": None, "max": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "q50": float(np.quantile(array, 0.50)),
        "q90": float(np.quantile(array, 0.90)),
        "q95": float(np.quantile(array, 0.95)),
        "max": float(np.max(array)),
    }


def population_signal_summary(
    population_cmi: Mapping[tuple[Any, Any], float] | None,
    truth_edges: Collection[tuple[Any, Any]],
    *,
    threshold: float = 0.01,
    signal_proxy: Mapping[tuple[Any, Any], float] | None = None,
) -> dict[str, Any]:
    """Summarize available population signal without inventing unavailable CMI."""

    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("threshold must be finite and nonnegative")
    nodes = {node for pair in truth_edges for node in pair}
    if population_cmi is not None:
        nodes.update(node for pair in population_cmi for node in pair)
        cmi_values = [float(population_cmi[pair]) for pair in truth_edges]
        if any(not np.isfinite(value) or value < 0 for value in cmi_values):
            raise ValueError("population CMI must be finite and nonnegative")
        quantiles = _quantiles(cmi_values)
        strong_count: int | None = sum(value >= threshold for value in cmi_values)
    else:
        quantiles = {"q50": None, "q90": None, "q95": None, "max": None}
        strong_count = None

    n_nodes = len(nodes)
    possible_edges = n_nodes * (n_nodes - 1) // 2
    summary: dict[str, Any] = {
        "cmi_available": population_cmi is not None,
        "edge_count": len(truth_edges),
        "edge_density": float(len(truth_edges) / possible_edges) if possible_edges else 0.0,
        "cmi_q50": quantiles["q50"],
        "cmi_q90": quantiles["q90"],
        "cmi_q95": quantiles["q95"],
        "cmi_max": quantiles["max"],
        "strong_edge_count": strong_count,
        "proxy_available": signal_proxy is not None,
    }
    if signal_proxy is not None:
        proxy_values = [float(signal_proxy[pair]) for pair in truth_edges]
        if any(not np.isfinite(value) or value < 0 for value in proxy_values):
            raise ValueError("signal proxy must be finite and nonnegative")
        proxy_quantiles = _quantiles(proxy_values)
        summary.update(
            {
                "proxy_q50": proxy_quantiles["q50"],
                "proxy_q90": proxy_quantiles["q90"],
                "proxy_q95": proxy_quantiles["q95"],
                "proxy_max": proxy_quantiles["max"],
            }
        )
    return summary
