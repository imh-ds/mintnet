"""Deterministic raw-evidence runner for the frozen Stage 5d
signal-strength sweep. See docs/stage5d_charter.md.

Reuses Stage 5b's own DGP registry and noise-column mechanism
(`mintnet.experiments.stage5b._DGP_REGISTRY`,
`._sample_with_extra_noise`, called here with the noise multiplier
fixed at `1` -- each shape's own native noise-column count, no extra
columns), Stage 5a's fitting/scoring helpers (`_mint_adjacency`,
`._graph_metrics`, `._true_adjacency`), and Stage 5c's `alpha(p)`
screening-alpha interpolation (now the preferred MINT configuration
per D-049) unmodified. The only new axis is `strength`, which is
already a native parameter of each shape's own DGP sampler.
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

from mintnet.comparators.ebicglasso import fit_ebicglasso
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage5a import _graph_metrics, _mint_adjacency, _true_adjacency
from mintnet.experiments.stage5b import _DGP_REGISTRY, _sample_with_extra_noise
from mintnet.experiments.stage5c import _screening_alpha_for_p

METHODS: tuple[str, ...] = ("mint", "ebicglasso")
DGPS: tuple[str, ...] = ("chain_fork_hub", "overlap")

_STAGE_TAG = 504  # disjoint from stage5a's 501, stage5b's 502, stage5c's 503
_NATIVE_MULTIPLIER = 1  # noise held at each shape's own native column count throughout


@dataclass(frozen=True)
class Stage5dConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    ebicglasso_gamma: float
    ebicglasso_n_lambda: int
    ebicglasso_lambda_min_ratio: float
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage5d_config(path: Path) -> Stage5dConfig:
    """Load a Stage 5d configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 5d configuration must be a mapping")

    return Stage5dConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        ebicglasso_gamma=float(values["ebicglasso_gamma"]),
        ebicglasso_n_lambda=int(values["ebicglasso_n_lambda"]),
        ebicglasso_lambda_min_ratio=float(values["ebicglasso_lambda_min_ratio"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        source_path=path.resolve(),
    )


def _condition_seed(
    master_seed: int, dgp_index: int, sample_index: int, strength_index: int, replicate: int
) -> int:
    sequence = np.random.SeedSequence(
        [master_seed, _STAGE_TAG, dgp_index, sample_index, strength_index, replicate]
    )
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage5dConfig) -> Path:
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


