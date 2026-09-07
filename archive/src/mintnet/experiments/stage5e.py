"""Deterministic raw-evidence runner for the frozen Stage 5e PC-algorithm
skeleton comparison. See docs/stage5e_charter.md.

Runs only the new PC-stable skeleton comparator
(`mintnet.comparators.pc_skeleton.fit_pc_skeleton`) -- MINT and
EBICglasso are not re-run here; their numbers are D-047's own,
referenced in the report, not regenerated. This charter reuses Stage
5a's own DGP registry, full grid, and exact condition-seed derivation
(`stage5a._condition_seed`, unchanged `_STAGE_TAG`/`master_seed`) so
every `(dgp, N, replicate)` cell draws the identical simulated dataset
D-047 was computed on -- a paired comparison, not merely a comparable
one.
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
from typing import Callable

import numpy as np
import pandas as pd
import yaml

from mintnet.comparators.pc_skeleton import fit_pc_skeleton
from mintnet.experiments.stage5a import DGPS, _DGP_REGISTRY, _condition_seed, _graph_metrics, _true_adjacency

METHODS: tuple[str, ...] = ("pc",)


@dataclass(frozen=True)
class Stage5eConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    pc_alpha: float
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    source_path: Path | None = None


def load_stage5e_config(path: Path) -> Stage5eConfig:
    """Load a Stage 5e configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 5e configuration must be a mapping")

    return Stage5eConfig(
        sample_sizes=tuple(int(value) for value in values["sample_sizes"]),
        strength=float(values["strength"]),
        pc_alpha=float(values["pc_alpha"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        source_path=path.resolve(),
    )


# --- Generic shard-aggregation contract -------------------------------
# See stage5a.py's own comment for the full contract description.

load_config = load_stage5e_config
COMBINATION_COLUMNS: tuple[str, ...] = ("dgp", "n", "method")


def expected_row_count(config: Stage5eConfig) -> int:
    return len(DGPS) * len(config.sample_sizes) * config.replicates * len(METHODS)


def expected_combinations(config: Stage5eConfig) -> set[tuple[str, int, str]]:
    return {(dgp, n, method) for dgp in DGPS for n in config.sample_sizes for method in METHODS}


def _repository_root(config: Stage5eConfig) -> Path:
    if config.source_path is not None:
        return config.source_path.parent.parent
    return Path(__file__).resolve().parents[3]


def _git_commit(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _resolved_config(config: Stage5eConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "pc_alpha": config.pc_alpha,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "note": (
            "master_seed/strength are unchanged from stage5a_comparator_benchmark.yaml so this "
            "charter's condition seeds are bit-identical to D-047's own draws -- see "
            "docs/stage5e_charter.md's 'Data access' fair-comparison rule."
        ),
    }


def _write_evidence(config: Stage5eConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage5e_charter.md"
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


def _pc_adjacency(data: np.ndarray, pc_alpha: float) -> np.ndarray:
    return fit_pc_skeleton(data, alpha=pc_alpha).adjacency


def _run_cell(task: tuple[int, str, int, int, Stage5eConfig]) -> list[dict[str, object]]:
    """Every (dgp, N) cell's full replicate loop, self-contained and
    picklable so it can run in a worker process. Seeds are derived via
    `stage5a._condition_seed` unchanged -- identical draws to D-047."""
    dgp_index, dgp_name, sample_index, n, config = task
    dgp = _DGP_REGISTRY[dgp_name]
    sample: Callable = dgp["sample"]  # type: ignore[assignment]
    p = int(dgp["p"])
    truth = _true_adjacency(dgp["true_edges"], p)  # type: ignore[arg-type]

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _condition_seed(config.master_seed, dgp_index, sample_index, replicate)
        try:
            data = sample(n, config.strength, np.random.default_rng(seed))
            status, error = "ok", ""
        except Exception as exc:  # raw evidence must retain sampling failures
            data = None
            status, error = "error", f"{type(exc).__name__}: {exc}"

        for method in METHODS:
            started = time.perf_counter()
            row_status, row_error = status, error
            metrics: dict[str, object] = {
                "precision": np.nan,
                "recall": np.nan,
                "f1": np.nan,
                "shd": np.nan,
                "n_estimated_edges": np.nan,
            }
            if data is not None:
                try:
                    estimated = _pc_adjacency(data, config.pc_alpha)
                    metrics = _graph_metrics(estimated, truth)
                except Exception as exc:
                    row_status = "error"
                    row_error = f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "dgp": dgp_name,
                    "method": method,
                    "n": n,
                    "pc_alpha": config.pc_alpha,
                    "replicate": replicate,
                    "seed": seed,
                    **metrics,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    return rows


def run_stage5e(
    config: Stage5eConfig,
    output_dir: Path,
    max_workers: int | None = None,
    dgps: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """Run the PC-stable skeleton comparator across all five DGP shapes
    and the full N grid, on data drawn identically to D-047's own.

    Parallelized across (dgp, N) cells via a process pool -- each cell is
    fully independent. `dgps`/`sample_sizes` restrict which cells run,
    for a single-cell CI shard; `dgp_index`/`sample_index` are always
    derived from the *full* `DGPS`/`config.sample_sizes`, so a shard's
    seeds are bit-identical to what an unsharded run would draw.
    `write_report=False` skips the descriptive-verdict report, which
    requires every cell to be present to be meaningful."""
    import os
    from concurrent.futures import ProcessPoolExecutor

    run_started = time.perf_counter()

    target_dgps = set(dgps) if dgps is not None else set(DGPS)
    target_sizes = set(sample_sizes) if sample_sizes is not None else set(config.sample_sizes)

    tasks = [
        (dgp_index, dgp_name, sample_index, n, config)
        for dgp_index, dgp_name in enumerate(DGPS)
        if dgp_name in target_dgps
        for sample_index, n in enumerate(config.sample_sizes)
        if n in target_sizes
    ]
    if not tasks:
        raise ValueError("dgps/sample_sizes filter selected no cells")

    if max_workers is None:
        max_workers = min(len(tasks), max(1, (os.cpu_count() or 1) - 1))

    rows: list[dict[str, object]] = []
    if max_workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for cell_rows in executor.map(_run_cell, tasks):
                rows.extend(cell_rows)
    else:
        for task in tasks:
            rows.extend(_run_cell(task))

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if not write_report:
        return raw
    from mintnet.experiments.stage5e_reporting import write_stage5e_report

    write_stage5e_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--dgps", type=str, default=None, help="comma-separated subset of DGP shapes to run (default: all)"
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values to run (default: all)"
    )
    parser.add_argument(
        "--no-report", action="store_true", help="skip the descriptive-verdict report (use for CI shards)"
    )
    arguments = parser.parse_args()
    dgps = tuple(arguments.dgps.split(",")) if arguments.dgps else None
    sample_sizes = tuple(int(value) for value in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    run_stage5e(
        load_stage5e_config(arguments.config),
        arguments.output,
        max_workers=arguments.workers,
        dgps=dgps,
        sample_sizes=sample_sizes,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
