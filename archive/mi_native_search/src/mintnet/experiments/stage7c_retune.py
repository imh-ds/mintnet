"""Deterministic raw-evidence runner for the frozen Stage 7c estimator-
retuning experiment. See docs/stage7c_charter.md.

Sweeps `k_CMI` (k_perm=3 held fixed) against the four most diagnostic
`target_rho` points from Stage 7b/D-060, computing ONLY the weak-edge
`(1, 2)` pair per replicate (the two dominant edges' own near-certain
retention is not in question here -- a disclosed ~3x cost reduction
from Stage 7b's own full-evidence approach).

Resolved design, per this session's own direct timing measurement at
the grid's own k_CMI extremes (10 and 100) at N=3000 -- confirming
cost is NOT k-invariant (27.1s at k=10, 48.2s at k=40, 68.9s at k=100,
per single-pair significance test): `replicates=400`, `batch_size=200`
(worst case k=100/N=3000: 200 x 68.9s ~= 3.83h per shard, safely under
GitHub Actions' 6-hour job timeout). `(k_cmi, target_rho)` combined
into one composite shard label (28 combinations) crossed with `N` (3)
and `batch` (2): `28 x 3 x 2 = 168` shards, under the 256-job matrix
cap -- fits a single dispatch.
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

from mintnet.mi.cmiknn import local_permutation_test
from mintnet.simulation.motifs import sample_weak_edge_triangle


@dataclass(frozen=True)
class Stage7cConfig:
    k_cmis: tuple[int, ...]
    target_rhos: tuple[float, ...]
    sample_sizes: tuple[int, ...]
    replicates: int
    batch_size: int
    k_perm: int
    permutations: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage7cConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7c configuration must be a mapping")
    return Stage7cConfig(
        k_cmis=_values(values, "k_cmis", int),
        target_rhos=_values(values, "target_rhos", float),
        sample_sizes=_values(values, "sample_sizes", int),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


def condition_label(k_cmi: int, target_rho: float) -> str:
    return f"k{k_cmi}_rho{target_rho}"


def _parse_condition(condition: str) -> tuple[int, float]:
    k_part, rho_part = condition.split("_rho")
    return int(k_part[1:]), float(rho_part)


def all_conditions(config: Stage7cConfig) -> tuple[str, ...]:
    return tuple(condition_label(k, rho) for k in config.k_cmis for rho in config.target_rhos)


COMBINATION_COLUMNS: tuple[str, ...] = ("k_cmi", "target_rho", "n", "replicate")


def _n_batches(config: Stage7cConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7cConfig) -> set[tuple[int, float, int, int]]:
    return {
        (k_cmi, target_rho, n, replicate)
        for k_cmi in config.k_cmis
        for target_rho in config.target_rhos
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage7cConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(master_seed: int, k_index: int, rho_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, k_index, rho_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(k_cmi: int, target_rho: float, n: int, replicate: int, config: Stage7cConfig) -> dict[str, object]:
    k_index = config.k_cmis.index(k_cmi)
    rho_index = config.target_rhos.index(target_rho)
    sample_index = config.sample_sizes.index(n)
    seed = _condition_seed(config.master_seed, k_index, rho_index, sample_index, replicate)

    row: dict[str, object] = {
        "k_cmi": k_cmi, "target_rho": target_rho, "n": n, "replicate": replicate, "seed": seed,
        "status": "ok", "error": "", "cmi_12": np.nan, "p_value_12": np.nan, "elapsed_seconds": np.nan,
    }
    started = time.perf_counter()
    try:
        data = sample_weak_edge_triangle(target_rho, n, np.random.default_rng(seed))
        x, y, z = data[:, 1], data[:, 2], data[:, 0]
        sequence = np.random.SeedSequence([config.master_seed, k_index, rho_index, sample_index, replicate])
        rng = np.random.default_rng(int(sequence.generate_state(1)[0]))
        result = local_permutation_test(x, y, z, k=k_cmi, k_perm=config.k_perm, permutations=config.permutations, rng=rng)
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


_COLUMNS = ("k_cmi", "target_rho", "n", "replicate", "seed", "status", "error", "cmi_12", "p_value_12", "elapsed_seconds")


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7cConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "k_cmis": list(config.k_cmis), "target_rhos": list(config.target_rhos),
        "sample_sizes": list(config.sample_sizes), "replicates": config.replicates,
        "batch_size": config.batch_size, "k_perm": config.k_perm, "permutations": config.permutations,
        "master_seed": config.master_seed,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7c_charter.md"
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


def run_stage7c(
    config: Stage7cConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- `conditions` are `condition_label(k,
    rho)` strings, decoded back to `(k_cmi, target_rho)`. Replicate
    ranges are derived from `config.batch_size` against the full
    replicate count, and seeds key off `config.k_cmis.index(...)`/
    `config.target_rhos.index(...)`/`config.sample_sizes.index(...)`/
    `replicate` (all full-grid quantities), so a shard's results match
    an unsharded run's for the same replicates."""
    started = time.perf_counter()
    target_conditions = conditions if conditions is not None else all_conditions(config)
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        k_cmi, target_rho = _parse_condition(condition)
        for n in target_sizes:
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.append(_run_one_replicate(k_cmi, target_rho, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7c_retune_reporting import write_report as write_stage7c_report

    write_stage7c_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None,
        help="comma-separated subset of condition labels (e.g. k10_rho0.08; default: all)",
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

    run_stage7c(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
