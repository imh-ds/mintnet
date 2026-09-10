"""Deterministic raw-evidence runner for the frozen Stage 7f frontier-
mapping charter (Part A). See docs/stage7f_charter.md.

Mirrors `mintnet.experiments.stage7_isolation`'s own chain/fork/triangle
structure and `stage7b_frontier`'s own "compute once, threshold many
times" design, with two changes: (1) the structured-density engine
(`mintnet.pipeline.growing_subset_dpi_structured_density`, D-063's own
`degree=1` operating setting) is used in place of CMIknn, so this run
also exercises Part B's own new `decisive_p_value`/`confidence` fields;
(2) since every candidate pair in a 3-node motif has exactly one
possible conditioning set, `decisive_p_value` is provably alpha-
independent here -- one call per replicate (at an arbitrary fixed
`alpha`, ignored downstream) yields the decisive p-value for all three
pairs, and BOTH the retain/prune decision at any alpha AND the
confidence score at any alpha are re-derived entirely at reporting
time by re-thresholding/re-applying `edge_margin` to this same stored
evidence -- zero additional significance-test cost either way.

Real per-replicate cost measured directly under GitHub Actions' own
thread limits (`OMP_NUM_THREADS=2` etc., this session's own repeated
lesson from D-078/D-080): `9s`-`13s` per replicate (one `growing_
subset_dpi_structured_density` call, `degree=1`, `permutations=199`),
consistent across chain/triangle and `N in {400, 750, 1500}` -- not
assumed to transfer from D-062's own different-machine measurement.
`replicates=400` per cell at this cost is `~60-90` minutes per shard,
comfortably under GitHub Actions' 6-hour job timeout, so `batch_size`
is set equal to `replicates` (one shard per `(condition, N)` cell, no
sub-batching): `11 conditions x 7 N = 77` shards total, well under the
256-job matrix cap -- unlike a `batch_size=50` split, which would have
produced `616` shards and overflowed it.
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

from mintnet.pipeline.growing_subset_dpi_structured_density import growing_subset_dpi_structured_density
from mintnet.simulation import sample_chain, sample_measured_fork
from mintnet.simulation.motifs import sample_weak_edge_triangle

MOTIFS: tuple[str, ...] = ("chain", "fork", "triangle")
# "chain_0".."chain_2" (config.strengths), "fork_0".."fork_2" (config.
# strengths), "triangle_0".."triangle_4" (config.target_rhos) -- an
# uneven per-motif index count, unlike stage7_isolation's own uniform
# 3-per-motif scheme, since the triangle side needs finer effect-size
# resolution than chain/fork's own null does.
_TRIANGLE_INDEX_COUNT = 5


def _conditions(config: "Stage7fConfig") -> tuple[str, ...]:
    return (
        tuple(f"chain_{i}" for i in range(len(config.strengths)))
        + tuple(f"fork_{i}" for i in range(len(config.strengths)))
        + tuple(f"triangle_{i}" for i in range(len(config.target_rhos)))
    )


def _parse_condition(condition: str) -> tuple[str, int]:
    motif, index = condition.rsplit("_", 1)
    return motif, int(index)


@dataclass(frozen=True)
class Stage7fConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    target_rhos: tuple[float, ...]
    degree: int
    ridge_lambda: float
    cv_folds: int
    k_perm: int
    permutations: int
    replicates: int
    batch_size: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage7fConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7f configuration must be a mapping")
    return Stage7fConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        target_rhos=_values(values, "target_rhos", float),
        degree=int(values["degree"]),
        ridge_lambda=float(values["ridge_lambda"]),
        cv_folds=int(values["cv_folds"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("condition", "n", "replicate")


def _n_batches(config: Stage7fConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7fConfig) -> set[tuple[str, int, int]]:
    return {
        (condition, n, replicate)
        for condition in _conditions(config)
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage7fConfig) -> int:
    return len(expected_combinations(config))


def _sample_motif(motif: str, index: int, n: int, config: Stage7fConfig, rng: np.random.Generator) -> np.ndarray:
    if motif == "chain":
        return sample_chain(n, config.strengths[index], rng)
    if motif == "fork":
        return sample_measured_fork(n, config.strengths[index], rng)
    return sample_weak_edge_triangle(config.target_rhos[index], n, rng)


def _condition_seed(master_seed: int, motif_index: int, index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, motif_index, index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


_PLACEHOLDER_ALPHA = 0.5  # decisive_p_value is alpha-independent here (pool size 1); any value works


def _run_one_replicate(condition: str, n: int, replicate: int, config: Stage7fConfig) -> dict[str, object]:
    motif, index = _parse_condition(condition)
    motif_index = MOTIFS.index(motif)
    sample_index = config.sample_sizes.index(n)
    seed = _condition_seed(config.master_seed, motif_index, index, sample_index, replicate)

    row: dict[str, object] = {
        "condition": condition, "motif": motif, "index": index, "n": n, "replicate": replicate, "seed": seed,
        "decisive_p_value_01": np.nan, "decisive_p_value_02": np.nan, "decisive_p_value_12": np.nan,
        "n_significance_tests": np.nan, "elapsed_seconds": np.nan, "status": "ok", "error": "",
    }
    started = time.perf_counter()
    try:
        data = _sample_motif(motif, index, n, config, np.random.default_rng(seed))
        flagged = np.ones((3, 3), dtype=bool)
        np.fill_diagonal(flagged, False)
        result = growing_subset_dpi_structured_density(
            data, flagged, _PLACEHOLDER_ALPHA, master_seed=config.master_seed, replicate=replicate,
            degree=config.degree, ridge_lambda=config.ridge_lambda, cv_folds=config.cv_folds,
            k_perm=config.k_perm, permutations=config.permutations,
        )
        row["decisive_p_value_01"] = result.decisive_p_value[(0, 1)]
        row["decisive_p_value_02"] = result.decisive_p_value[(0, 2)]
        row["decisive_p_value_12"] = result.decisive_p_value[(1, 2)]
        row["n_significance_tests"] = result.n_significance_tests
    except Exception as exc:  # raw evidence must retain sampling/estimation failures
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["elapsed_seconds"] = time.perf_counter() - started
    return row


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
    "condition", "motif", "index", "n", "replicate", "seed",
    "decisive_p_value_01", "decisive_p_value_02", "decisive_p_value_12",
    "n_significance_tests", "elapsed_seconds", "status", "error",
)


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7fConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "sample_sizes": list(config.sample_sizes), "strengths": list(config.strengths),
        "target_rhos": list(config.target_rhos), "degree": config.degree, "ridge_lambda": config.ridge_lambda,
        "cv_folds": config.cv_folds, "k_perm": config.k_perm, "permutations": config.permutations,
        "replicates": config.replicates, "batch_size": config.batch_size, "master_seed": config.master_seed,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7f_charter.md"
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


def run_stage7f(
    config: Stage7fConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- replicate ranges are always derived
    from `config.batch_size` against the FULL replicate count, and
    seeds key off full-grid quantities only, so a shard's results match
    an unsharded run's for the same replicates."""
    started = time.perf_counter()
    target_conditions = conditions if conditions is not None else _conditions(config)
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        for n in target_sizes:
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.append(_run_one_replicate(condition, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7f_frontier_reporting import write_report as write_stage7f_report

    write_stage7f_report(raw, config, output_dir)
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

    run_stage7f(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
