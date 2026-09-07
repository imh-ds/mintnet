"""Deterministic raw-evidence runner for the frozen Stage 5c p-adjusted-
screening-alpha re-test. See docs/stage5c_charter.md.

Reuses Stage 5b's own DGP registry and noise-column-extension mechanism
(`mintnet.experiments.stage5b._DGP_REGISTRY`,
`._sample_with_extra_noise`) and Stage 5a's fitting/scoring helpers
(`mintnet.experiments.stage5a._mint_adjacency`, `._graph_metrics`,
`._true_adjacency`) unmodified. The only new mechanism is
`_screening_alpha_for_p`: a disclosed, deterministic log-linear
interpolation of Stage 2's own two already-calibrated screening-alpha
anchor points (`.001` at `p=15`, `.0001` at `p=30`), used in place of
Stage 5b's fixed `alpha=.001` -- see this charter's own "p-adjusted
alpha" section for why this is an interpolation, not a fresh
truth-informed calibration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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

METHODS: tuple[str, ...] = ("mint", "ebicglasso")
DGPS: tuple[str, ...] = ("chain_fork_hub", "overlap")

_STAGE_TAG = 503  # disjoint from stage5a's 501 and stage5b's 502

# Stage 2's own two already-calibrated screening-alpha anchor points
# (outline Section 16's own v3 revision note: ".001 at p=15, .0001 at
# p=30"), log-linearly interpolated in ln(p) -- see this module's own
# docstring and docs/stage5c_charter.md for why this is an
# interpolation, not a fresh calibration.
_ANCHOR_P_LOW, _ANCHOR_ALPHA_LOW = 15.0, 0.001
_ANCHOR_P_HIGH, _ANCHOR_ALPHA_HIGH = 30.0, 0.0001


def _screening_alpha_for_p(p: int) -> float:
    log_low = math.log10(_ANCHOR_ALPHA_LOW)
    log_high = math.log10(_ANCHOR_ALPHA_HIGH)
    ln_low = math.log(_ANCHOR_P_LOW)
    ln_high = math.log(_ANCHOR_P_HIGH)
    slope = (log_high - log_low) / (ln_high - ln_low)
    log_alpha = log_low + slope * (math.log(p) - ln_low)
    return float(10.0**log_alpha)


@dataclass(frozen=True)
class Stage5cConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    ebicglasso_gamma: float
    ebicglasso_n_lambda: int
    ebicglasso_lambda_min_ratio: float
    noise_multipliers: tuple[int, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage5c_config(path: Path) -> Stage5cConfig:
    """Load a Stage 5c configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 5c configuration must be a mapping")

    return Stage5cConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        ebicglasso_gamma=float(values["ebicglasso_gamma"]),
        ebicglasso_n_lambda=int(values["ebicglasso_n_lambda"]),
        ebicglasso_lambda_min_ratio=float(values["ebicglasso_lambda_min_ratio"]),
        noise_multipliers=_values(values, "noise_multipliers", int),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        source_path=path.resolve(),
    )


def _condition_seed(
    master_seed: int, dgp_index: int, sample_index: int, multiplier_index: int, replicate: int
) -> int:
    sequence = np.random.SeedSequence(
        [master_seed, _STAGE_TAG, dgp_index, sample_index, multiplier_index, replicate]
    )
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage5cConfig) -> Path:
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


def _resolved_config(config: Stage5cConfig, alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "ebicglasso_gamma": config.ebicglasso_gamma,
        "ebicglasso_n_lambda": config.ebicglasso_n_lambda,
        "ebicglasso_lambda_min_ratio": config.ebicglasso_lambda_min_ratio,
        "noise_multipliers": list(config.noise_multipliers),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "d012_dpi_alpha_by_n": alpha_by_n,
        "screening_alpha_anchors": {
            "p15": _ANCHOR_ALPHA_LOW,
            "p30": _ANCHOR_ALPHA_HIGH,
        },
    }