def _resolved_config(config: Stage5dConfig, alpha_by_n: dict[int, float], screening_alpha_by_dgp: dict[str, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strengths": list(config.strengths),
        "ebicglasso_gamma": config.ebicglasso_gamma,
        "ebicglasso_n_lambda": config.ebicglasso_n_lambda,
        "ebicglasso_lambda_min_ratio": config.ebicglasso_lambda_min_ratio,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "d012_dpi_alpha_by_n": alpha_by_n,
        "alpha_p_screening_alpha_by_dgp": screening_alpha_by_dgp,
    }


def _write_evidence(
    config: Stage5dConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    alpha_by_n: dict[int, float],
    screening_alpha_by_dgp: dict[str, float],
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, alpha_by_n, screening_alpha_by_dgp), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage5d_charter.md"
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


# --- Generic shard-aggregation contract (see stage5a.py's own comment) -
load_config = load_stage5d_config
COMBINATION_COLUMNS: tuple[str, ...] = ("dgp", "n", "strength", "method")


def expected_row_count(config: Stage5dConfig) -> int:
    return len(DGPS) * len(config.sample_sizes) * len(config.strengths) * config.replicates * len(METHODS)


def expected_combinations(config: Stage5dConfig) -> set[tuple[str, int, float, str]]:
    return {
        (dgp, n, strength, method)
        for dgp in DGPS
        for n in config.sample_sizes
        for strength in config.strengths
        for method in METHODS
    }


def _run_cell(
    task: tuple[int, str, int, int, int, float, float, Stage5dConfig]
) -> list[dict[str, object]]:
    """Every (dgp, N, strength) cell's full replicate loop, self-
    contained and picklable so it can run in a worker process or a CI
    shard -- each cell is fully independent."""
    dgp_index, dgp_name, sample_index, n, strength_index, strength, dpi_alpha, screening_alpha, config = task
    dgp = _DGP_REGISTRY[dgp_name]
    sample: Callable = dgp["sample"]  # type: ignore[assignment]
    native_noise = int(dgp["native_noise"])
    native_p = int(dgp["native_p"])
    p = native_p  # multiplier fixed at 1 throughout this charter
    truth = _true_adjacency(dgp["true_edges"], p)  # type: ignore[arg-type]

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _condition_seed(config.master_seed, dgp_index, sample_index, strength_index, replicate)
        try:
            data = _sample_with_extra_noise(
                sample, native_noise, _NATIVE_MULTIPLIER, n, strength, np.random.default_rng(seed)
            )
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
            selected_lambda: float | None = None
            if data is not None:
                try:
                    if method == "mint":
                        estimated = _mint_adjacency(data, screening_alpha, dpi_alpha)
                    else:
                        result = fit_ebicglasso(
                            data,
                            gamma=config.ebicglasso_gamma,
                            n_lambda=config.ebicglasso_n_lambda,
                            lambda_min_ratio=config.ebicglasso_lambda_min_ratio,
                        )
                        estimated = result.adjacency
                        selected_lambda = result.selected_lambda
                    metrics = _graph_metrics(estimated, truth)
                except Exception as exc:  # retain fitting/scoring failures by method
                    row_status = "error"
                    row_error = f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "dgp": dgp_name,
                    "method": method,
                    "n": n,
                    "strength": strength,
                    "p": p,
                    "dpi_alpha": dpi_alpha if method == "mint" else np.nan,
                    "screening_alpha": screening_alpha if method == "mint" else np.nan,
                    "ebicglasso_lambda": selected_lambda if selected_lambda is not None else np.nan,
                    "replicate": replicate,
                    "seed": seed,
                    **metrics,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    return rows


def run_stage5d(
    config: Stage5dConfig,
    output_dir: Path,
    max_workers: int | None = None,
    dgps: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    strengths: tuple[float, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """Run MINT (alpha(p), Stage 5c's own preferred configuration) and
    EBICglasso across the strength grid, noise held at each shape's own
    native column count. Parallelized/shardable across (dgp, N,
    strength) cells; `dgp_index`/`sample_index`/`strength_index` are
    always derived from the full grids, so a shard's seeds match an
    unsharded run's."""
    import os
    from concurrent.futures import ProcessPoolExecutor

    run_started = time.perf_counter()

    selected = select_form(fit_candidate_forms())
    alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}
    screening_alpha_by_dgp = {
        dgp_name: _screening_alpha_for_p(int(_DGP_REGISTRY[dgp_name]["native_p"])) for dgp_name in DGPS
    }

    target_dgps = set(dgps) if dgps is not None else set(DGPS)
    target_sizes = set(sample_sizes) if sample_sizes is not None else set(config.sample_sizes)
    target_strengths = set(strengths) if strengths is not None else set(config.strengths)

    tasks = [
        (
            dgp_index, dgp_name, sample_index, n, strength_index, strength,
            alpha_by_n[n], screening_alpha_by_dgp[dgp_name], config,
        )
        for dgp_index, dgp_name in enumerate(DGPS)
        if dgp_name in target_dgps
        for sample_index, n in enumerate(config.sample_sizes)
        if n in target_sizes
        for strength_index, strength in enumerate(config.strengths)
        if strength in target_strengths
    ]
    if not tasks:
        raise ValueError("dgps/sample_sizes/strengths filter selected no cells")

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
    _write_evidence(config, output_dir, raw, alpha_by_n, screening_alpha_by_dgp, time.perf_counter() - run_started)
    if not write_report:
        return raw
    from mintnet.experiments.stage5d_reporting import write_stage5d_report

    write_stage5d_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--dgps", type=str, default=None, help="comma-separated subset of DGP shapes to run")
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values to run"
    )
    parser.add_argument(
        "--strengths", type=str, default=None, help="comma-separated subset of strengths to run"
    )
    parser.add_argument(
        "--no-report", action="store_true", help="skip the descriptive-verdict report (use for CI shards)"
    )
    arguments = parser.parse_args()
    dgps = tuple(arguments.dgps.split(",")) if arguments.dgps else None
    sample_sizes = tuple(int(value) for value in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    strengths = tuple(float(value) for value in arguments.strengths.split(",")) if arguments.strengths else None
    run_stage5d(
        load_stage5d_config(arguments.config),
        arguments.output,
        arguments.workers,
        dgps=dgps,
        sample_sizes=sample_sizes,
        strengths=strengths,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
