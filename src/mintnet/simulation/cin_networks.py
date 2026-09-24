"""Deterministic CIN simulation cases, exact truth, and cost inputs."""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd


_GAUSSIAN_CASES = {
    "A": {"n": 100, "p": 8},
    "B": {"n": 200, "p": 30},
    "C": {"n": 150, "p": 100},
}


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


def _validate_seed(seed: int, field_name: str) -> int:
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError(f"{field_name} must be a nonnegative integer")
    return int(seed)


def _validate_sample_size(n: int, default: int | None = None) -> int:
    value = default if n is None else n
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError("n must be a positive integer")
    return int(value)


def _node_names(p: int) -> tuple[str, ...]:
    return tuple(f"V{index:02d}" for index in range(p))


def _all_pairs(p: int) -> list[tuple[int, int]]:
    return [(left, right) for left in range(p) for right in range(left + 1, p)]


def _spanning_tree_from_parent_draws(p: int, rng: np.random.Generator) -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = []
    for vertex in range(1, p):
        parent = int(rng.integers(0, vertex))
        edges.append((parent, vertex))
    return edges


def _add_edges(
    edges: list[tuple[int, int]],
    candidates: list[tuple[int, int]],
    count: int,
    rng: np.random.Generator,
) -> None:
    existing = set(edges)
    available = [edge for edge in candidates if edge not in existing]
    if count < 0 or count > len(available):
        raise ValueError("requested edge count exceeds available candidates")
    if count:
        order = rng.permutation(len(available))[:count]
        edges.extend(available[int(index)] for index in order)


