"""Deterministic raw-evidence runner for the frozen Stage 1 DPI experiment."""

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

from mintnet.dpi import prune_tolerant_dpi
from mintnet.metrics import score_motif
from mintnet.mi import estimate_pairwise_mi
from mintnet.simulation import sample_chain, sample_measured_fork, sample_precision_triangle


@dataclass(frozen=True)
class Stage1Config:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    triangle_families: tuple[str, ...]
    k: int
    taus: tuple[float, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_triangle_true_edge_prune_fpr: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float] | type[str]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage1_config(path: Path) -> Stage1Config:
    """Load a Stage 1 configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 1 configuration must be a mapping")

    config = Stage1Config(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        triangle_families=_values(values, "triangle_families", str),
        k=int(values["k"]),
        taus=_values(values, "taus", float),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_triangle_true_edge_prune_fpr=float(values["maximum_triangle_true_edge_prune_fpr"]),
        source_path=path.resolve(),
    )
    if len(config.strengths) != len(config.triangle_families):
        raise ValueError("strengths and triangle_families must have equal length")
    return config


def _condition_seed(
    config: Stage1Config,
    motif_index: int,
    sample_index: int,
    strength_index: int,
    replicate: int,
) -> int:
    sequence = np.random.SeedSequence(
        [config.master_seed, motif_index, sample_index, strength_index, replicate]
    )
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage1Config) -> Path:
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


def _resolved_config(config: Stage1Config) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strengths": list(config.strengths),
        "triangle_families": list(config.triangle_families),
        "k": config.k,
        "taus": list(config.taus),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_triangle_true_edge_prune_fpr": config.maximum_triangle_true_edge_prune_fpr,
    }


def _write_evidence(
    config: Stage1Config, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage1_charter.md"
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


def _sample_motif(
    motif: str, family: str, n: int, strength: float, rng: np.random.Generator
) -> np.ndarray:
    if motif == "chain":
        return sample_chain(n, strength, rng)
    if motif == "fork":
        return sample_measured_fork(n, strength, rng)
    return sample_precision_triangle(family, n, rng)


def run_stage1(config: Stage1Config, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 1 conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for motif_index, motif in enumerate(("chain", "fork", "triangle")):
        for sample_index, n in enumerate(config.sample_sizes):
            for strength_index, strength in enumerate(config.strengths):
                family = "gaussian" if motif != "triangle" else config.triangle_families[strength_index]
                for replicate in range(config.replicates):
                    seed = _condition_seed(
                        config, motif_index, sample_index, strength_index, replicate
                    )
                    started = time.perf_counter()
                    try:
                        data = _sample_motif(
                            motif, family, n, strength, np.random.default_rng(seed)
                        )
                        mi_matrix = estimate_pairwise_mi(data, config.k)
                        status, error = "ok", ""
                    except Exception as exc:  # raw evidence must retain pipeline failures
                        mi_matrix = None
                        status, error = "error", f"{type(exc).__name__}: {exc}"

                    for tau in config.taus:
                        metrics = {
                            "indirect_prune_tpr": np.nan,
                            "true_edge_prune_fpr": np.nan,
                            "perfect_recovery": np.nan,
                        }
                        retained_01 = retained_02 = retained_12 = np.nan
                        row_status, row_error = status, error
                        if mi_matrix is not None:
                            try:
                                adjacency = prune_tolerant_dpi(mi_matrix, tau)
                                metrics = score_motif(adjacency, motif)
                                retained_01 = bool(adjacency[0, 1])
                                retained_02 = bool(adjacency[0, 2])
                                retained_12 = bool(adjacency[1, 2])
                            except Exception as exc:  # retain pruning and scoring failures by tau
                                row_status = "error"
                                row_error = f"{type(exc).__name__}: {exc}"
                        rows.append(
                            {
                                "motif": motif,
                                "family": family,
                                "strength": strength,
                                "n": n,
                                "k": config.k,
                                "tau": tau,
                                "replicate": replicate,
                                "seed": seed,
                                "retained_01": retained_01,
                                "retained_02": retained_02,
                                "retained_12": retained_12,
                                **metrics,
                                "elapsed_seconds": time.perf_counter() - started,
                                "status": row_status,
                                "error": row_error,
                            }
                        )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    # Keep the raw-evidence runner independent at import time while ensuring
    # every CLI invocation leaves the aggregate R2 gate evidence alongside it.
    from mintnet.experiments.stage1_reporting import write_stage1_report

    write_stage1_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage1(load_stage1_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
