"""Deterministic, shardable raw-evidence runner for the frozen Stage 8a
Tier-0 confidence-score calibration check. See docs/stage8a_charter.md.

Runs `growing_subset_dpi` (the partial-correlation mechanism, D-053)
on every candidate edge of each swept 3-node fixture, records the
decisive p-value and resulting margin score per edge alongside ground
truth, and leaves binning/monotonicity/ECE analysis to
stage8a_calibration_reporting -- mirroring this project's own
established raw-evidence-first discipline.
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

from mintnet.confidence import edge_margin
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage8a_conditions import all_conditions, sample_condition, true_edges_for
from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi

# Dash-separated, not zero-padded digit pairs ("01"/"02"/"12") -- those
# round-trip through CSV as ints (pandas infers numeric dtype and drops
# the leading zero), silently breaking combination-key equality checks.
_EDGE_LABELS: dict[tuple[int, int], str] = {(0, 1): "0-1", (0, 2): "0-2", (1, 2): "1-2"}
CONDITIONS: tuple[str, ...] = all_conditions()


@dataclass(frozen=True)
class Stage8aConfig:
    sample_sizes: tuple[int, ...]
    replicates: int
    batch_size: int
    master_seed: int
    ece_tolerance: float
    bin_count: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage8aConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 8a configuration must be a mapping")

    return Stage8aConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        master_seed=int(values["master_seed"]),
        ece_tolerance=float(values["ece_tolerance"]),
        bin_count=int(values["bin_count"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("condition", "n", "replicate", "edge")


def _n_batches(config: Stage8aConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage8aConfig) -> set[tuple[str, int, int, str]]:
    return {
        (condition, n, replicate, edge)
        for condition in CONDITIONS
        for n in config.sample_sizes
        for replicate in range(config.replicates)
        for edge in _EDGE_LABELS.values()
    }


def expected_row_count(config: Stage8aConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(config: Stage8aConfig, condition_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.master_seed, condition_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage8aConfig) -> Path:
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


def _resolved_config(config: Stage8aConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "batch_size": config.batch_size,
        "master_seed": config.master_seed,
        "ece_tolerance": config.ece_tolerance,
        "bin_count": config.bin_count,
    }


def _write_evidence(config: Stage8aConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage8a_charter.md"
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


def _run_one_replicate(
    condition: str, condition_index: int, n: int, sample_index: int, replicate: int,
    alpha: float, config: Stage8aConfig,
) -> list[dict[str, object]]:
    true_edges = true_edges_for(condition)
    seed = _condition_seed(config, condition_index, sample_index, replicate)
    started = time.perf_counter()
    try:
        data = sample_condition(condition, n, np.random.default_rng(seed))
        flagged = np.ones((3, 3), dtype=bool)
        np.fill_diagonal(flagged, False)
        result = growing_subset_dpi(data, flagged, alpha)
        status, error = "ok", ""
    except Exception as exc:  # raw evidence must retain pipeline failures
        result = None
        status, error = "error", f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    rows: list[dict[str, object]] = []
    for pair, label in _EDGE_LABELS.items():
        row_status, row_error = status, error
        decisive_p_value = np.nan
        retained = np.nan
        margin = np.nan
        correct = np.nan
        if result is not None:
            try:
                decisive_p_value = float(result.decisive_p_value[pair])
                retained = bool(result.adjacency[pair])
                margin = edge_margin(decisive_p_value, alpha, retained=retained)
                correct = float(retained == true_edges[pair])
            except Exception as exc:  # retain scoring failures per edge
                row_status = "error"
                row_error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "condition": condition, "n": n, "alpha": alpha, "replicate": replicate, "seed": seed,
                "edge": label, "decisive_p_value": decisive_p_value, "retained": retained,
                "true_edge": true_edges[pair], "margin": margin, "correct": correct,
                "elapsed_seconds": elapsed, "status": row_status, "error": row_error,
            }
        )
    return rows


def run_stage8a(
    config: Stage8aConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- replicate ranges are always derived
    from `config.batch_size` against the FULL replicate count, and
    seeds key off `CONDITIONS.index(...)`/`config.sample_sizes.index(...)`/
    `replicate` (all full-grid quantities), so a shard's results match
    an unsharded run's for the same replicates."""
    run_started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_conditions = conditions if conditions is not None else CONDITIONS
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        condition_index = CONDITIONS.index(condition)
        for n in target_sizes:
            sample_index = config.sample_sizes.index(n)
            alpha = float(alpha_formula.predict(float(n)))
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.extend(
                        _run_one_replicate(condition, condition_index, n, sample_index, replicate, alpha, config)
                    )

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if write_report:
        from mintnet.experiments.stage8a_calibration_reporting import write_report as write_stage8a_report

        write_stage8a_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None,
        help="comma-separated subset of conditions (e.g. chain_0.5,triangle_balanced; default: all)",
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

    run_stage8a(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