def _case_edges(case: str, rng: np.random.Generator) -> list[tuple[int, int]]:
    if case == "A":
        edges = _spanning_tree_from_parent_draws(8, rng)
        _add_edges(edges, _all_pairs(8), 2, rng)
        return edges
    if case == "B":
        p = 30
        edges = _spanning_tree_from_parent_draws(p, rng)
        target = round(0.25 * (p * (p - 1) // 2))
        _add_edges(edges, _all_pairs(p), target - len(edges), rng)
        return edges
    if case == "C":
        edges: list[tuple[int, int]] = []
        community = list(range(25))
        remainder = list(range(25, 100))
        community_candidates = [(left, right) for left in community for right in community if left < right]
        remainder_candidates = [(left, right) for left in remainder for right in remainder if left < right]
        edges.extend(_spanning_tree_from_parent_draws(len(community), rng))
        _add_edges(edges, community_candidates, round(0.50 * len(community_candidates)) - len(edges), rng)
        remainder_edges = _spanning_tree_from_parent_draws(len(remainder), rng)
        edges.extend((left + 25, right + 25) for left, right in remainder_edges)
        _add_edges(
            edges,
            remainder_candidates,
            round(0.03 * len(remainder_candidates)) - len(remainder_edges),
            rng,
        )
        cross_candidates = [(left, right) for left in community for right in remainder]
        _add_edges(edges, cross_candidates, 30, rng)
        return edges
    raise ValueError(f"unknown Gaussian case: {case}")


def _signed_weights(
    count: int,
    rng: np.random.Generator,
    *,
    low: float,
    high: float,
) -> np.ndarray:
    magnitudes = rng.uniform(low, high, size=count)
    signs = np.where(rng.integers(0, 2, size=count) == 0, -1.0, 1.0)
    return magnitudes * signs


def _mixture_weights(count: int, rng: np.random.Generator) -> np.ndarray:
    high_mask = rng.random(count) < 0.30
    magnitudes = np.where(
        high_mask,
        rng.uniform(1.0, 1.8, size=count),
        rng.uniform(0.3, 0.8, size=count),
    )
    signs = np.where(rng.integers(0, 2, size=count) == 0, -1.0, 1.0)
    return magnitudes * signs


def _structure_digest(omega: np.ndarray) -> str:
    payload = json.dumps(
        {
            "shape": list(omega.shape),
            "values": np.asarray(omega, dtype="<f8").tolist(),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _gaussian_structure(
    case: str, structure_seed: int
) -> tuple[np.ndarray, dict[str, Any]]:
    base_case = "B" if case == "D" else case
    if base_case not in _GAUSSIAN_CASES:
        raise ValueError(f"unknown Gaussian case: {case}")
    rng = np.random.default_rng(_validate_seed(structure_seed, "structure_seed"))
    p = _GAUSSIAN_CASES[base_case]["p"]
    edges = _case_edges(base_case, rng)
    if base_case == "A":
        weights = _signed_weights(len(edges), rng, low=0.6, high=1.2)
    else:
        weights = _mixture_weights(len(edges), rng)
    adjacency = np.zeros((p, p), dtype=np.float64)
    for (left, right), weight in zip(edges, weights):
        adjacency[left, right] = weight
        adjacency[right, left] = weight
    scale = 0.8 / float(np.linalg.norm(adjacency, ord=2))
    omega = np.eye(p, dtype=np.float64) + scale * adjacency
    np.linalg.cholesky(omega)
    minimum_eigenvalue = float(np.linalg.eigvalsh(omega)[0])
    if minimum_eigenvalue < 0.19:
        raise RuntimeError("Gaussian precision matrix missed the positive-definite margin")
    edge_density = len(edges) / (p * (p - 1) / 2)
    meta = {
        "base_case": base_case,
        "edges": [list(edge) for edge in edges],
        "weights": weights.tolist(),
        "min_eigenvalue": minimum_eigenvalue,
        "edge_density": float(edge_density),
        "structure_digest": _structure_digest(omega),
    }
    return omega, meta


def _sample_gaussian_precision(omega: np.ndarray, sample_seed: int, n: int) -> np.ndarray:
    covariance = np.linalg.inv(omega)
    rng = np.random.default_rng(_validate_seed(sample_seed, "sample_seed"))
    return rng.multivariate_normal(np.zeros(omega.shape[0]), covariance, size=n)


def _named_gaussian_result(
    case: str,
    *,
    structure_seed: int,
    sample_seed: int,
    n: int | None,
) -> SimulatedDataset:
    default_n = _GAUSSIAN_CASES[case]["n"]
    sample_size = _validate_sample_size(n, default_n)
    omega, structure_meta = _gaussian_structure(case, structure_seed)
    data = _sample_gaussian_precision(omega, sample_seed, sample_size)
    names = _node_names(omega.shape[0])
    truth_indices, cmi_indices = gaussian_truth(omega)
    truth_edges = frozenset((names[left], names[right]) for left, right in truth_indices)
    population_cmi = {
        (names[left], names[right]): value for (left, right), value in cmi_indices.items()
    }
    summary = population_signal_summary(population_cmi, truth_edges)
    meta = {
        **structure_meta,
        "case": case,
        "structure_seed": int(structure_seed),
        "sample_seed": int(sample_seed),
        "n": sample_size,
        "p": omega.shape[0],
        "rejection_tries": 0,
        "population_signal_summary": summary,
    }
    schema = {name: {"kind": "continuous"} for name in names}
    return SimulatedDataset(
        frame=pd.DataFrame(data, index=pd.RangeIndex(sample_size), columns=names),
        schema=schema,
        truth_edges=truth_edges,
        population_cmi=population_cmi,
        meta=meta,
    )


def generate_case(
    case: str,
    *,
    structure_seed: int,
    sample_seed: int,
    n: int | None = None,
) -> SimulatedDataset:
    """Generate one deterministic CIN evaluation case."""

    if case in _GAUSSIAN_CASES:
        return _named_gaussian_result(
            case,
            structure_seed=structure_seed,
            sample_seed=sample_seed,
            n=n,
        )
    if case == "D":
        base = _named_gaussian_result(
            "B",
            structure_seed=structure_seed,
            sample_seed=sample_seed,
            n=n,
        )
        frame = base.frame.copy()
        frame.iloc[:, ::2] = np.sinh(0.5 * frame.iloc[:, ::2])
        meta = {**base.meta, "case": "D", "paired_case": "B"}
        return SimulatedDataset(
            frame=frame,
            schema=base.schema,
            truth_edges=base.truth_edges,
            population_cmi=base.population_cmi,
            meta=meta,
        )
    raise ValueError(f"unknown CIN simulation case: {case}")


__all__ = [
    "SimulatedDataset",
    "exact_cmi_from_joint",
    "gaussian_truth",
    "generate_case",
    "is_connected",
    "population_signal_summary",
]
