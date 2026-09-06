"""Deterministic raw-evidence runner for Stage 7e's own up-front
calibration-transfer check. See docs/stage7e_charter.md.

Before Stage 7e's own main run commits to `degree=1` (D-062's best
performer on `weak_edge_triangle`), this checks whether that
calibration actually transfers onto Stage 7's own real isolation-tier
fixtures (chain/fork/triangle), rather than assuming it does. Sweeps
`degree in {1, 2, 3}` (D-062's own finding that higher degrees add no
benefit on linear/curvature data justifies not re-testing `4`) against
all 9 conditions from `mintnet.experiments.stage7e_conditions` (chain
and fork at 3 strengths each, both testing their own genuine null pair
`(0, 2) | 1`; triangle at 3 families, testing all three real pairs as
a descriptive, non-gating power check).

Resolved design, per this session's own direct timing measurement (a
single significance test at `degree` in `{1, 3}`, on `chain`, at each
`N`): `1.9s`-`2.9s` per test -- comparable to Stage 7d's own
per-replicate costs. `replicates=200` (half Stage 7c/7d's own `R=400`
-- this is a preliminary transfer check, not the charter's own main
evidence, and does not need that precision to decide whether to
proceed with `degree=1`). `batch_size=200` (a single batch: even the
worst case, a `triangle` condition's own 3 pairs at `degree=3`/
`N=1500`, costs well under an hour per shard). `(degree, condition)`
combined into one composite shard label (`3 x 9 = 27` combinations)
crossed with `N` (`2`): `27 x 2 = 54` shards, well under the 256-job
matrix cap.
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

from mintnet.experiments.stage7e_conditions import all_conditions, condition_pairs, sample_condition
from mintnet.mi.structured_density import local_permutation_test


@dataclass(frozen=True)
class Stage7eCalibrationTransferConfig:
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


def load_config(path: Path) -> Stage7eCalibrationTransferConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7e calibration-transfer configuration must be a mapping")
    return Stage7eCalibrationTransferConfig(
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


def shard_label(degree: int, condition: str) -> str:
    return f"deg{degree}__{condition}"


def _parse_shard_label(label: str) -> tuple[int, str]:
    degree_part, condition = label.split("__", 1)
    return int(degree_part[3:]), condition


def all_shard_labels(config: Stage7eCalibrationTransferConfig) -> tuple[str, ...]:
    return tuple(shard_label(degree, condition) for degree in config.degrees for condition in all_conditions())


def _pair_label(pair: tuple[int, int]) -> str:
    return f"{pair[0]}-{pair[1]}"


COMBINATION_COLUMNS: tuple[str, ...] = ("degree", "condition", "n", "replicate", "pair")


def _n_batches(config: Stage7eCalibrationTransferConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7eCalibrationTransferConfig) -> set[tuple[int, str, int, int, str]]:
    return {
        (degree, condition, n, replicate, _pair_label(pair))
        for degree in config.degrees
        for condition in all_conditions()
        for pair in condition_pairs(condition)
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage7eCalibrationTransferConfig) -> int:
    return len(expected_combinations(config))


def _replicate_seed(master_seed: int, degree_index: int, condition_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, degree_index, condition_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    degree: int, condition: str, n: int, replicate: int, config: Stage7eCalibrationTransferConfig
) -> list[dict[str, object]]:
    degree_index = config.degrees.index(degree)
    condition_index = all_conditions().index(condition)
    sample_index = config.sample_sizes.index(n)
    seed = _replicate_seed(config.master_seed, degree_index, condition_index, sample_index, replicate)

    rows: list[dict[str, object]] = []
    try:
        data = sample_condition(condition, n, np.random.default_rng(seed))
    except Exception as exc:  # sampling failure -> one error row per expected pair
        for pair in condition_pairs(condition):
            rows.append(
                {
                    "degree": degree, "condition": condition, "n": n, "replicate": replicate, "pair": _pair_label(pair),
                    "seed": seed, "status": "error", "error": f"{type(exc).__name__}: {exc}",
                    "cmi": np.nan, "p_value": np.nan, "elapsed_seconds": np.nan,
                }
            )
        return rows

    for i, j in condition_pairs(condition):
        (k,) = {0, 1, 2} - {i, j}
        row: dict[str, object] = {
            "degree": degree, "condition": condition, "n": n, "replicate": replicate, "pair": _pair_label((i, j)),
            "seed": seed, "status": "ok", "error": "", "cmi": np.nan, "p_value": np.nan, "elapsed_seconds": np.nan,
        }
        started = time.perf_counter()
        try:
            sequence = np.random.SeedSequence(
                [config.master_seed, degree_index, condition_index, sample_index, replicate, i, j]
            )
            rng = np.random.default_rng(int(sequence.generate_state(1)[0]))
            result = local_permutation_test(
                data[:, i], data[:, j], data[:, k], degree=degree, ridge_lambda=config.ridge_lambda,
                cv_folds=config.cv_folds, k_perm=config.k_perm, permutations=config.permutations, rng=rng,
            )
            row["cmi"] = float(result.statistic)
            row["p_value"] = float(result.p_value)
        except Exception as exc:  # raw evidence must retain estimation failures
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        row["elapsed_seconds"] = time.perf_counter() - started
        rows.append(row)
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


_COLUMNS = ("degree", "condition", "n", "replicate", "pair", "seed", "status", "error", "cmi", "p_value", "elapsed_seconds")


def _write_evidence(
    output_dir: Path, raw: pd.DataFrame, config: Stage7eCalibrationTransferConfig, runtime_seconds: float
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


def run_stage7e_calibration_transfer(
    config: Stage7eCalibrationTransferConfig,
    output_dir: Path,
    shard_labels: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`shard_labels`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- `shard_labels` are
    `shard_label(degree, condition)` strings. Replicate ranges are
    derived from `config.batch_size` against the full replicate count,
    and seeds key off full-grid indices, so a shard's results match an
    unsharded run's."""
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
                    rows.extend(_run_one_replicate(degree, condition, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7e_calibration_transfer_reporting import write_report as write_stage7e_report

    write_stage7e_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--shard-labels", type=str, default=None,
        help="comma-separated subset of shard labels (e.g. deg1__chain_0.3; default: all)",
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

    run_stage7e_calibration_transfer(
        load_config(arguments.config), arguments.output,
        shard_labels=shard_labels, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
