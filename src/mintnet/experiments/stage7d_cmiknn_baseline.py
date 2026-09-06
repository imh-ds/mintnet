"""Deterministic raw-evidence runner for the frozen Stage 7d CMIknn
baseline re-run. See docs/stage7d_charter.md.

The charter requires the CMIknn comparison baseline to be re-run on
the *same* new curvature/U-shape DGPs (`mintnet.experiments.
stage7d_conditions`), not reused from D-060/D-061's own linear-only
evidence. Fixed at `k_CMI=80`/`k_perm=3` (D-061's own recommended
default) -- no sweep here, unlike the structured-density side's own
`degree` sweep.

**Replicates deliberately reduced to `R=100`** (not 400, matching the
structured-density side): CMIknn's own per-replicate cost dwarfs the
structured-density estimator's (measured directly this session: ~62s
at `N=3000` vs ~11s, roughly 5-6x for this single-pair scope), so a
full-grid `R=400` re-run would make this baseline comparison a
disproportionate share of the whole charter's cost, for a role
(comparison baseline, not the object of the charter's own calibration
question) that doesn't need Stage 7c's own precision. `R=100` still
gives Wilson-CI-defensible calibration/power estimates.

Resolved design, per this session's own direct timing measurement (a
single-pair significance test at `k_CMI=80`, matching this runner's own
weak-edge-only scope -- all 13 conditions being cost-equivalent since
CMIknn's own runtime depends on `N`/`k`, not the specific DGP, per
Stage 7c's own established finding, reconfirmed here on both a linear
and a U-shape fixture at `N=3000`): `7.4s`/`21.4s`/`61.6s` at
`N=750`/`1500`/`3000`. `batch_size=100` (a single batch: worst case,
`N=3000`: `100 x 61.6s ~= 1.71h`, safely under the 6-hour job timeout,
so no further batching is needed). `condition` (13) crossed with `N`
(3): `13 x 3 = 39` shards, well under the 256-job matrix cap. Projected
total single-threaded cost: ~32.6 hours (13 conditions x 100 replicates
x the summed per-N cost above), heavily shardable across the 39 cells.
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

from mintnet.experiments.stage7d_conditions import all_conditions, sample_condition
from mintnet.mi.cmiknn import local_permutation_test


@dataclass(frozen=True)
class Stage7dCmiknnBaselineConfig:
    sample_sizes: tuple[int, ...]
    replicates: int
    batch_size: int
    k_cmi: int
    k_perm: int
    permutations: int
    master_seed: int
    source_path: Path | None = None


def load_config(path: Path) -> Stage7dCmiknnBaselineConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7d CMIknn-baseline configuration must be a mapping")
    return Stage7dCmiknnBaselineConfig(
        sample_sizes=tuple(int(v) for v in values["sample_sizes"]),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        k_cmi=int(values["k_cmi"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("condition", "n", "replicate")


def _n_batches(config: Stage7dCmiknnBaselineConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7dCmiknnBaselineConfig) -> set[tuple[str, int, int]]:
    return {
        (condition, n, replicate)
        for condition in all_conditions()
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage7dCmiknnBaselineConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(master_seed: int, condition_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, condition_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(condition: str, n: int, replicate: int, config: Stage7dCmiknnBaselineConfig) -> dict[str, object]:
    condition_index = all_conditions().index(condition)
    sample_index = config.sample_sizes.index(n)
    seed = _condition_seed(config.master_seed, condition_index, sample_index, replicate)

    row: dict[str, object] = {
        "condition": condition, "n": n, "replicate": replicate, "seed": seed,
        "status": "ok", "error": "", "cmi_12": np.nan, "p_value_12": np.nan, "elapsed_seconds": np.nan,
    }
    started = time.perf_counter()
    try:
        data = sample_condition(condition, n, np.random.default_rng(seed))
        x, y, z = data[:, 1], data[:, 2], data[:, 0]
        sequence = np.random.SeedSequence([config.master_seed, condition_index, sample_index, replicate])
        rng = np.random.default_rng(int(sequence.generate_state(1)[0]))
        result = local_permutation_test(
            x, y, z, k=config.k_cmi, k_perm=config.k_perm, permutations=config.permutations, rng=rng
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


_COLUMNS = ("condition", "n", "replicate", "seed", "status", "error", "cmi_12", "p_value_12", "elapsed_seconds")


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7dCmiknnBaselineConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "sample_sizes": list(config.sample_sizes), "replicates": config.replicates, "batch_size": config.batch_size,
        "k_cmi": config.k_cmi, "k_perm": config.k_perm, "permutations": config.permutations,
        "master_seed": config.master_seed,
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


def run_stage7d_cmiknn_baseline(
    config: Stage7dCmiknnBaselineConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard. Replicate ranges are derived from
    `config.batch_size` against the full replicate count, and seeds key
    off full-grid indices (`all_conditions().index(...)`,
    `config.sample_sizes.index(...)`, `replicate`), so a shard's results
    match an unsharded run's."""
    started = time.perf_counter()
    target_conditions = conditions if conditions is not None else all_conditions()
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        for n in target_sizes:
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.append(_run_one_replicate(condition, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7d_cmiknn_baseline_reporting import write_report as write_stage7d_baseline_report

    write_stage7d_baseline_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None, help="comma-separated subset of condition labels (default: all)"
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

    run_stage7d_cmiknn_baseline(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
