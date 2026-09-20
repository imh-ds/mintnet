"""Deterministic raw-evidence runner for the frozen Stage 7 isolation-
tier evidence run -- the falsification core of docs/stage7_charter.md's
own PROCEED/REASSESS gate. Mirrors `mintnet.experiments.stage1b`'s own
structure and DGPs (chain, measured fork, triangle balanced/moderate/
strong) exactly, substituting the calibrated CMIknn/local-permutation
test (`mintnet.dpi.cmi_conditional`, D-056/D-057's own `k_cmi=40`/
`k_perm=3` defaults) for Fisher-z partial correlation.

Draws are NOT paired with Stage 1b's own historical evidence: this
charter's own `N` grid (`{750, 1500}`, D-057's operating-range floor)
differs from Stage 1b's (`100`-`1000`), so bit-identical pairing across
every cell isn't possible regardless of seed choice -- a fresh,
independent `master_seed` is used instead, documented here rather than
silently assumed equivalent to Stage 1b's own draws.

Since every candidate pair in a 3-node motif has exactly one possible
conditioning set (the remaining column), `mintnet.dpi.cmi_conditional`
computes each pair's CMI/p-value ONCE per replicate and this runner
sweeps the full `alphas` grid by re-thresholding that same evidence --
zero additional significance-test cost per alpha, mirroring Stage 1b's
own "compute once, threshold many times" structure (there, free
because Fisher-z is closed-form; here, a deliberate design choice
because CMIknn is not).

Sharded by (condition, N, batch) -- `condition` combines motif and
strength-index into one label (`chain_0`, `triangle_2`, etc., see
`CONDITIONS`) to fit the generic 3-dimension sharded_benchmark.yml
workflow; `batch` selects a `config.batch_size`-sized slice of the
full replicate range, keeping each shard's own wall-clock cost well
under GitHub Actions' 6-hour job timeout (D-058's own measured
per-replicate costs, at this design's much cheaper 3-node motifs, make
a single dispatch of `9 conditions x 2 N x ceil(replicates/batch_size)
batches` shards comfortably fit under the 256-job matrix cap for the
charter's own R=500 target).
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

from mintnet.dpi.cmi_conditional import compute_cmi_conditional_independence_evidence, prune_cmi_conditional_independence
from mintnet.metrics import score_motif
from mintnet.simulation import sample_chain, sample_measured_fork, sample_precision_triangle

MOTIFS: tuple[str, ...] = ("chain", "fork", "triangle")
# (motif, strength_index) pairs, matching Stage 1b's own strength/
# triangle_families index pairing -- strength_index selects config.strengths[i]
# for chain/fork, or config.triangle_families[i] for triangle.
CONDITIONS: tuple[str, ...] = tuple(f"{motif}_{i}" for motif in MOTIFS for i in range(3))


def _parse_condition(condition: str) -> tuple[str, int]:
    motif, index = condition.rsplit("_", 1)
    return motif, int(index)


@dataclass(frozen=True)
class Stage7IsolationConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    triangle_families: tuple[str, ...]
    alphas: tuple[float, ...]
    replicates: int
    batch_size: int
    k_cmi: int
    k_perm: int
    permutations: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_triangle_true_edge_prune_fpr: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float] | type[str]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage7IsolationConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 7 isolation configuration must be a mapping")
    config = Stage7IsolationConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        triangle_families=_values(values, "triangle_families", str),
        alphas=_values(values, "alphas", float),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        k_cmi=int(values["k_cmi"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_triangle_true_edge_prune_fpr=float(values["maximum_triangle_true_edge_prune_fpr"]),
        source_path=path.resolve(),
    )
    if len(config.strengths) != 3 or len(config.triangle_families) != 3:
        raise ValueError("strengths and triangle_families must each have exactly 3 entries")
    return config


COMBINATION_COLUMNS: tuple[str, ...] = ("motif", "strength_index", "n", "replicate", "alpha")


def _n_batches(config: Stage7IsolationConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage7IsolationConfig) -> set[tuple[str, int, int, int, float]]:
    return {
        (motif, strength_index, n, replicate, alpha)
        for motif in MOTIFS
        for strength_index in range(3)
        for n in config.sample_sizes
        for replicate in range(config.replicates)
        for alpha in config.alphas
    }


def expected_row_count(config: Stage7IsolationConfig) -> int:
    return len(expected_combinations(config))


def _sample_motif(motif: str, family: str, n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    if motif == "chain":
        return sample_chain(n, strength, rng)
    if motif == "fork":
        return sample_measured_fork(n, strength, rng)
    return sample_precision_triangle(family, n, rng)


def _condition_seed(master_seed: int, motif_index: int, sample_index: int, strength_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, motif_index, sample_index, strength_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_replicate(
    motif: str, strength_index: int, n: int, replicate: int, config: Stage7IsolationConfig
) -> list[dict[str, object]]:
    motif_index = MOTIFS.index(motif)
    sample_index = config.sample_sizes.index(n)
    strength = config.strengths[strength_index]
    family = "gaussian" if motif != "triangle" else config.triangle_families[strength_index]
    seed = _condition_seed(config.master_seed, motif_index, sample_index, strength_index, replicate)

    started = time.perf_counter()
    try:
        data = _sample_motif(motif, family, n, strength, np.random.default_rng(seed))
        evidence = compute_cmi_conditional_independence_evidence(
            data,
            seed_context=(config.master_seed, motif_index, sample_index, strength_index, replicate),
            k_cmi=config.k_cmi, k_perm=config.k_perm, permutations=config.permutations,
        )
        status, error = "ok", ""
    except Exception as exc:  # raw evidence must retain sampling/estimation failures
        data = None
        evidence = None
        status, error = "error", f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    rows: list[dict[str, object]] = []
    for alpha in config.alphas:
        metrics = {"indirect_prune_tpr": np.nan, "true_edge_prune_fpr": np.nan, "perfect_recovery": np.nan}
        cmi_01 = cmi_02 = cmi_12 = np.nan
        p_value_01 = p_value_02 = p_value_12 = np.nan
        retained_01 = retained_02 = retained_12 = np.nan
        row_status, row_error = status, error
        if evidence is not None:
            try:
                adjacency = prune_cmi_conditional_independence(evidence, alpha)
                metrics = score_motif(adjacency, motif)
                retained_01, retained_02, retained_12 = bool(adjacency[0, 1]), bool(adjacency[0, 2]), bool(adjacency[1, 2])
                cmi_01, cmi_02, cmi_12 = float(evidence.cmi[0, 1]), float(evidence.cmi[0, 2]), float(evidence.cmi[1, 2])
                p_value_01 = float(evidence.p_value[0, 1])
                p_value_02 = float(evidence.p_value[0, 2])
                p_value_12 = float(evidence.p_value[1, 2])
            except Exception as exc:  # retain pruning/scoring failures by alpha
                row_status = "error"
                row_error = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "motif": motif, "family": family, "strength_index": strength_index, "strength": strength,
                "n": n, "alpha": alpha, "replicate": replicate, "seed": seed,
                "retained_01": retained_01, "retained_02": retained_02, "retained_12": retained_12,
                "cmi_01": cmi_01, "cmi_02": cmi_02, "cmi_12": cmi_12,
                "p_value_01": p_value_01, "p_value_02": p_value_02, "p_value_12": p_value_12,
                "confidence_01": (1.0 - p_value_01) if row_status == "ok" else np.nan,
                "confidence_02": (1.0 - p_value_02) if row_status == "ok" else np.nan,
                "confidence_12": (1.0 - p_value_12) if row_status == "ok" else np.nan,
                **metrics,
                "elapsed_seconds": elapsed,
                "status": row_status, "error": row_error,
            }
        )
    return rows


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
    "motif", "family", "strength_index", "strength", "n", "alpha", "replicate", "seed",
    "retained_01", "retained_02", "retained_12", "cmi_01", "cmi_02", "cmi_12",
    "p_value_01", "p_value_02", "p_value_12", "confidence_01", "confidence_02", "confidence_12",
    "indirect_prune_tpr", "true_edge_prune_fpr", "perfect_recovery", "elapsed_seconds", "status", "error",
)


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7IsolationConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "sample_sizes": list(config.sample_sizes), "strengths": list(config.strengths),
        "triangle_families": list(config.triangle_families), "alphas": list(config.alphas),
        "replicates": config.replicates, "batch_size": config.batch_size,
        "k_cmi": config.k_cmi, "k_perm": config.k_perm, "permutations": config.permutations,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_triangle_true_edge_prune_fpr": config.maximum_triangle_true_edge_prune_fpr,
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7_charter.md"
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


def run_stage7_isolation(
    config: Stage7IsolationConfig,
    output_dir: Path,
    conditions: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`conditions`/`sample_sizes`/`batches` restrict which cells run,
    for a single-cell CI shard -- replicate ranges are always derived
    from `config.batch_size` against the FULL replicate count, and
    seeds key off `MOTIFS.index(...)`/`config.sample_sizes.index(...)`/
    `strength_index`/`replicate` (all full-grid quantities), so a
    shard's results match an unsharded run's for the same replicates."""
    started = time.perf_counter()
    target_conditions = conditions if conditions is not None else CONDITIONS
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for condition in target_conditions:
        motif, strength_index = _parse_condition(condition)
        for n in target_sizes:
            for batch in target_batches:
                start_replicate = batch * config.batch_size
                end_replicate = min(start_replicate + config.batch_size, config.replicates)
                for replicate in range(start_replicate, end_replicate):
                    rows.extend(_run_one_replicate(motif, strength_index, n, replicate, config))

    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7_isolation_reporting import write_report as write_stage7_report

    write_stage7_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--conditions", type=str, default=None,
        help="comma-separated subset of conditions (e.g. chain_0,triangle_2; default: all)",
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

    run_stage7_isolation(
        load_config(arguments.config), arguments.output,
        conditions=conditions, sample_sizes=sample_sizes, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
