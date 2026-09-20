"""Deterministic, shardable raw-evidence runner for the frozen Stage 9c
charter: adapting bootstrap-rescue to the structured-density engine.
See docs/stage9c_charter.md.

**Cost profile is fundamentally different from Stage 9a's own (Fisher-z)
design, which this module otherwise mirrors closely.** A single
structured-density search is itself expensive (D-085's own measured
`40s`-`264s` typical, with a heavy tail up to multiple hours per
replicate) -- bootstrapping means paying that cost once per resample,
not once per replicate. Two DGP-specific consequences, both handled by
`--replicate-range` chunking (Stage 9b's own precedent, cap tracked
FRESH per chunk, not shared globally):

- `overlap` qualifies (has >=1 edge at `conditioning_size_used >= 2`)
  at essentially 100% of replicates (measured directly from Stage 7h's
  own evidence) -- a chunk must be tiny (as small as 1 replicate) or
  every replicate in it pays the full bootstrap cost.
- `chain_fork_hub` qualifies at only ~7.4% of replicates -- a chunk can
  be much larger (most replicates are cheap point-estimate checks
  only), needed to reach the per-cell bootstrap cap at all within a
  reasonable number of shards.

Records raw `pi_final` per qualifying edge (not a final rescued
decision) -- `pi_min` is calibrated fresh at report time (Step 3),
not inherited from D-079's own Fisher-z-tuned value, since a much
smaller `bootstraps` (`B`) here makes `pi_final` a coarser statistic.
Calls `growing_subset_dpi_structured_density_with_stability_rescue`
(the actual wired function, per this charter's own Step 4) with a
placeholder `pi_min` used only to decide `bootstrapped`/produce
`pi_final` -- irrelevant to the recorded `pi_final` value itself, which
is what Step 3's own calibration and Step 4's own recall/removal
evaluation both use directly.
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
from mintnet.pipeline.growing_subset_dpi_structured_density import growing_subset_dpi_structured_density
from mintnet.pipeline.stability_rescue import growing_subset_dpi_structured_density_with_stability_rescue

_PLACEHOLDER_PI_MIN = 0.5  # irrelevant to the recorded pi_final; only affects the unused "rescued" field


def _category(is_true_edge: bool, retained: bool) -> str:
    if is_true_edge:
        return "true_retained" if retained else "true_wrongly_pruned"
    return "false_wrongly_retained" if retained else "false_correctly_pruned"


@dataclass(frozen=True)
class Stage9cConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha: float
    max_conditioning_size: int
    degree: int
    ridge_lambda: float
    cv_folds: int
    k_perm: int
    permutations: int
    replicates: int
    base_master_seed: int
    bootstrap_master_seed: int
    bootstraps: int
    max_bootstrapped_replicates_per_cell: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage9cConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 9c configuration must be a mapping")
    return Stage9cConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        screening_alpha=float(values["screening_alpha"]),
        max_conditioning_size=int(values["max_conditioning_size"]),
        degree=int(values["degree"]),
        ridge_lambda=float(values["ridge_lambda"]),
        cv_folds=int(values["cv_folds"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        replicates=int(values["replicates"]),
        base_master_seed=int(values["base_master_seed"]),
        bootstrap_master_seed=int(values["bootstrap_master_seed"]),
        bootstraps=int(values["bootstraps"]),
        max_bootstrapped_replicates_per_cell=int(values["max_bootstrapped_replicates_per_cell"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("dgp", "n", "replicate")


def expected_combinations(config: Stage9cConfig) -> set[tuple[str, int, int]]:
    return {
        (dgp, n, replicate)
        for dgp in COMPOSED_SHAPES
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage9cConfig) -> int:
    return len(expected_combinations(config))


def _base_seed(config: Stage9cConfig, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.base_master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _bootstrap_seed(config: Stage9cConfig, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.bootstrap_master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    dgp: str, dgp_index: int, n: int, sample_index: int, replicate: int, alpha: float,
    bootstrapped_so_far: int, config: Stage9cConfig,
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

        # A cheap point-estimate-only pass first to know whether this
        # replicate even qualifies, before deciding whether to pay the
        # (potentially very expensive) bootstrap cost at all.
        from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

        evidence = compute_pairwise_screening_evidence(data)
        flagged = screen_uncorrected(evidence, config.screening_alpha)
        point_estimate = growing_subset_dpi_structured_density(
            data, flagged, alpha, master_seed=config.base_master_seed, replicate=replicate,
            degree=config.degree, ridge_lambda=config.ridge_lambda, cv_folds=config.cv_folds,
            k_perm=config.k_perm, permutations=config.permutations, max_conditioning_size=config.max_conditioning_size,
        )
        pairs: list[tuple[int, int]] = [
            (i, j)
            for i in range(p) for j in range(i + 1, p)
            if flagged[i, j] and point_estimate.conditioning_size_used[(i, j)] >= 2
        ]
        will_bootstrap = bool(pairs) and bootstrapped_so_far < config.max_bootstrapped_replicates_per_cell

        if will_bootstrap:
            result = growing_subset_dpi_structured_density_with_stability_rescue(
                data, flagged, alpha, max_conditioning_size=config.max_conditioning_size,
                screening_alpha=config.screening_alpha, bootstraps=config.bootstraps,
                pi_min=_PLACEHOLDER_PI_MIN, master_seed=config.base_master_seed, replicate=replicate,
                degree=config.degree, ridge_lambda=config.ridge_lambda, cv_folds=config.cv_folds,
                k_perm=config.k_perm, permutations=config.permutations,
                bootstrap_rng=np.random.default_rng(_bootstrap_seed(config, dgp_index, sample_index, replicate)),
                n_jobs="auto",
            )
            adjacency = result.original_adjacency
            pi_final_lookup = result.pi_final
        else:
            adjacency = point_estimate.adjacency
            pi_final_lookup = {}

        for i, j in pairs:
            retained = bool(adjacency[i, j])
            is_true_edge = bool(truth[i, j])
            pi_final = pi_final_lookup.get((i, j))
            qualifying.append(
                {
                    "i": i, "j": j, "is_true_edge": is_true_edge, "retained": retained,
                    "category": _category(is_true_edge, retained),
                    "conditioning_size_used": int(point_estimate.conditioning_size_used[(i, j)]),
                    "bootstrapped": will_bootstrap,
                    "pi_final": float(pi_final) if pi_final is not None and not np.isnan(pi_final) else None,
                }
            )
    except Exception as exc:  # raw evidence must retain pipeline failures
        status, error = "error", f"{type(exc).__name__}: {exc}"

    return {
        "dgp": dgp, "n": n, "alpha": alpha, "replicate": replicate, "seed": seed,
        "qualifying_json": json.dumps(qualifying), "n_qualifying": len(qualifying),
        "dataset_bootstrapped": bool(qualifying) and any(q["bootstrapped"] for q in qualifying),
        "elapsed_seconds": time.perf_counter() - started, "status": status, "error": error,
    }


def _repository_root(config: Stage9cConfig) -> Path:
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


def _write_evidence(config: Stage9cConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "sample_sizes": list(config.sample_sizes), "strength": config.strength,
        "screening_alpha": config.screening_alpha, "max_conditioning_size": config.max_conditioning_size,
        "degree": config.degree, "ridge_lambda": config.ridge_lambda, "cv_folds": config.cv_folds,
        "k_perm": config.k_perm, "permutations": config.permutations, "replicates": config.replicates,
        "base_master_seed": config.base_master_seed, "bootstrap_master_seed": config.bootstrap_master_seed,
        "bootstraps": config.bootstraps,
        "max_bootstrapped_replicates_per_cell": config.max_bootstrapped_replicates_per_cell,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage9c_charter.md"
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


def run_stage9c(
    config: Stage9cConfig,
    output_dir: Path,
    dgps: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    replicate_range: tuple[int, int] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`dgps`/`sample_sizes` restrict which cells run; `replicate_range`
    (inclusive) restricts which replicates within each cell run (default
    the full `0..replicates-1` range), each with its own freshly-started
    cap counter -- Stage 9b's own chunking semantics, needed here since
    `overlap`'s and `chain_fork_hub`'s own wildly different qualification
    rates require wildly different chunk sizes (see this module's own
    docstring)."""
    started = time.perf_counter()
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
    _write_evidence(config, output_dir, raw, time.perf_counter() - started)
    if write_report:
        from mintnet.experiments.stage9c_bootstrap_rescue_reporting import write_report as write_stage9c_report

        write_stage9c_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dgps", type=str, default=None, help="comma-separated subset of dgps (default: all)")
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--replicate-range", type=str, default=None, help="'start-end' inclusive (default: full 0..replicates-1)"
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    dgps = tuple(arguments.dgps.split(",")) if arguments.dgps else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    replicate_range = None
    if arguments.replicate_range:
        start_str, end_str = arguments.replicate_range.split("-")
        replicate_range = (int(start_str), int(end_str))

    run_stage9c(
        load_config(arguments.config), arguments.output,
        dgps=dgps, sample_sizes=sample_sizes, replicate_range=replicate_range,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
