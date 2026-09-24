"""Audit the frozen CIN simulation population properties."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mintnet.simulation import (  # noqa: E402
    ORGANIC_NETWORK_TRUE_EDGES,
    generate_case,
    generate_cost_input,
    gaussian_truth,
    is_connected,
    sample_organic_network,
)
from mintnet.simulation.cin_networks import _gaussian_structure  # noqa: E402


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _case_record(case: str, structure_seed: int, sample_seed: int) -> dict[str, Any]:
    result = generate_case(case, structure_seed=structure_seed, sample_seed=sample_seed)
    summary = result.meta["population_signal_summary"]
    return {
        "case": case,
        "p": result.meta["p"],
        "n": result.meta["n"],
        "edge_count": len(result.truth_edges),
        "density": summary["edge_density"],
        "cmi_available": summary["cmi_available"],
        "cmi_q50": summary["cmi_q50"],
        "cmi_q90": summary["cmi_q90"],
        "cmi_q95": summary["cmi_q95"],
        "cmi_max": summary["cmi_max"],
        "strong_edge_count": summary["strong_edge_count"],
        "rejection_tries": result.meta["rejection_tries"],
        "structure_seed": structure_seed,
        "sample_seed": sample_seed,
    }


def _gaussian_population_audit(structure_seed: int) -> list[dict[str, Any]]:
    bounds = {"A": (9 / 28, 9 / 28), "B": (0.24, 0.26), "C": (0.05, 0.06)}
    records: list[dict[str, Any]] = []
    for case, (lower, upper) in bounds.items():
        for offset in range(200):
            omega, meta = _gaussian_structure(case, structure_seed + offset)
            eigenvalues = np.linalg.eigvalsh(omega)
            np.linalg.cholesky(omega)
            truth, _ = gaussian_truth(omega)
            expected = frozenset(tuple(edge) for edge in meta["edges"])
            density = len(expected) / (omega.shape[0] * (omega.shape[0] - 1) / 2)
            _require(float(eigenvalues[0]) >= 0.19, f"{case} lost its eigenvalue floor")
            _require(is_connected(meta["edges"], omega.shape[0]), f"{case} is disconnected")
            _require(truth == expected, f"{case} precision support changed")
            _require(lower <= density <= upper, f"{case} density {density} is out of bounds")
        records.append(
            {
                "case": case,
                "replicates": 200,
                "density_bounds": [lower, upper],
                "minimum_eigenvalue_floor": 0.19,
                "passed": True,
            }
        )
    return records


def _categorical_frequency_audit(
    structure_seed: int, sample_seed: int
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in ("F", "G"):
        result = generate_case(
            case,
            structure_seed=structure_seed,
            sample_seed=sample_seed,
            n=100_000,
        )
        levels = tuple(len(spec["levels"]) for spec in result.schema.values())
        codes = result.frame.to_numpy(dtype=int)
        flat = np.ravel_multi_index(codes.T, dims=levels)
        observed = np.bincount(flat, minlength=int(np.prod(levels))).astype(float)
        expected = np.asarray(result.meta["joint_tensor"], dtype=float).ravel() * len(codes)
        positive = expected > 0.0
        chi_square = float(np.sum((observed[positive] - expected[positive]) ** 2 / expected[positive]))
        degrees_of_freedom = int(positive.sum() - 1)
        max_frequency_error = float(
            np.max(np.abs(observed / len(codes) - expected / len(codes)))
        )
        threshold = degrees_of_freedom + 6.0 * np.sqrt(2.0 * degrees_of_freedom)
        passed = chi_square <= threshold and max_frequency_error <= 0.02
        _require(passed, f"{case} exact-joint frequency check failed")
        records.append(
            {
                "case": case,
                "n": len(codes),
                "chi_square": chi_square,
                "degrees_of_freedom": degrees_of_freedom,
                "chi_square_threshold": threshold,
                "max_frequency_error": max_frequency_error,
                "passed": passed,
            }
        )
    return records


def _pairing_audit(structure_seed: int, sample_seed: int) -> dict[str, Any]:
    base = generate_case("B", structure_seed=structure_seed, sample_seed=sample_seed)
    transformed = generate_case("D", structure_seed=structure_seed, sample_seed=sample_seed)
    _require(base.truth_edges == transformed.truth_edges, "B/D truth differs")
    _require(base.population_cmi == transformed.population_cmi, "B/D population CMI differs")
    _require(base.meta["structure_digest"] == transformed.meta["structure_digest"], "B/D structure differs")
    for column in range(base.frame.shape[1]):
        if column % 2 == 0:
            expected = np.sinh(0.5 * base.frame.iloc[:, column].to_numpy())
        else:
            expected = base.frame.iloc[:, column].to_numpy()
        np.testing.assert_array_equal(transformed.frame.iloc[:, column].to_numpy(), expected)
    return {"same_structure": True, "same_draw": True, "passed": True}


def _organic_smoke_audit(sample_seed: int) -> dict[str, Any]:
    data = sample_organic_network(300, np.random.default_rng(sample_seed))
    _require(data.shape == (300, 14), "organic smoke dimensions changed")
    return {
        "n": data.shape[0],
        "p": data.shape[1],
        "edge_count": len(ORGANIC_NETWORK_TRUE_EDGES),
        "passed": True,
    }


def _frame_digest(frame: Any, schema: dict[str, dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    hasher.update(np.asarray(frame.index, dtype=np.int64).tobytes())
    for name in frame.columns:
        values = frame[name].to_numpy()
        hasher.update(name.encode("utf-8"))
        hasher.update(np.asarray(values).tobytes(order="C"))
    hasher.update(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return hasher.hexdigest()


def _cost_audit(sample_seed: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for kind in ("dense_continuous", "categorical5", "categorical10", "mixed"):
        frame, schema = generate_cost_input(kind, 12, 512, seed=sample_seed)
        repeat_frame, repeat_schema = generate_cost_input(kind, 12, 512, seed=sample_seed)
        digest = _frame_digest(frame, schema)
        _require(digest == _frame_digest(repeat_frame, repeat_schema), f"{kind} is not deterministic")
        kind_counts = {
            "continuous": sum(spec["kind"] == "continuous" for spec in schema.values()),
            "categorical": sum(spec["kind"] == "categorical" for spec in schema.values()),
        }
        records.append(
            {
                "kind": kind,
                "shape": list(frame.shape),
                "schema_kind_counts": kind_counts,
                "digest": digest,
                "truth_declared": False,
            }
        )
    return records


def build_report(structure_seed: int, sample_seed: int) -> dict[str, Any]:
    return {
        "seeds": {"structure_seed": structure_seed, "sample_seed": sample_seed},
        "cases": [_case_record(case, structure_seed, sample_seed) for case in "ABCDEFGHI"],
        "gaussian_population_checks": _gaussian_population_audit(structure_seed),
        "categorical_frequency_checks": _categorical_frequency_audit(structure_seed, sample_seed),
        "pairing": _pairing_audit(structure_seed, sample_seed),
        "organic_smoke": _organic_smoke_audit(sample_seed),
        "cost_inputs": _cost_audit(sample_seed),
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--structure-seed", type=int, default=17)
    parser.add_argument("--sample-seed", type=int, default=23)
    args = parser.parse_args()
    report = build_report(args.structure_seed, args.sample_seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
