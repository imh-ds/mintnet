"""Deterministic, shardable raw-evidence runner for the frozen Stage 7h
composed-tier validation of the structured-density growing-subset
engine. See docs/stage7h_charter.md.

First time `growing_subset_dpi_structured_density` is composed with
MINT's own screening step and run on a real, noisy p=15 network
(`chain_fork_hub`/`overlap`) -- every prior mi-native composed-tier
charter (D-053, D-069-D-081) used the older Fisher-z engine instead.

Alpha is selected via the SAME already-validated fitted-alpha
procedure Stage 9b used (`fit_candidate_forms`/`select_form`), one
value per N, NOT a manual grid: unlike the isolation tier's pool-size-1
motifs (Stage 7f), a composed candidate edge can have more than one
possible conditioning subset, so `decisive_p_value` is not
alpha-independent here -- re-thresholding stored p-values across many
alphas would silently misrepresent what a different-alpha run would
actually have done.

Row unit is one replicate, with every candidate edge's own decisive_p_
value/confidence/conditioning_size_used/is_true_edge persisted as a
JSON blob (mirrors Stage 9a's/9b's own qualifying_json pattern) --
required for Part A's own stratified-accuracy table (D-076's own
design, extended across N/strength) and Part B's own confidence-
transfer check.

Real per-replicate cost measured directly under GitHub Actions' own
thread limits (`OMP_NUM_THREADS=2` etc.), at `permutations=199`,
BEFORE sizing anything, per this charter's own explicit requirement:
does NOT transfer from the isolation tier's own cheap `9s`-`13s`
(Stage 7f) at all -- `chain_fork_hub` costs `~40s`-`65s`/replicate;
`overlap` costs `~172s`-`264s`/replicate (its own known deeper
conditioning need, D-053). At the charter's own provisional `R=200`,
`overlap` alone would need up to `~14.7` hours per shard -- over
GitHub Actions' 6-hour limit. **Revised down to `replicates=100`,
`batch_size=25`** (worst-case per-shard cost `25 x 264s ~= 1.83h`,
comfortable margin): `6` conditions (`2` dgps `x` `3` strengths) `x`
`7` `N` `x` `4` batches = `168` shards, under the `256`-job matrix cap.
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
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected


@dataclass(frozen=True)
class Stage7hConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    screening_alpha: float
    max_conditioning_size: int
    degree: int
    ridge_lambda: float
    cv_folds: int
    k_perm: int
    permutations: int
    replicates: int
    batch_size: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage7hConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7h configuration must be a mapping")
    return Stage7hConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        screening_alpha=float(values["screening_alpha"]),
        max_conditioning_size=int(values["max_conditioning_size"]),
        degree=int(values["degree"]),
        ridge_lambda=float(values["ridge_lambda"]),
        cv_folds=int(values["cv_folds"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


# "chain_fork_hub_0".."chain_fork_hub_2" (config.strengths), same for "overlap".
def _conditions(config: Stage7hConfig) -> tuple[str, ...]:
    return tuple(f"{dgp}_{i}" for dgp in COMPOSED_SHAPES for i in range(len(config.strengths)))


def _parse_condition(condition: str) -> tuple[str, int]:
    dgp, index = condition.rsplit("_", 1)
    return dgp, int(index)


COMBINATION_COLUMNS: tuple[str, ...] = ("condition", "n", "replicate")


def _n_batches(config: Stage7hConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7hConfig) -> set[tuple[str, int, int]]:
    return {
        (condition, n, replicate)
        for condition in _conditions(config)
        for n in config.sample_sizes
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage7hConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(master_seed: int, dgp_index: int, strength_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, dgp_index, strength_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(condition: str, n: int, replicate: int, alpha: float, config: Stage7hConfig) -> dict[str, object]:
    dgp, strength_index = _parse_condition(condition)
    dgp_index = COMPOSED_SHAPES.index(dgp)
    sample_index = config.sample_sizes.index(n)
    strength = config.strengths[strength_index]
    seed = _condition_seed(config.master_seed, dgp_index, strength_index, sample_index, replicate)

    entry = _COMPOSED_DGP_REGISTRY[dgp]
    sample: Callable = entry["sample"]  # type: ignore[assignment]
    p = int(entry["p"])
    truth = _true_adjacency(entry["true_edges"], p)  # type: ignore[arg-type]

    row: dict[str, object] = {
        "condition": condition, "dgp": dgp, "strength": strength, "n": n, "replicate": replicate,
        "alpha": alpha, "seed": seed, "qualifying_json": "[]", "n_qualifying": 0,
        "elapsed_seconds": np.nan, "status": "ok", "error": "",
    }
    started = time.perf_counter()
    try:
        data = sample(n, strength, np.random.default_rng(seed))
        evidence = compute_pairwise_screening_evidence(data)
        flagged = screen_uncorrected(evidence, config.screening_alpha)
        result = growing_subset_dpi_structured_density(
            data, flagged, alpha, master_seed=config.master_seed, replicate=replicate,
            degree=config.degree, ridge_lambda=config.ridge_lambda, cv_folds=config.cv_folds,
            k_perm=config.k_perm, permutations=config.permutations, max_conditioning_size=config.max_conditioning_size,
        )
        qualifying = []
        for i in range(p):
            for j in range(i + 1, p):
                if not flagged[i, j]:
                    continue
                qualifying.append(
                    {
                        "i": i, "j": j, "is_true_edge": bool(truth[i, j]),
                        "retained": bool(result.adjacency[i, j]),
                        "conditioning_size_used": int(result.conditioning_size_used[(i, j)]),
                        "decisive_p_value": result.decisive_p_value[(i, j)],
                        "confidence": result.confidence[(i, j)],
                    }
                )
        row["qualifying_json"] = json.dumps(qualifying)
        row["n_qualifying"] = len(qualifying)
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


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7hConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "sample_sizes": list(config.sample_sizes), "strengths": list(config.strengths),
        "screening_alpha": config.screening_alpha, "max_conditioning_size": config.max_conditioning_size,
        "degree": config.degree, "ridge_lambda": config.ridge_lambda, "cv_folds": config.cv_folds,
        "k_perm": config.k_perm, "permutations": config.permutations,
        "replicates": config.replicates, "batch_size": config.batch_size, "master_seed": config.master_seed,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7h_charter.md"
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


def run_stage7h(
    config: Stage7hConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    replicate_range: tuple[int, int] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- replicate ranges are normally derived
    from `config.batch_size` against the FULL replicate count, and
    seeds key off full-grid quantities only, so a shard's results match
    an unsharded run's for the same replicates.

    `replicate_range` (inclusive `(start, end)`) overrides `batches`
    entirely, for a finer-grained recovery dispatch -- e.g. re-running
    one already-timed-out batch as several smaller sub-ranges without
    needing a new `config.batch_size`. Not used by a normal dispatch."""
    started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_conditions = conditions if conditions is not None else _conditions(config)
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        for n in target_sizes:
            alpha = float(alpha_formula.predict(float(n)))
            if replicate_range is not None:
                start_replicate, end_replicate_inclusive = replicate_range
                for replicate in range(start_replicate, end_replicate_inclusive + 1):
                    rows.append(_run_one_replicate(condition, n, replicate, alpha, config))
                continue
            target_batches = batches if batches is not None else tuple(range(_n_batches(config)))
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.append(_run_one_replicate(condition, n, replicate, alpha, config))

    raw = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=[
            "condition", "dgp", "strength", "n", "replicate", "alpha", "seed",
            "qualifying_json", "n_qualifying", "elapsed_seconds", "status", "error",
        ]
    )
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7h_composed_reporting import write_report as write_stage7h_report

    write_stage7h_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None,
        help="comma-separated subset of conditions (e.g. chain_fork_hub_0,overlap_2; default: all)",
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--batches", type=str, default=None, help="comma-separated subset of batch indices (default: all)"
    )
    parser.add_argument(
        "--replicate-range", type=str, default=None,
        help="'start-end' inclusive, overrides --batches for a finer-grained recovery dispatch",
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    conditions = tuple(arguments.conditions.split(",")) if arguments.conditions else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    batches = tuple(int(v) for v in arguments.batches.split(",")) if arguments.batches else None
    replicate_range = None
    if arguments.replicate_range:
        start_str, end_str = arguments.replicate_range.split("-")
        replicate_range = (int(start_str), int(end_str))

    run_stage7h(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches, replicate_range=replicate_range,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
