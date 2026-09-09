"""Deterministic, shardable raw-evidence runner for the frozen Stage 9b
end-to-end stability-rescue validation. See docs/stage9b_charter.md.

Unlike every prior Stage 8/9 charter, this one draws entirely FRESH
replicates -- `base_master_seed`/`bootstrap_master_seed` below are new
values never used by any prior charter for these DGPs at this
`strength`, so this is not a re-analysis of already-scored evidence.

Calls `mintnet.pipeline.stability_rescue.growing_subset_dpi_with_
stability_rescue` directly (the actual wired function this charter
validates), not the individual pieces by hand -- the whole point is to
confirm the ONE function a caller would actually use reproduces
D-079's own retrospective numbers.

**Row unit is one replicate** (mirrors Stage 8c's/9a's own data-
dependent-candidate-count solution). **Bootstrap cost is bounded per
`(dgp, n)` cell by `max_bootstrapped_replicates_per_cell`, tracked
across whatever `replicate_range` a shard is given** (Stage 9a's own
`--replicate-range` mechanism, reused unchanged) -- no development/
validation split is needed here (this charter checks a FIXED, already-
selected `pi_min` against a tolerance, it does not calibrate a new
one), so each `(dgp, n)` cell needs only ONE cap-tracked pass, chunked
across multiple shards purely to bound each individual shard's own
wall-clock cost (Stage 9a's own hard-learned lesson: measure real,
thread-limited per-call cost before sizing any cap, and prefer many
small independently-capped chunks over one large sequential cap).
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

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage5a import _DGP_REGISTRY as _COMPOSED_DGP_REGISTRY
from mintnet.experiments.stage5a import _true_adjacency
from mintnet.experiments.stage8c_composed_calibration import COMPOSED_SHAPES
from mintnet.pipeline.stability_rescue import growing_subset_dpi_with_stability_rescue
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected


@dataclass(frozen=True)
class Stage9bConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha: float
    max_conditioning_size: int
    replicates: int
    base_master_seed: int
    bootstrap_master_seed: int
    bootstraps: int
    pi_min: float
    max_bootstrapped_replicates_per_cell: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage9bConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 9b configuration must be a mapping")
    return Stage9bConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        screening_alpha=float(values["screening_alpha"]),
        max_conditioning_size=int(values["max_conditioning_size"]),
        replicates=int(values["replicates"]),
        base_master_seed=int(values["base_master_seed"]),
        bootstrap_master_seed=int(values["bootstrap_master_seed"]),
        bootstraps=int(values["bootstraps"]),
        pi_min=float(values["pi_min"]),
        max_bootstrapped_replicates_per_cell=int(values["max_bootstrapped_replicates_per_cell"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("dgp", "n", "replicate")


def expected_combinations(config: Stage9bConfig) -> set[tuple[str, int, int]]:
    return {
        (dgp, n, replicate)
        for dgp in COMPOSED_SHAPES
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage9bConfig) -> int:
    return len(expected_combinations(config))


def _repository_root(config: Stage9bConfig) -> Path:
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


def _resolved_config(config: Stage9bConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "screening_alpha": config.screening_alpha,
        "max_conditioning_size": config.max_conditioning_size,
        "replicates": config.replicates,
        "base_master_seed": config.base_master_seed,
        "bootstrap_master_seed": config.bootstrap_master_seed,
        "bootstraps": config.bootstraps,
        "pi_min": config.pi_min,
        "max_bootstrapped_replicates_per_cell": config.max_bootstrapped_replicates_per_cell,
    }


def _write_evidence(config: Stage9bConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage9b_charter.md"
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


def _base_seed(config: Stage9bConfig, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.base_master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _bootstrap_seed(config: Stage9bConfig, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.bootstrap_master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    dgp: str, dgp_index: int, n: int, sample_index: int, replicate: int, alpha: float,
    bootstrapped_so_far: int, config: Stage9bConfig,
) -> dict[str, object]:
    entry = _COMPOSED_DGP_REGISTRY[dgp]
    sample: Callable = entry["sample"]  # type: ignore[assignment]
    p = int(entry["p"])
    truth = _true_adjacency(entry["true_edges"], p)  # type: ignore[arg-type]
    seed = _base_seed(config, dgp_index, sample_index, replicate)

    started = time.perf_counter()
    qualifying: list[dict[str, object]] = []
    status, error = "ok", ""
    try:
        data = sample(n, config.strength, np.random.default_rng(seed))
        evidence = compute_pairwise_screening_evidence(data)
        flagged = screen_uncorrected(evidence, config.screening_alpha)

        # Only spend the bootstrap budget if this replicate hasn't
        # already exhausted the cell's own cap -- pass bootstraps=0
        # equivalent by simply not calling the rescue path at all when
        # capped, falling back to a plain point-estimate check instead
        # (still cheap, still recorded, just never bootstrapped).
        if bootstrapped_so_far < config.max_bootstrapped_replicates_per_cell:
            result = growing_subset_dpi_with_stability_rescue(
                data, flagged, alpha, max_conditioning_size=config.max_conditioning_size, motif_family=None,
                screening_alpha=config.screening_alpha, bootstraps=config.bootstraps, pi_min=config.pi_min,
                rng=np.random.default_rng(_bootstrap_seed(config, dgp_index, sample_index, replicate)),
            )
        else:
            from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi

            base = growing_subset_dpi(
                data, flagged, alpha, max_conditioning_size=config.max_conditioning_size, motif_family=None
            )

            class _Unbootstrapped:
                original_adjacency = base.adjacency
                final_adjacency = base.adjacency
                conditioning_size_used = base.conditioning_size_used
                pi_final = {k: float("nan") for k in base.conditioning_size_used}
                rescued = {k: False for k in base.conditioning_size_used}
                bootstrapped = False

            result = _Unbootstrapped()

        for i in range(p):
            for j in range(i + 1, p):
                if not flagged[i, j]:
                    continue
                size = result.conditioning_size_used[(i, j)]
                if size < 2:
                    continue
                qualifying.append(
                    {
                        "i": i, "j": j, "is_true_edge": bool(truth[i, j]),
                        "original_retained": bool(result.original_adjacency[i, j]),
                        "final_retained": bool(result.final_adjacency[i, j]),
                        "conditioning_size_used": int(size),
                        "pi_final": result.pi_final[(i, j)],
                        "rescued": bool(result.rescued[(i, j)]),
                    }
                )
        dataset_bootstrapped = bool(result.bootstrapped)
    except Exception as exc:  # raw evidence must retain pipeline failures
        status, error = "error", f"{type(exc).__name__}: {exc}"
        dataset_bootstrapped = False

    return {
        "dgp": dgp, "n": n, "alpha": alpha, "replicate": replicate, "seed": seed,
        "qualifying_json": json.dumps(qualifying), "n_qualifying": len(qualifying),
        "dataset_bootstrapped": dataset_bootstrapped,
        "elapsed_seconds": time.perf_counter() - started, "status": status, "error": error,
    }


def run_stage9b(
    config: Stage9bConfig,
    output_dir: Path,
    dgps: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    replicate_range: tuple[int, int] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`dgps`/`sample_sizes` restrict which cells run; `replicate_range`
    restricts which replicates within each cell run (default the FULL
    `0..replicates-1` range), each with its own freshly-started cap
    counter -- see this module's own docstring for why bounding shard
    cost this way, not via `batches`, is the right lever here."""
    run_started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_dgps = dgps if dgps is not None else COMPOSED_SHAPES
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    start_replicate, end_replicate = replicate_range if replicate_range is not None else (0, config.replicates - 1)

    rows: list[dict[str, object]] = []
    for dgp in target_dgps:
        dgp_index = COMPOSED_SHAPES.index(dgp)
        for n in target_sizes:
            sample_index = config.sample_sizes.index(n)
            alpha = float(alpha_formula.predict(float(n)))
            bootstrapped_so_far = 0
            for replicate in range(start_replicate, end_replicate + 1):
                row = _run_one_replicate(dgp, dgp_index, n, sample_index, replicate, alpha, bootstrapped_so_far, config)
                if row["dataset_bootstrapped"]:
                    bootstrapped_so_far += 1
                rows.append(row)

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if write_report:
        from mintnet.experiments.stage9b_stability_rescue_validation_reporting import (
            write_report as write_stage9b_report,
        )

        write_stage9b_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dgps", type=str, default=None, help="comma-separated subset of DGPs (default: all)")
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--replicate-range", type=str, default=None,
        help="dash-separated inclusive replicate range, e.g. 0-199 (default: full 0..replicates-1)",
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    dgps = tuple(arguments.dgps.split(",")) if arguments.dgps else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    replicate_range = None
    if arguments.replicate_range:
        start_text, end_text = arguments.replicate_range.split("-")
        replicate_range = (int(start_text), int(end_text))

    run_stage9b(
        load_config(arguments.config), arguments.output,
        dgps=dgps, sample_sizes=sample_sizes, replicate_range=replicate_range, write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
