"""Deterministic, shardable raw-evidence runner for docs/stage9d_charter.md's
own localized (single-edge) bootstrap-rescue mechanism -- Steps 3-4,
reframed per this stage's own decision-log record (D-090): this
evaluates the localized mechanism entirely on its own merits (does it
correctly retain true edges and correctly drop false ones), not as a
comparison against the old full-repeat mechanism, which will never be
exposed through the public API and is archived, not benchmarked
against going forward.

Mirrors `stage9c_bootstrap_rescue.py`'s structure closely (same
shardable `--dgps`/`--sample-sizes`/`--replicate-range` contract, same
raw evidence schema) so the already-written calibration/validation
logic in `stage9c_bootstrap_rescue_reporting.py` (development/validation
split by replicate parity, `_PI_MIN_GRID`, `calibrate_and_validate_
per_cell`) is reused UNCHANGED rather than duplicated -- it operates
generically on the shared raw-evidence schema and has no Stage-9c-
specific assumption baked in.

The one structural difference from Stage 9c's own runner: the
localized mechanism needs `decisive_conditioning_set` from the point
estimate (Stage 9d's own addition to `StructuredDensityGrowingSubset
Result`) to know which frozen conditioning set to re-test each
qualifying edge against, and takes no `screening_alpha` (it never
re-screens). Because the localized mechanism's own per-replicate
bootstrap cost is cheap (seconds, not the old mechanism's hours),
`max_bootstrapped_replicates_per_cell` can be set far higher than
Stage 9c's own `10` -- the whole point of this mechanism existing.
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
from mintnet.experiments.stage9c_bootstrap_rescue_reporting import write_report as write_stage9c_style_report
from mintnet.pipeline.growing_subset_dpi_structured_density import growing_subset_dpi_structured_density
from mintnet.pipeline.stability_rescue import growing_subset_dpi_structured_density_with_localized_rescue

_PLACEHOLDER_PI_MIN = 0.5  # irrelevant to the recorded pi_final; only affects the unused "rescued" field


def _category(is_true_edge: bool, retained: bool) -> str:
    if is_true_edge:
        return "true_retained" if retained else "true_wrongly_pruned"
    return "false_wrongly_retained" if retained else "false_correctly_pruned"


@dataclass(frozen=True)
class Stage9dConfig:
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


def load_config(path: Path) -> Stage9dConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 9d configuration must be a mapping")
    return Stage9dConfig(
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


def expected_combinations(config: Stage9dConfig) -> set[tuple[str, int, int]]:
    return {
        (dgp, n, replicate)
        for dgp in COMPOSED_SHAPES
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage9dConfig) -> int:
    return len(expected_combinations(config))


def _base_seed(config: Stage9dConfig, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.base_master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _bootstrap_seed(config: Stage9dConfig, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.bootstrap_master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    dgp: str, dgp_index: int, n: int, sample_index: int, replicate: int, alpha: float,
    bootstrapped_so_far: int, config: Stage9dConfig,
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
            # Recomputes its own internal point estimate (needed for
            # decisive_conditioning_set) -- the same double-computation
            # Stage 9c's own runner already accepts for the full-repeat
            # mechanism. There the point estimate was a small fraction
            # of total cost; here it is the dominant cost, so this is a
            # real, known inefficiency (roughly 2x this mechanism's own
            # per-replicate cost), accepted for now to keep this runner
            # consistent with established precedent rather than
            # changing the already-tested rescue function's own API.
            result = growing_subset_dpi_structured_density_with_localized_rescue(
                data, flagged, alpha, max_conditioning_size=config.max_conditioning_size,
                bootstraps=config.bootstraps,
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


def _repository_root(config: Stage9dConfig) -> Path:
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


def _write_evidence(config: Stage9dConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
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
    charter = repository_root / "docs/stage9d_charter.md"
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


def run_stage9d(
    config: Stage9dConfig,
    output_dir: Path,
    dgps: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    replicate_range: tuple[int, int] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """Mirrors `stage9c_bootstrap_rescue.run_stage9c`'s own chunking
    semantics exactly (`replicate_range` gets its own fresh cap
    counter per chunk) -- still needed even though the localized
    mechanism's own per-replicate cost is cheap, since `overlap`'s
    near-100% qualification rate still means a chunk could otherwise
    request an unbounded number of bootstrapped replicates."""
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
        write_stage9c_style_report(raw, config, output_dir)
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

    run_stage9d(
        load_config(arguments.config), arguments.output,
        dgps=dgps, sample_sizes=sample_sizes, replicate_range=replicate_range,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
