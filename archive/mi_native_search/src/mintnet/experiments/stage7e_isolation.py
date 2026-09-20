"""Deterministic raw-evidence runner for the frozen Stage 7e isolation-
tier evidence run -- the falsification core of docs/stage7e_charter.md's
own PROCEED/REASSESS gate, retrying Stage 7's own gate (docs/
stage7_charter.md) with the structured conditional-density estimator
in place of CMIknn. Mirrors `mintnet.experiments.stage7_isolation.py`'s
own structure and DGPs (chain, measured fork, triangle balanced/
moderate/strong) exactly, substituting `mintnet.dpi.
structured_density_conditional` (D-063's own `degree=1` default) for
`mintnet.dpi.cmi_conditional`.

Since every candidate pair in a 3-node motif has exactly one possible
conditioning set (the remaining column),
`compute_structured_density_conditional_independence_evidence` computes
each pair's CMI/p-value ONCE per replicate and this runner sweeps the
full `alphas` grid by re-thresholding that same evidence -- identical
"compute once, threshold many times" structure to Stage 7's own.

Resolved design, per this session's own direct timing measurement
(a full 3-pair evidence computation at `degree=1`, on `chain` and
`triangle_strong`, at each `N`): `10s`-`16s` per replicate under
today's actual machine load -- notably higher than the `~7s`-`11s`
range measured for Stage 7d's own evidence run, a reminder that this
project's own timing measurements reflect real, variable machine
conditions, not a fixed per-call cost, and are re-measured rather than
assumed each time for exactly this reason. Even the worst case,
`R=500` in a single batch at `N=1500` (`500 x 16s ~= 2.2h`), is safely
under GitHub Actions' 6-hour job timeout, so `batch_size=500` (a single
batch) is used -- `9 conditions x 2 N x 1 batch = 18` shards, a real
reduction from Stage 7's own CMIknn-based run (`90` shards at
`batch_size=100`), disclosed here as a genuine, cost-driven design
difference rather than an arbitrary one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mintnet.dpi.structured_density_conditional import (
    compute_structured_density_conditional_independence_evidence,
    prune_structured_density_conditional_independence,
)
from mintnet.metrics import score_motif
from mintnet.simulation import sample_chain, sample_measured_fork, sample_precision_triangle

MOTIFS: tuple[str, ...] = ("chain", "fork", "triangle")
# (motif, strength_index) pairs, matching Stage 1b/Stage 7's own
# strength/triangle_families index pairing -- strength_index selects
# config.strengths[i] for chain/fork, or config.triangle_families[i]
# for triangle.
CONDITIONS: tuple[str, ...] = tuple(f"{motif}_{i}" for motif in MOTIFS for i in range(3))


def _parse_condition(condition: str) -> tuple[str, int]:
    motif, index = condition.rsplit("_", 1)
    return motif, int(index)


@dataclass(frozen=True)
class Stage7eIsolationConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    triangle_families: tuple[str, ...]
    alphas: tuple[float, ...]
    replicates: int
    batch_size: int
    degree: int
    ridge_lambda: float
    cv_folds: int
    k_perm: int
    permutations: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_triangle_true_edge_prune_fpr: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float] | type[str]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage7eIsolationConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7e isolation configuration must be a mapping")
    config = Stage7eIsolationConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        triangle_families=_values(values, "triangle_families", str),
        alphas=_values(values, "alphas", float),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        degree=int(values["degree"]),
        ridge_lambda=float(values["ridge_lambda"]),
        cv_folds=int(values["cv_folds"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_triangle_true_edge_prune_fpr=float(values["maximum_triangle_true_edge_prune_fpr"]),
        source_path=path.resolve(),
    )
    if len(config.strengths) != 3 or len(config.triangle_families) != 3:
        raise ValueError("strengths and triangle_families must each have exactly 3 entries")
    return config


COMBINATION_COLUMNS: tuple[str, ...] = ("motif", "strength_index", "n", "replicate", "alpha")


def _n_batches(config: Stage7eIsolationConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7eIsolationConfig) -> set[tuple[str, int, int, int, float]]:
    return {
        (motif, strength_index, n, replicate, alpha)
        for motif in MOTIFS
        for strength_index in range(3)
        for n in config.sample_sizes
        for replicate in range(config.replicates)
        for alpha in config.alphas
    }


def expected_row_count(config: Stage7eIsolationConfig) -> int:
    return len(expected_combinations(config))


def _sample_motif(motif: str, family: str, n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    if motif == "chain":
        return sample_chain(n, strength, rng)
    if motif == "fork":
        return sample_measured_fork(n, strength, rng)
    return sample_precision_triangle(family, n, rng)


def _condition_seed(master_seed: int, motif_index: int, sample_index: int, strength_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, motif_index, sample_index, strength_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    motif: str, strength_index: int, n: int, replicate: int, config: Stage7eIsolationConfig
) -> list[dict[str, object]]:
    motif_index = MOTIFS.index(motif)
    sample_index = config.sample_sizes.index(n)
    strength = config.strengths[strength_index]
    family = "gaussian" if motif != "triangle" else config.triangle_families[strength_index]
    seed = _condition_seed(config.master_seed, motif_index, sample_index, strength_index, replicate)

    started = time.perf_counter()
    try:
        data = _sample_motif(motif, family, n, strength, np.random.default_rng(seed))
        evidence = compute_structured_density_conditional_independence_evidence(
            data,
            seed_context=(config.master_seed, motif_index, sample_index, strength_index, replicate),
            degree=config.degree, ridge_lambda=config.ridge_lambda, cv_folds=config.cv_folds,
            k_perm=config.k_perm, permutations=config.permutations,
        )
        status, error = "ok", ""
    except Exception as exc:  # raw evidence must retain sampling/estimation failures
        data = None
        evidence = None
        status, error = "error", f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    rows: list[dict[str, object]] = []
    for alpha in config.alphas:
        metrics = {"indirect_prune_tpr": np.nan, "true_edge_prune_fpr": np.nan, "perfect_recovery": np.nan}
        cmi_01 = cmi_02 = cmi_12 = np.nan
        p_value_01 = p_value_02 = p_value_12 = np.nan
        retained_01 = retained_02 = retained_12 = np.nan
        row_status, row_error = status, error
        if evidence is not None:
            try:
                adjacency = prune_structured_density_conditional_independence(evidence, alpha)
                metrics = score_motif(adjacency, motif)
                retained_01, retained_02, retained_12 = bool(adjacency[0, 1]), bool(adjacency[0, 2]), bool(adjacency[1, 2])
                cmi_01, cmi_02, cmi_12 = float(evidence.cmi[0, 1]), float(evidence.cmi[0, 2]), float(evidence.cmi[1, 2])
                p_value_01 = float(evidence.p_value[0, 1])
                p_value_02 = float(evidence.p_value[0, 2])
                p_value_12 = float(evidence.p_value[1, 2])
            except Exception as exc:  # retain pruning/scoring failures by alpha
                row_status = "error"
                row_error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "motif": motif, "family": family, "strength_index": strength_index, "strength": strength,
                "n": n, "alpha": alpha, "replicate": replicate, "seed": seed,
                "retained_01": retained_01, "retained_02": retained_02, "retained_12": retained_12,
                "cmi_01": cmi_01, "cmi_02": cmi_02, "cmi_12": cmi_12,
                "p_value_01": p_value_01, "p_value_02": p_value_02, "p_value_12": p_value_12,
                "confidence_01": (1.0 - p_value_01) if row_status == "ok" else np.nan,
                "confidence_02": (1.0 - p_value_02) if row_status == "ok" else np.nan,
                "confidence_12": (1.0 - p_value_12) if row_status == "ok" else np.nan,
                **metrics,
                "elapsed_seconds": elapsed,
                "status": row_status, "error": row_error,
            }
        )
    return rows


def _repository_root(source_path: Path | None) -> Path:
    if source_path is not None:
        return source_path.resolve().parent.parent
    return Path(__file__).resolve().parents[3]


def _git_commit(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


_COLUMNS = (
    "motif", "family", "strength_index", "strength", "n", "alpha", "replicate", "seed",
    "retained_01", "retained_02", "retained_12", "cmi_01", "cmi_02", "cmi_12",
    "p_value_01", "p_value_02", "p_value_12", "confidence_01", "confidence_02", "confidence_12",
    "indirect_prune_tpr", "true_edge_prune_fpr", "perfect_recovery", "elapsed_seconds", "status", "error",
)


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7eIsolationConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "sample_sizes": list(config.sample_sizes), "strengths": list(config.strengths),
        "triangle_families": list(config.triangle_families), "alphas": list(config.alphas),
        "replicates": config.replicates, "batch_size": config.batch_size,
        "degree": config.degree, "ridge_lambda": config.ridge_lambda, "cv_folds": config.cv_folds,
        "k_perm": config.k_perm, "permutations": config.permutations, "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_triangle_true_edge_prune_fpr": config.maximum_triangle_true_edge_prune_fpr,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7e_charter.md"
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    metadata = {
        "charter_sha256": charter_hash,
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def run_stage7e_isolation(
    config: Stage7eIsolationConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- replicate ranges are always derived
    from `config.batch_size` against the FULL replicate count, and
    seeds key off `MOTIFS.index(...)`/`config.sample_sizes.index(...)`/
    `strength_index`/`replicate` (all full-grid quantities), so a
    shard's results match an unsharded run's for the same replicates."""
    started = time.perf_counter()
    target_conditions = conditions if conditions is not None else CONDITIONS
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        motif, strength_index = _parse_condition(condition)
        for n in target_sizes:
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.extend(_run_one_replicate(motif, strength_index, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7e_isolation_reporting import write_report as write_stage7e_report

    write_stage7e_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None,
        help="comma-separated subset of conditions (e.g. chain_0,triangle_2; default: all)",
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--batches", type=str, default=None, help="comma-separated subset of batch indices (default: all)"
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    conditions = tuple(arguments.conditions.split(",")) if arguments.conditions else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    batches = tuple(int(v) for v in arguments.batches.split(",")) if arguments.batches else None

    run_stage7e_isolation(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
