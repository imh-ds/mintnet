"""Deterministic, shardable raw-evidence runner for the frozen Stage 8j
post-screening selection-effect diagnostic. See docs/stage8j_charter.md.

Fixture: `sample_chain` (`X1 -> X2 -> X3`, columns `0, 1, 2`), extended
with `K` independent decoy columns (columns `3` through `3+K-1`,
`N(0,1)`, zero population correlation with everything). The tested pair
is `(0, 2)` -- exactly conditionally independent given column `1`
alone (chain's own already-validated ground truth). Three conditions
per replicate:

- `baseline`: condition on `(1,)` alone -- the already-correct,
  sufficient set. Does not depend on `K` at all; run at every `K` value
  purely to keep the combination-key schema uniform for shard
  aggregation (mirrors Stage 8f's own `step2_control` precedent), not
  because the baseline DGP itself depends on `K`.
- `random_decoy`: condition on `(1, 3)` -- the first decoy,
  unconditionally (the same "arbitrary, unselected" comparator Stage 8h
  already used at `decoy_count=1`).
- `selected_decoy`: condition on `(1, s)` where `s` is whichever of the
  `K` decoy columns has the largest `max(|corr(decoy, X1)|,
  |corr(decoy, X3)|)` **in that specific sample** -- the "winner" of an
  implicit screening contest against `K` candidates.
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

CONDITIONS: tuple[str, ...] = ("baseline", "random_decoy", "selected_decoy")


def _sample_fixture(n: int, strength: float, k: int, rng: np.random.Generator) -> np.ndarray:
    chain = sample_chain(n, strength, rng)
    decoys = rng.normal(size=(n, k))
    return np.column_stack((chain, decoys))


def _selected_decoy_column(data: np.ndarray, k: int) -> int:
    """The decoy column (index into `data`, in `[3, 3+k)`) with the
    largest max(|corr(., X1)|, |corr(., X3)|) in this specific sample."""
    x1, x3 = data[:, 0], data[:, 2]
    best_column = 3
    best_score = -1.0
    for column in range(3, 3 + k):
        decoy = data[:, column]
        score = max(abs(np.corrcoef(decoy, x1)[0, 1]), abs(np.corrcoef(decoy, x3)[0, 1]))
        if score > best_score:
            best_score = score
            best_column = column
    return best_column


def _conditioning_for(condition: str, data: np.ndarray, k: int) -> tuple[int, ...]:
    if condition == "baseline":
        return (1,)
    if condition == "random_decoy":
        return (1, 3)
    if condition == "selected_decoy":
        return (1, _selected_decoy_column(data, k))
    raise ValueError(f"unknown condition: {condition!r}")


@dataclass(frozen=True)
class Stage8jConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    pool_sizes: tuple[int, ...]
    replicates: int
    batch_size: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage8jConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 8j configuration must be a mapping")

    return Stage8jConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        pool_sizes=_values(values, "pool_sizes", int),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("condition", "k", "n", "strength", "replicate")


def _n_batches(config: Stage8jConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage8jConfig) -> set[tuple[str, int, int, float, int]]:
    return {
        (condition, k, n, strength, replicate)
        for condition in CONDITIONS
        for k in config.pool_sizes
        for n in config.sample_sizes
        for strength in config.strengths
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage8jConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(
    config: Stage8jConfig, condition_index: int, k_index: int, sample_index: int, strength_index: int, replicate: int
) -> int:
    sequence = np.random.SeedSequence(
        [config.master_seed, condition_index, k_index, sample_index, strength_index, replicate]
    )
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage8jConfig) -> Path:
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


def _resolved_config(config: Stage8jConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strengths": list(config.strengths),
        "pool_sizes": list(config.pool_sizes),
        "replicates": config.replicates,
        "batch_size": config.batch_size,
        "master_seed": config.master_seed,
    }


def _write_evidence(config: Stage8jConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage8j_charter.md"
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
    condition: str, condition_index: int, k: int, k_index: int, n: int, sample_index: int, strength: float,
    strength_index: int, replicate: int, alpha: float, config: Stage8jConfig,
) -> dict[str, object]:
    seed = _condition_seed(config, condition_index, k_index, sample_index, strength_index, replicate)
    started = time.perf_counter()
    p_value = np.nan
    rejected = np.nan
    conditioning_size = np.nan
    status, error = "ok", ""
    try:
        data = _sample_fixture(n, strength, k, np.random.default_rng(seed))
        conditioning = _conditioning_for(condition, data, k)
        evidence = compute_partial_correlation_evidence(data, 0, 2, conditioning)
        p_value = float(evidence.p_value)
        rejected = bool(p_value <= alpha)
        conditioning_size = len(conditioning)
    except Exception as exc:  # raw evidence must retain pipeline failures
        status, error = "error", f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    return {
        "condition": condition, "k": k, "n": n, "strength": strength, "alpha": alpha, "replicate": replicate,
        "seed": seed, "conditioning_size": conditioning_size,
        "p_value": p_value, "rejected": rejected, "elapsed_seconds": elapsed, "status": status, "error": error,
    }


def run_stage8j(
    config: Stage8jConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    pool_sizes: tuple[int, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    strengths: tuple[float, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`pool_sizes`/`sample_sizes`/`strengths`/`batches`
    restrict which cells run, for a single-cell CI shard -- replicate
    ranges are always derived from `config.batch_size` against the FULL
    replicate count, and seeds key off `CONDITIONS.index(...)`/
    `config.pool_sizes.index(...)`/`config.sample_sizes.index(...)`/
    `config.strengths.index(...)`/`replicate` (all full-grid
    quantities), so a shard's results match an unsharded run's for the
    same replicates."""
    run_started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_conditions = conditions if conditions is not None else CONDITIONS
    target_pool_sizes = pool_sizes if pool_sizes is not None else config.pool_sizes
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_strengths = strengths if strengths is not None else config.strengths
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        condition_index = CONDITIONS.index(condition)
        for k in target_pool_sizes:
            k_index = config.pool_sizes.index(k)
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
                                    condition, condition_index, k, k_index, n, sample_index, strength,
                                    strength_index, replicate, alpha, config,
                                )
                            )

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if write_report:
        from mintnet.experiments.stage8j_selection_effect_diagnosis_reporting import (
            write_report as write_stage8j_report,
        )

        write_stage8j_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None, help="comma-separated subset of conditions (default: all)"
    )
    parser.add_argument(
        "--pool-sizes", type=str, default=None, help="comma-separated subset of K values (default: all)"
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

    conditions = tuple(arguments.conditions.split(",")) if arguments.conditions else None
    pool_sizes = tuple(int(v) for v in arguments.pool_sizes.split(",")) if arguments.pool_sizes else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    strengths = tuple(float(v) for v in arguments.strengths.split(",")) if arguments.strengths else None
    batches = tuple(int(v) for v in arguments.batches.split(",")) if arguments.batches else None

    run_stage8j(
        load_config(arguments.config), arguments.output,
        conditions=conditions, pool_sizes=pool_sizes, sample_sizes=sample_sizes, strengths=strengths,
        batches=batches, write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
