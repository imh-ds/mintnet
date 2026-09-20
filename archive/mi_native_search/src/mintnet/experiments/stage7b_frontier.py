"""Deterministic raw-evidence runner for the frozen Stage 7b power-
curve/operating-frontier mapping. See docs/stage7b_charter.md.

Unlike `mintnet.experiments.stage7_isolation`, raw evidence here stores
each replicate's own p-values ONCE (not exploded per `alpha`) -- the
charter's own 50-value alpha grid is applied entirely at reporting
time by re-thresholding this same stored evidence, since the number of
alpha values considered here (50) makes an exploded per-alpha raw
schema needlessly large for no benefit (nothing about raw-evidence
storage needs to fix the alpha grid in advance the way computing it
would).

Resolved design, per the charter's own "Compute-cost disclosure"
section and this session's own direct N=3000 timing measurement
(single significance test: ~48s; full 3-pair replicate: ~137-193s,
averaging ~157s -- confirms worse-than-linear scaling from N=1500's
own ~69s/replicate): `replicates=400` (the charter's own provisional
range's upper bound), `batch_size=50` (sized against the N=3000 worst
case: 50 x 157s ~= 2.2h per shard, safely under GitHub Actions' 6-hour
job timeout). Total shards for the full grid: `9 target_rho values x 3
N values x 8 batches = 216`, under the 256-job matrix cap -- fits in a
single dispatch, no multi-dispatch tooling needed.
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

from mintnet.dpi.cmi_conditional import compute_cmi_conditional_independence_evidence
from mintnet.simulation.motifs import sample_weak_edge_triangle


@dataclass(frozen=True)
class Stage7bConfig:
    target_rhos: tuple[float, ...]
    sample_sizes: tuple[int, ...]
    replicates: int
    batch_size: int
    k_cmi: int
    k_perm: int
    permutations: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage7bConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7b configuration must be a mapping")
    return Stage7bConfig(
        target_rhos=_values(values, "target_rhos", float),
        sample_sizes=_values(values, "sample_sizes", int),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        k_cmi=int(values["k_cmi"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("target_rho", "n", "replicate")


def _n_batches(config: Stage7bConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7bConfig) -> set[tuple[float, int, int]]:
    return {
        (target_rho, n, replicate)
        for target_rho in config.target_rhos
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage7bConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(master_seed: int, rho_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, rho_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(target_rho: float, n: int, replicate: int, config: Stage7bConfig) -> dict[str, object]:
    rho_index = config.target_rhos.index(target_rho)
    sample_index = config.sample_sizes.index(n)
    seed = _condition_seed(config.master_seed, rho_index, sample_index, replicate)

    row: dict[str, object] = {
        "target_rho": target_rho, "n": n, "replicate": replicate, "seed": seed,
        "status": "ok", "error": "",
        "cmi_01": np.nan, "cmi_02": np.nan, "cmi_12": np.nan,
        "p_value_01": np.nan, "p_value_02": np.nan, "p_value_12": np.nan,
        "elapsed_seconds": np.nan,
    }
    started = time.perf_counter()
    try:
        data = sample_weak_edge_triangle(target_rho, n, np.random.default_rng(seed))
        evidence = compute_cmi_conditional_independence_evidence(
            data,
            seed_context=(config.master_seed, rho_index, sample_index, replicate),
            k_cmi=config.k_cmi, k_perm=config.k_perm, permutations=config.permutations,
        )
        row["cmi_01"] = float(evidence.cmi[0, 1])
        row["cmi_02"] = float(evidence.cmi[0, 2])
        row["cmi_12"] = float(evidence.cmi[1, 2])
        row["p_value_01"] = float(evidence.p_value[0, 1])
        row["p_value_02"] = float(evidence.p_value[0, 2])
        row["p_value_12"] = float(evidence.p_value[1, 2])
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
    "target_rho", "n", "replicate", "seed", "status", "error",
    "cmi_01", "cmi_02", "cmi_12", "p_value_01", "p_value_02", "p_value_12", "elapsed_seconds",
)


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7bConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "target_rhos": list(config.target_rhos), "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates, "batch_size": config.batch_size,
        "k_cmi": config.k_cmi, "k_perm": config.k_perm, "permutations": config.permutations,
        "master_seed": config.master_seed,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7b_charter.md"
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


def run_stage7b(
    config: Stage7bConfig,
    output_dir: Path,
    target_rhos: tuple[float, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`target_rhos`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- replicate ranges are derived from
    `config.batch_size` against the full replicate count, and seeds
    key off `config.target_rhos.index(...)`/`config.sample_sizes.
    index(...)`/`replicate` (all full-grid quantities), so a shard's
    results match an unsharded run's for the same replicates."""
    started = time.perf_counter()
    target_rho_values = target_rhos if target_rhos is not None else config.target_rhos
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for target_rho in target_rho_values:
        for n in target_sizes:
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.append(_run_one_replicate(target_rho, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7b_frontier_reporting import write_report as write_stage7b_report

    write_stage7b_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--target-rhos", type=str, default=None, help="comma-separated subset of target_rho values (default: all)"
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--batches", type=str, default=None, help="comma-separated subset of batch indices (default: all)"
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    target_rhos = tuple(float(v) for v in arguments.target_rhos.split(",")) if arguments.target_rhos else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    batches = tuple(int(v) for v in arguments.batches.split(",")) if arguments.batches else None

    run_stage7b(
        load_config(arguments.config), arguments.output,
        target_rhos=target_rhos, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
