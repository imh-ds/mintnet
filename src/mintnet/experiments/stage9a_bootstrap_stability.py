"""Deterministic, shardable raw-evidence runner for the frozen Stage 9a
Tier-1 bootstrap-stability diagnostic. See docs/stage9a_charter.md.

Reuses Stage 8c's own exact base-data seed formula (`stage5a._condition
_seed`/`_DGP_REGISTRY`, the same `base_master_seed` Stage 8c's own real
config uses) so every replicate's own underlying `p=15` data is
bit-identical to what Stage 8c already generated -- this module does
not re-derive Stage 8c's own raw evidence from a downloaded CSV, it
regenerates the same deterministic data directly and re-runs the same
point-estimate decision (screening + `growing_subset_dpi`) fresh, which
is cheap (~11-14ms/replicate, per Stage 8c's own measurement).

**Row unit is one replicate**, exactly mirroring `stage8c_composed_
calibration.py`'s own "data-dependent candidate count" solution: a
replicate's own qualifying edges (`conditioning_size_used >= 2`) are
embedded as a JSON sub-table in one column, keeping `expected_row_count`
/`expected_combinations` knowable from config alone.

**Compute-efficient design (disclosed simplification from the charter's
own per-edge cost estimate, made cheaper, not more expensive, at
implementation time)**: `compute_edge_stability_growing_subset` already
computes the FULL `p x p` `pi_final` matrix in one `B`-resample pass --
a replicate with multiple qualifying edges pays the `B=500` bootstrap
cost only ONCE, not once per edge. Only replicates containing at least
one qualifying edge ever pay this cost at all; the ~98% of replicates
with none only pay the cheap point-estimate check.

**Cap is enforced per-cell across the FULL replicate range, not per
batch** -- `run_stage9a` always processes a selected `(dgp, n)` cell's
entire `0..replicates-1` range in one pass (no `batches` parameter, a
deliberate departure from Stage 8a/8c's own convention), because the
cap ("stop paying the bootstrap cost after `max_bootstrapped_
replicates_per_cell` qualifying replicates") is inherently sequential
within a cell; splitting it across independently-scheduled shards would
make the cap's own outcome depend on shard-ordering. Sharding is by
`(dgp, n)` only (`14` shards at Stage 8c's own real grid).
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

from mintnet.bootstrap import compute_edge_stability_growing_subset
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage5a import _DGP_REGISTRY as _COMPOSED_DGP_REGISTRY
from mintnet.experiments.stage5a import _condition_seed
from mintnet.experiments.stage5a import _true_adjacency
from mintnet.experiments.stage8c_composed_calibration import COMPOSED_SHAPES
from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

CATEGORIES: tuple[str, ...] = ("true_retained", "false_wrongly_retained", "false_correctly_pruned")


def _category(is_true_edge: bool, retained: bool) -> str:
    if is_true_edge:
        return "true_retained" if retained else "true_wrongly_pruned"
    return "false_wrongly_retained" if retained else "false_correctly_pruned"


@dataclass(frozen=True)
class Stage9aConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha: float
    max_conditioning_size: int
    replicates: int
    base_master_seed: int
    bootstrap_master_seed: int
    bootstraps: int
    max_bootstrapped_replicates_per_cell: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage9aConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 9a configuration must be a mapping")
    return Stage9aConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        screening_alpha=float(values["screening_alpha"]),
        max_conditioning_size=int(values["max_conditioning_size"]),
        replicates=int(values["replicates"]),
        base_master_seed=int(values["base_master_seed"]),
        bootstrap_master_seed=int(values["bootstrap_master_seed"]),
        bootstraps=int(values["bootstraps"]),
        max_bootstrapped_replicates_per_cell=int(values["max_bootstrapped_replicates_per_cell"]),
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("dgp", "n", "replicate")


def expected_combinations(config: Stage9aConfig) -> set[tuple[str, int, int]]:
    return {
        (dgp, n, replicate)
        for dgp in COMPOSED_SHAPES
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage9aConfig) -> int:
    return len(expected_combinations(config))


def _repository_root(config: Stage9aConfig) -> Path:
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


def _resolved_config(config: Stage9aConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "screening_alpha": config.screening_alpha,
        "max_conditioning_size": config.max_conditioning_size,
        "replicates": config.replicates,
        "base_master_seed": config.base_master_seed,
        "bootstrap_master_seed": config.bootstrap_master_seed,
        "bootstraps": config.bootstraps,
        "max_bootstrapped_replicates_per_cell": config.max_bootstrapped_replicates_per_cell,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
    }


def _write_evidence(config: Stage9aConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage9a_charter.md"
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


def _bootstrap_seed(config: Stage9aConfig, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.bootstrap_master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    dgp: str, dgp_index: int, n: int, sample_index: int, replicate: int, alpha: float,
    bootstrapped_so_far: int, config: Stage9aConfig,
) -> dict[str, object]:
    entry = _COMPOSED_DGP_REGISTRY[dgp]
    sample: Callable = entry["sample"]  # type: ignore[assignment]
    p = int(entry["p"])
    truth = _true_adjacency(entry["true_edges"], p)  # type: ignore[arg-type]
    seed = _condition_seed(config.base_master_seed, dgp_index, sample_index, replicate)

    started = time.perf_counter()
    qualifying: list[dict[str, object]] = []
    status, error = "ok", ""
    try:
        data = sample(n, config.strength, np.random.default_rng(seed))
        evidence = compute_pairwise_screening_evidence(data)
        flagged = screen_uncorrected(evidence, config.screening_alpha)
        result = growing_subset_dpi(
            data, flagged, alpha, max_conditioning_size=config.max_conditioning_size, motif_family=None
        )

        pairs: list[tuple[int, int]] = []
        for i in range(p):
            for j in range(i + 1, p):
                if flagged[i, j] and result.conditioning_size_used[(i, j)] >= 2:
                    pairs.append((i, j))

        will_bootstrap = bool(pairs) and bootstrapped_so_far < config.max_bootstrapped_replicates_per_cell
        stability = None
        if will_bootstrap:
            stability = compute_edge_stability_growing_subset(
                data, config.screening_alpha, alpha, config.max_conditioning_size, config.bootstraps,
                np.random.default_rng(_bootstrap_seed(config, dgp_index, sample_index, replicate)),
            )

        for i, j in pairs:
            retained = bool(result.adjacency[i, j])
            is_true_edge = bool(truth[i, j])
            qualifying.append(
                {
                    "i": i, "j": j, "is_true_edge": is_true_edge, "retained": retained,
                    "category": _category(is_true_edge, retained),
                    "conditioning_size_used": int(result.conditioning_size_used[(i, j)]),
                    "decisive_p_value": float(result.decisive_p_value[(i, j)]),
                    "bootstrapped": will_bootstrap,
                    "pi_final": float(stability.pi_final[i, j]) if stability is not None else None,
                    "successful_bootstraps": stability.successful_bootstraps if stability is not None else None,
                    "failed_bootstraps": stability.failed_bootstraps if stability is not None else None,
                }
            )
    except Exception as exc:  # raw evidence must retain pipeline failures
        status, error = "error", f"{type(exc).__name__}: {exc}"

    return {
        "dgp": dgp, "n": n, "alpha": alpha, "replicate": replicate, "seed": seed,
        "qualifying_json": json.dumps(qualifying), "n_qualifying": len(qualifying),
        "elapsed_seconds": time.perf_counter() - started, "status": status, "error": error,
    }


def run_stage9a(
    config: Stage9aConfig,
    output_dir: Path,
    dgps: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`dgps`/`sample_sizes` restrict which cells run, for a single-cell
    CI shard -- each selected `(dgp, n)` cell always processes its own
    FULL `0..replicates-1` range in order (no `batches` restriction, see
    this module's own docstring on why the bootstrap cap requires this),
    so a shard's own results match an unsharded run's exactly for the
    cells it covers."""
    run_started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_dgps = dgps if dgps is not None else COMPOSED_SHAPES
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes

    rows: list[dict[str, object]] = []
    for dgp in target_dgps:
        dgp_index = COMPOSED_SHAPES.index(dgp)
        for n in target_sizes:
            sample_index = config.sample_sizes.index(n)
            alpha = float(alpha_formula.predict(float(n)))
            bootstrapped_so_far = 0
            for replicate in range(config.replicates):
                row = _run_one_replicate(dgp, dgp_index, n, sample_index, replicate, alpha, bootstrapped_so_far, config)
                if any(edge["bootstrapped"] for edge in json.loads(row["qualifying_json"])):
                    bootstrapped_so_far += 1
                rows.append(row)

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if write_report:
        from mintnet.experiments.stage9a_bootstrap_stability_reporting import write_report as write_stage9a_report

        write_stage9a_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dgps", type=str, default=None, help="comma-separated subset of DGPs (default: all)")
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    dgps = tuple(arguments.dgps.split(",")) if arguments.dgps else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None

    run_stage9a(
        load_config(arguments.config), arguments.output,
        dgps=dgps, sample_sizes=sample_sizes, write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
