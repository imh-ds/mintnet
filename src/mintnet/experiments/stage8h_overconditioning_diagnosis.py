"""Deterministic, shardable raw-evidence runner for the frozen Stage 8h
over-conditioning power-loss diagnostic. See docs/stage8h_charter.md.

Fixture: `sample_chain` (`X1 -> X2 -> X3`, columns `0, 1, 2`), extended
with three independent decoy columns `W1, W2, W3` (columns `3, 4, 5`,
`N(0,1)`, zero correlation with everything by construction). The tested
pair is `(0, 2)` -- genuinely, exactly conditionally independent given
column `1` alone (this project's own already-validated chain ground
truth). `decoy_count in {0, 1, 2, 3}` selects how many of the
independent decoys are added to that already-sufficient conditioning
set (`(1,)`, `(1, 3)`, `(1, 3, 4)`, `(1, 3, 4, 5)`) -- conditioning
sizes `1` through `4`, matching `growing_subset_dpi`'s own
`max_conditioning_size=4` cap.
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

from mintnet.dpi.multi_conditional import compute_partial_correlation_evidence
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.simulation.motifs import sample_chain

DECOY_COUNTS: tuple[int, ...] = (0, 1, 2, 3)


def _conditioning_for(decoy_count: int) -> tuple[int, ...]:
    return (1,) + tuple(range(3, 3 + decoy_count))


def _sample_fixture(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    chain = sample_chain(n, strength, rng)
    decoys = rng.normal(size=(n, 3))
    return np.column_stack((chain, decoys))


@dataclass(frozen=True)
class Stage8hConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    replicates: int
    batch_size: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage8hConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 8h configuration must be a mapping")

    return Stage8hConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("decoy_count", "n", "strength", "replicate")


def _n_batches(config: Stage8hConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage8hConfig) -> set[tuple[int, int, float, int]]:
    return {
        (decoy_count, n, strength, replicate)
        for decoy_count in DECOY_COUNTS
        for n in config.sample_sizes
        for strength in config.strengths
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage8hConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(
    config: Stage8hConfig, decoy_index: int, sample_index: int, strength_index: int, replicate: int
) -> int:
    sequence = np.random.SeedSequence([config.master_seed, decoy_index, sample_index, strength_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage8hConfig) -> Path:
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


def _resolved_config(config: Stage8hConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strengths": list(config.strengths),
        "replicates": config.replicates,
        "batch_size": config.batch_size,
        "master_seed": config.master_seed,
    }


def _write_evidence(config: Stage8hConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage8h_charter.md"
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
    decoy_count: int, decoy_index: int, n: int, sample_index: int, strength: float, strength_index: int,
    replicate: int, alpha: float, config: Stage8hConfig,
) -> dict[str, object]:
    seed = _condition_seed(config, decoy_index, sample_index, strength_index, replicate)
    started = time.perf_counter()
    p_value = np.nan
    rejected = np.nan
    status, error = "ok", ""
    try:
        data = _sample_fixture(n, strength, np.random.default_rng(seed))
        conditioning = _conditioning_for(decoy_count)
        evidence = compute_partial_correlation_evidence(data, 0, 2, conditioning)
        p_value = float(evidence.p_value)
        rejected = bool(p_value <= alpha)
    except Exception as exc:  # raw evidence must retain pipeline failures
        status, error = "error", f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    return {
        "decoy_count": decoy_count, "n": n, "strength": strength, "alpha": alpha, "replicate": replicate,
        "seed": seed, "conditioning_size": 1 + decoy_count,
        "p_value": p_value, "rejected": rejected, "elapsed_seconds": elapsed, "status": status, "error": error,
    }


def run_stage8h(
    config: Stage8hConfig,
    output_dir: Path,
    decoy_counts: tuple[int, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    strengths: tuple[float, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`decoy_counts`/`sample_sizes`/`strengths`/`batches` restrict which
    cells run, for a single-cell CI shard -- replicate ranges are
    always derived from `config.batch_size` against the FULL replicate
    count, and seeds key off `DECOY_COUNTS.index(...)`/`config.
    sample_sizes.index(...)`/`config.strengths.index(...)`/`replicate`
    (all full-grid quantities), so a shard's results match an unsharded
    run's for the same replicates."""
    run_started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_decoy_counts = decoy_counts if decoy_counts is not None else DECOY_COUNTS
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_strengths = strengths if strengths is not None else config.strengths
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for decoy_count in target_decoy_counts:
        decoy_index = DECOY_COUNTS.index(decoy_count)
        for n in target_sizes:
            sample_index = config.sample_sizes.index(n)
            alpha = float(alpha_formula.predict(float(n)))
            for strength in target_strengths:
                strength_index = config.strengths.index(strength)
                for batch in target_batches:
                    start_replicate = batch * config.batch_size
                    end_replicate = min(start_replicate + config.batch_size, config.replicates)
                    for replicate in range(start_replicate, end_replicate):
                        rows.append(
                            _run_one_replicate(
                                decoy_count, decoy_index, n, sample_index, strength, strength_index,
                                replicate, alpha, config,
                            )
                        )

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if write_report:
        from mintnet.experiments.stage8h_overconditioning_diagnosis_reporting import (
            write_report as write_stage8h_report,
        )

        write_stage8h_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--decoy-counts", type=str, default=None, help="comma-separated subset of decoy counts (default: all)"
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--strengths", type=str, default=None, help="comma-separated subset of strength values (default: all)"
    )
    parser.add_argument(
        "--batches", type=str, default=None, help="comma-separated subset of batch indices (default: all)"
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    decoy_counts = tuple(int(v) for v in arguments.decoy_counts.split(",")) if arguments.decoy_counts else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    strengths = tuple(float(v) for v in arguments.strengths.split(",")) if arguments.strengths else None
    batches = tuple(int(v) for v in arguments.batches.split(",")) if arguments.batches else None

    run_stage8h(
        load_config(arguments.config), arguments.output,
        decoy_counts=decoy_counts, sample_sizes=sample_sizes, strengths=strengths, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
