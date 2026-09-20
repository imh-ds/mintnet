"""Deterministic raw-evidence runner for the frozen Stage 7d structured
conditional-density estimator sweep. See docs/stage7d_charter.md.

Sweeps `degree` (basis complexity; `ridge_lambda`, `cv_folds`, `k_perm`
held fixed at the estimator's own defaults) against all 13 DGP
conditions from `mintnet.experiments.stage7d_conditions` (5 linear +
4 curvature + 4 U-shape), computing only the weak/test-edge `(1, 2)`
pair per replicate -- the two dominant edges' own near-certain
retention is not in question here, mirroring Stage 7c's own disclosed
scope reduction.

Resolved design, per this session's own direct timing measurement (a
single 3-pair evidence computation, `degree` in `{1, 2, 4}`, at each
`N`): worst case `degree=4`/`N=3000` costs ~11.4s per replicate --
roughly 10-15x cheaper than CMIknn's own equivalent (~185s at
`k_CMI=80`/`N=3000`), since this estimator fits regularized regressions
rather than running kNN queries. `replicates=400` (Stage 7b/7c
precedent), `batch_size=400` (a single batch: even the worst-case cell,
400 x 11.4s ~= 1.27h, is safely under GitHub Actions' 6-hour job
timeout with wide margin, so no further batching is needed).
`(degree, condition)` combined into one composite shard label (4 x 13 =
52 combinations) crossed with `N` (3): `52 x 3 = 156` shards, under the
256-job matrix cap -- a single dispatch.
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

from mintnet.experiments.stage7d_conditions import all_conditions, parse_condition, sample_condition
from mintnet.mi.structured_density import local_permutation_test


@dataclass(frozen=True)
class Stage7dStructuredDensityConfig:
    degrees: tuple[int, ...]
    sample_sizes: tuple[int, ...]
    replicates: int
    batch_size: int
    ridge_lambda: float
    cv_folds: int
    k_perm: int
    permutations: int
    master_seed: int
    source_path: Path | None = None


def load_config(path: Path) -> Stage7dStructuredDensityConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7d structured-density configuration must be a mapping")
    return Stage7dStructuredDensityConfig(
        degrees=tuple(int(v) for v in values["degrees"]),
        sample_sizes=tuple(int(v) for v in values["sample_sizes"]),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        ridge_lambda=float(values["ridge_lambda"]),
        cv_folds=int(values["cv_folds"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


def condition_label(degree: int, condition: str) -> str:
    return f"deg{degree}__{condition}"


def _parse_shard_label(label: str) -> tuple[int, str]:
    degree_part, condition = label.split("__", 1)
    return int(degree_part[3:]), condition


def all_shard_labels(config: Stage7dStructuredDensityConfig) -> tuple[str, ...]:
    return tuple(condition_label(degree, condition) for degree in config.degrees for condition in all_conditions())


COMBINATION_COLUMNS: tuple[str, ...] = ("degree", "condition", "n", "replicate")


def _n_batches(config: Stage7dStructuredDensityConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7dStructuredDensityConfig) -> set[tuple[int, str, int, int]]:
    return {
        (degree, condition, n, replicate)
        for degree in config.degrees
        for condition in all_conditions()
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage7dStructuredDensityConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(master_seed: int, degree_index: int, condition_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, degree_index, condition_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    degree: int, condition: str, n: int, replicate: int, config: Stage7dStructuredDensityConfig
) -> dict[str, object]:
    degree_index = config.degrees.index(degree)
    condition_index = all_conditions().index(condition)
    sample_index = config.sample_sizes.index(n)
    seed = _condition_seed(config.master_seed, degree_index, condition_index, sample_index, replicate)

    row: dict[str, object] = {
        "degree": degree, "condition": condition, "n": n, "replicate": replicate, "seed": seed,
        "status": "ok", "error": "", "cmi_12": np.nan, "p_value_12": np.nan, "elapsed_seconds": np.nan,
    }
    started = time.perf_counter()
    try:
        data = sample_condition(condition, n, np.random.default_rng(seed))
        x, y, z = data[:, 1], data[:, 2], data[:, 0]
        sequence = np.random.SeedSequence([config.master_seed, degree_index, condition_index, sample_index, replicate])
        rng = np.random.default_rng(int(sequence.generate_state(1)[0]))
        result = local_permutation_test(
            x, y, z, degree=degree, ridge_lambda=config.ridge_lambda, cv_folds=config.cv_folds,
            k_perm=config.k_perm, permutations=config.permutations, rng=rng,
        )
        row["cmi_12"] = float(result.statistic)
        row["p_value_12"] = float(result.p_value)
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


_COLUMNS = ("degree", "condition", "n", "replicate", "seed", "status", "error", "cmi_12", "p_value_12", "elapsed_seconds")


def _write_evidence(
    output_dir: Path, raw: pd.DataFrame, config: Stage7dStructuredDensityConfig, runtime_seconds: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "degrees": list(config.degrees), "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates, "batch_size": config.batch_size,
        "ridge_lambda": config.ridge_lambda, "cv_folds": config.cv_folds,
        "k_perm": config.k_perm, "permutations": config.permutations, "master_seed": config.master_seed,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7d_charter.md"
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


def run_stage7d_structured_density(
    config: Stage7dStructuredDensityConfig,
    output_dir: Path,
    shard_labels: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`shard_labels`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- `shard_labels` are
    `condition_label(degree, condition)` strings. Replicate ranges are
    derived from `config.batch_size` against the full replicate count,
    and seeds key off full-grid indices (`config.degrees.index(...)`,
    `all_conditions().index(...)`, `config.sample_sizes.index(...)`,
    `replicate`), so a shard's results match an unsharded run's."""
    started = time.perf_counter()
    target_labels = shard_labels if shard_labels is not None else all_shard_labels(config)
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for label in target_labels:
        degree, condition = _parse_shard_label(label)
        for n in target_sizes:
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.append(_run_one_replicate(degree, condition, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7d_structured_density_reporting import write_report as write_stage7d_report

    write_stage7d_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--shard-labels", type=str, default=None,
        help="comma-separated subset of shard labels (e.g. deg2__linear_0.08; default: all)",
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--batches", type=str, default=None, help="comma-separated subset of batch indices (default: all)"
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    shard_labels = tuple(arguments.shard_labels.split(",")) if arguments.shard_labels else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    batches = tuple(int(v) for v in arguments.batches.split(",")) if arguments.batches else None

    run_stage7d_structured_density(
        load_config(arguments.config), arguments.output,
        shard_labels=shard_labels, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