def _write_evidence(
    config: Stage5cConfig, output_dir: Path, raw: pd.DataFrame, alpha_by_n: dict[int, float], runtime_seconds: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage5c_charter.md"
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
load_config = load_stage5c_config
COMBINATION_COLUMNS: tuple[str, ...] = ("dgp", "n", "noise_multiplier", "method")


def expected_row_count(config: Stage5cConfig) -> int:
    return len(DGPS) * len(config.sample_sizes) * len(config.noise_multipliers) * config.replicates * len(METHODS)


def expected_combinations(config: Stage5cConfig) -> set[tuple[str, int, int, str]]:
    return {
        (dgp, n, multiplier, method)
        for dgp in DGPS
        for n in config.sample_sizes
        for multiplier in config.noise_multipliers
        for method in METHODS
    }


def _run_cell(
    task: tuple[int, str, int, int, int, int, float, Stage5cConfig]
) -> list[dict[str, object]]:
    """Every (dgp, N, noise multiplier) cell's full replicate loop,
    self-contained and picklable so it can run in a worker process or a
    CI shard -- each cell is fully independent."""
    dgp_index, dgp_name, sample_index, n, multiplier_index, multiplier, dpi_alpha, config = task
    dgp = _DGP_REGISTRY[dgp_name]
    sample: Callable = dgp["sample"]  # type: ignore[assignment]
    native_noise = int(dgp["native_noise"])
    native_p = int(dgp["native_p"])
    p = native_p + native_noise * (multiplier - 1)
    truth = _true_adjacency(dgp["true_edges"], p)  # type: ignore[arg-type]
    screening_alpha = _screening_alpha_for_p(p)

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _condition_seed(config.master_seed, dgp_index, sample_index, multiplier_index, replicate)
        try:
            data = _sample_with_extra_noise(
                sample, native_noise, multiplier, n, config.strength, np.random.default_rng(seed)
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
                    "noise_multiplier": multiplier,
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


def run_stage5c(
    config: Stage5cConfig,
    output_dir: Path,
    max_workers: int | None = None,
    dgps: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    noise_multipliers: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """Run MINT (p-adjusted screening alpha) and EBICglasso across the
    noise-multiplier grid, paired same-draw per (dgp, N, noise
    multiplier, replicate). Parallelized across (dgp, N, noise
    multiplier) cells -- three shard-filterable dimensions, unlike
    Stage 5b's two, specifically so a CI shard never has more than one
    task inside it (see .github/workflows/sharded_benchmark.yml's own
    header comment on why that mattered for Stage 5b's own run time).
    `dgp_index`/`sample_index`/`multiplier_index` are always derived
    from the full grids, so a shard's seeds match an unsharded run's."""
    import os
    from concurrent.futures import ProcessPoolExecutor

    run_started = time.perf_counter()

    selected = select_form(fit_candidate_forms())
    alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    target_dgps = set(dgps) if dgps is not None else set(DGPS)
    target_sizes = set(sample_sizes) if sample_sizes is not None else set(config.sample_sizes)
    target_multipliers = set(noise_multipliers) if noise_multipliers is not None else set(config.noise_multipliers)

    tasks = [
        (dgp_index, dgp_name, sample_index, n, multiplier_index, multiplier, alpha_by_n[n], config)
        for dgp_index, dgp_name in enumerate(DGPS)
        if dgp_name in target_dgps
        for sample_index, n in enumerate(config.sample_sizes)
        if n in target_sizes
        for multiplier_index, multiplier in enumerate(config.noise_multipliers)
        if multiplier in target_multipliers
    ]
    if not tasks:
        raise ValueError("dgps/sample_sizes/noise_multipliers filter selected no cells")

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
    _write_evidence(config, output_dir, raw, alpha_by_n, time.perf_counter() - run_started)
    if not write_report:
        return raw
    from mintnet.experiments.stage5c_reporting import write_stage5c_report

    write_stage5c_report(raw, config, output_dir)
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
        "--noise-multipliers", type=str, default=None, help="comma-separated subset of noise multipliers to run"
    )
    parser.add_argument(
        "--no-report", action="store_true", help="skip the descriptive-verdict report (use for CI shards)"
    )
    arguments = parser.parse_args()
    dgps = tuple(arguments.dgps.split(",")) if arguments.dgps else None
    sample_sizes = tuple(int(value) for value in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    multipliers = (
        tuple(int(value) for value in arguments.noise_multipliers.split(","))
        if arguments.noise_multipliers
        else None
    )
    run_stage5c(
        load_stage5c_config(arguments.config),
        arguments.output,
        arguments.workers,
        dgps=dgps,
        sample_sizes=sample_sizes,
        noise_multipliers=multipliers,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
