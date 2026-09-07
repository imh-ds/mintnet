"""Shardable raw-evidence runner for the frozen Stage 8c composed-tier
margin-calibration transfer check. See docs/stage8c_charter.md.

Reuses Stage 6a's own composed-tier pipeline unchanged (D-053):
`stage5a`'s DGP registry/seed derivation/ground truth, `screen_
uncorrected` to build the candidate graph, `growing_subset_dpi`
(`motif_family=None` -- raw margin only, since a composed network's
edges carry no motif-family label D-067's own chain/fork curve could
validly apply to; see growing_subset_dpi's own docstring).

**Row unit is one replicate, not one edge.** Stage 8a's own fixed
3-node fixtures had a known, enumerable edge set from config alone
(`0-1`/`0-2`/`1-2`), which is what let it use `aggregate_shards.py`'s
generic shard-completeness contract directly. A composed p=15
network's own candidate edges are decided by screening -- genuinely
data-dependent, not enumerable from config -- so the same contract
cannot be applied at edge granularity here. Keeping the row unit at
the replicate level (fixed, one row per (dgp, n, replicate) always,
regardless of how many candidates that replicate's own screening
produced) preserves the existing generic contract unmodified; that
replicate's own edges are embedded as a JSON sub-table in one column
and exploded back out by stage8c_composed_calibration_reporting.
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

from mintnet.confidence.margin import edge_margin
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage5a import _DGP_REGISTRY as _COMPOSED_DGP_REGISTRY
from mintnet.experiments.stage5a import _condition_seed
from mintnet.experiments.stage5a import _true_adjacency
from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

COMPOSED_SHAPES: tuple[str, ...] = ("chain_fork_hub", "overlap")


@dataclass(frozen=True)
class Stage8cConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha: float
    max_conditioning_size: int
    replicates: int
    batch_size: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    ece_tolerance: float
    bin_count: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage8cConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 8c configuration must be a mapping")
    return Stage8cConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        screening_alpha=float(values["screening_alpha"]),
        max_conditioning_size=int(values["max_conditioning_size"]),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        ece_tolerance=float(values["ece_tolerance"]),
        bin_count=int(values["bin_count"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("dgp", "n", "replicate")


def _n_batches(config: Stage8cConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage8cConfig) -> set[tuple[str, int, int]]:
    return {
        (dgp, n, replicate)
        for dgp in COMPOSED_SHAPES
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage8cConfig) -> int:
    return len(expected_combinations(config))


def _repository_root(config: Stage8cConfig) -> Path:
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


def _resolved_config(config: Stage8cConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "screening_alpha": config.screening_alpha,
        "max_conditioning_size": config.max_conditioning_size,
        "replicates": config.replicates,
        "batch_size": config.batch_size,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "ece_tolerance": config.ece_tolerance,
        "bin_count": config.bin_count,
    }


def _write_evidence(config: Stage8cConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage8c_charter.md"
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


def _run_one_replicate(dgp: str, dgp_index: int, n: int, sample_index: int, replicate: int, alpha: float, config: Stage8cConfig) -> dict[str, object]:
    entry = _COMPOSED_DGP_REGISTRY[dgp]
    sample: Callable = entry["sample"]  # type: ignore[assignment]
    p = int(entry["p"])
    truth = _true_adjacency(entry["true_edges"], p)  # type: ignore[arg-type]
    seed = _condition_seed(config.master_seed, dgp_index, sample_index, replicate)

    started = time.perf_counter()
    edges: list[dict[str, object]] = []
    try:
        data = sample(n, config.strength, np.random.default_rng(seed))
        evidence = compute_pairwise_screening_evidence(data)
        flagged = screen_uncorrected(evidence, config.screening_alpha)
        result = growing_subset_dpi(
            data, flagged, alpha, max_conditioning_size=config.max_conditioning_size, motif_family=None
        )
        for i in range(p):
            for j in range(i + 1, p):
                if not flagged[i, j]:
                    continue
                p_value = float(result.decisive_p_value[(i, j)])
                retained = bool(result.adjacency[i, j])
                is_true_edge = bool(truth[i, j])
                margin = edge_margin(p_value, alpha, retained=retained)
                edges.append(
                    {
                        "i": i, "j": j, "is_true_edge": is_true_edge,
                        "decisive_p_value": p_value, "margin": margin, "retained": retained,
                        "correct": bool(retained == is_true_edge),
                    }
                )
        status, error = "ok", ""
    except Exception as exc:  # raw evidence must retain pipeline failures
        status, error = "error", f"{type(exc).__name__}: {exc}"

    return {
        "dgp": dgp, "n": n, "alpha": alpha, "replicate": replicate, "seed": seed,
        "edges_json": json.dumps(edges), "n_edges": len(edges),
        "elapsed_seconds": time.perf_counter() - started, "status": status, "error": error,
    }


def run_stage8c(
    config: Stage8cConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- replicate ranges are always derived
    from `config.batch_size` against the FULL replicate count, and
    seeds key off `COMPOSED_SHAPES.index(...)`/`config.sample_sizes.
    index(...)`/`replicate` (all full-grid quantities), so a shard's
    results match an unsharded run's for the same replicates."""
    run_started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_dgps = conditions if conditions is not None else COMPOSED_SHAPES
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for dgp in target_dgps:
        dgp_index = COMPOSED_SHAPES.index(dgp)
        for n in target_sizes:
            sample_index = config.sample_sizes.index(n)
            alpha = float(alpha_formula.predict(float(n)))
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.append(_run_one_replicate(dgp, dgp_index, n, sample_index, replicate, alpha, config))

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if write_report:
        from mintnet.experiments.stage8c_composed_calibration_reporting import write_report as write_stage8c_report

        write_stage8c_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None, help="comma-separated subset of DGPs (default: all)"
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

    run_stage8c(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
