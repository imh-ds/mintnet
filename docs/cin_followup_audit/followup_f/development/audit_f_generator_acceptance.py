"""Replay preserved F failures and measure fresh development acceptance yield.

This script performs generator-only diagnostics. It does not fit CIN models,
alter the frozen validation artifacts, or treat the validation replays as new
validation evidence.
"""

from __future__ import annotations

import csv
import hashlib
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import xlogy

from mintnet.experiments.cin_baseline import CASE_ORDER
from mintnet.experiments.cin_common import derive_seed_bundle
from mintnet.simulation.cin_networks import (
    _finite_case_graph,
    _finite_states,
    exact_cmi_from_joint,
)


ROOT = Path(__file__).resolve().parents[4]
VALIDATION_RAW = ROOT / "docs/cin_followup_audit/followup_f/validation/candidate/raw_metrics.csv"
OUT_DIR = Path(__file__).resolve().parent
FLOOR = 0.005
DEVELOPMENT_MASTER_SEED = 20261003
DEVELOPMENT_REPLICATES = range(4000, 4100)
CAPS = (500, 1000, 2500)


def _entropy(probabilities: np.ndarray) -> float:
    values = np.asarray(probabilities, dtype=np.float64)
    return float(-xlogy(values, values).sum())


def _independent_pair_cmi(tensor: np.ndarray, left: int, right: int) -> float:
    """Calculate I(X_left; X_right | all remaining variables) by entropies."""
    pair = np.moveaxis(tensor, (left, right), (0, 1))
    return (
        _entropy(pair.sum(axis=1))
        + _entropy(pair.sum(axis=0))
        - _entropy(pair.sum(axis=(0, 1)))
        - _entropy(tensor)
    )


def _attempt(rng: np.random.Generator, states: np.ndarray):
    edges = _finite_case_graph(8, 10, rng)
    fields = rng.uniform(-0.5, 0.5, size=8)
    interactions = rng.uniform(0.6, 1.2, size=len(edges))
    logits = states @ fields
    for (left, right), interaction in zip(edges, interactions):
        logits += interaction * states[:, left] * states[:, right]
    probabilities = np.exp(logits - float(np.max(logits)))
    probabilities /= probabilities.sum()
    tensor = probabilities.reshape((2,) * 8)
    cmi = exact_cmi_from_joint(tensor)
    edge_values = [float(cmi[edge]) for edge in edges]
    return edges, tensor, edge_values


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty diagnostic output: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def replay_validation_failures() -> list[dict[str, object]]:
    raw = pd.read_csv(VALIDATION_RAW)
    failed = raw.loc[raw["status"].eq("error")].sort_values("replicate")
    states = _finite_states(2, 8)
    rows: list[dict[str, object]] = []
    for source in failed.itertuples(index=False):
        rng = np.random.default_rng(int(source.structure_seed))
        final_edges: list[tuple[int, int]] = []
        final_values: list[float] = []
        final_tensor: np.ndarray | None = None
        for _ in range(500):
            final_edges, final_tensor, final_values = _attempt(rng, states)
        assert final_tensor is not None
        independent = [
            _independent_pair_cmi(final_tensor, left, right)
            for left, right in final_edges
        ]
        errors = [abs(expected - observed) for expected, observed in zip(final_values, independent)]
        minimum_index = int(np.argmin(final_values))
        rows.append(
            {
                "replicate": int(source.replicate),
                "structure_seed": int(source.structure_seed),
                "sample_seed": int(source.sample_seed),
                "replayed_attempts": 500,
                "passing_draws_within_500": 0,
                "last_attempt_min_true_edge_cmi": min(final_values),
                "last_attempt_max_true_edge_cmi": max(final_values),
                "last_attempt_edges_below_floor": sum(value < FLOOR for value in final_values),
                "limiting_edge": f"V{final_edges[minimum_index][0]:02d}-V{final_edges[minimum_index][1]:02d}",
                "independent_min_true_edge_cmi": min(independent),
                "max_abs_cmi_difference": max(errors),
                "last_attempt_true_edge_cmis_json": "[" + ",".join(f"{v:.17g}" for v in final_values) + "]",
            }
        )
    return rows


def fresh_development_yield() -> list[dict[str, object]]:
    states = _finite_states(2, 8)
    rows: list[dict[str, object]] = []
    for replicate in DEVELOPMENT_REPLICATES:
        seeds = derive_seed_bundle(
            DEVELOPMENT_MASTER_SEED,
            CASE_ORDER.index("F"),
            0,
            replicate,
        )
        rng = np.random.default_rng(seeds.structure)
        first_accept: int | None = None
        last_minimum: float | None = None
        for attempt_number in range(1, max(CAPS) + 1):
            _, _, edge_values = _attempt(rng, states)
            last_minimum = min(edge_values)
            if last_minimum >= FLOOR:
                first_accept = attempt_number
                break
        rows.append(
            {
                "replicate": replicate,
                "structure_seed": seeds.structure,
                "sample_seed": seeds.sample,
                "attempts_observed": first_accept if first_accept is not None else max(CAPS),
                "first_accepting_attempt": first_accept if first_accept is not None else "",
                "accepted_by_500": first_accept is not None and first_accept <= 500,
                "accepted_by_1000": first_accept is not None and first_accept <= 1000,
                "accepted_by_2500": first_accept is not None and first_accept <= 2500,
                "last_observed_min_true_edge_cmi": last_minimum,
            }
        )
    return rows


def main() -> None:
    replay_rows = replay_validation_failures()
    development_rows = fresh_development_yield()
    _write_csv(OUT_DIR / "validation_failure_replay.csv", replay_rows)
    _write_csv(OUT_DIR / "fresh_development_acceptance.csv", development_rows)
    source_path = ROOT / "src/mintnet/simulation/cin_networks.py"
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    print(f"python={__import__('sys').version.split()[0]}")
    print(f"numpy={np.__version__}")
    print(f"scipy={__import__('scipy').__version__}")
    print(f"revision={revision}")
    print(f"generator_sha256={digest}")
    print(f"replay_rows={len(replay_rows)}")
    print(f"development_rows={len(development_rows)}")
    for cap in CAPS:
        accepted = sum(bool(row[f"accepted_by_{cap}"]) for row in development_rows)
        print(f"accepted_by_{cap}={accepted}/{len(development_rows)}")
    print(
        "max_abs_replay_cmi_difference="
        f"{max(float(row['max_abs_cmi_difference']) for row in replay_rows):.17g}"
    )


if __name__ == "__main__":
    main()
