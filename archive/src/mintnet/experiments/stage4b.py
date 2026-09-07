"""Deterministic raw-evidence runner for the frozen Stage 4b sequential/
greedy conditioning engine experiment (hub and shared-node overlap
components). See docs/stage4b_charter.md.

Reuses Stage 1k's hub DGP and ground truth (`mintnet.experiments.
stage1k.TRUE_EDGES`, `INDIRECT_EDGES`, `mintnet.simulation.sample_hub`)
and Stage 1L's overlap DGP and ground truth (`mintnet.experiments.
stage1l.TRUE_EDGES`, `INDIRECT_EDGES`, `mintnet.simulation.
sample_overlapping_triangles`) unmodified, and Stage 4a's sequential
engine (`mintnet.pipeline.sequential_screen_and_prune_detailed`)
unmodified. Only the runner and reporting are new, so this charter's
evidence hashes docs/stage4b_charter.md rather than Stage 1k/1L/4a's.
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

from mintnet.experiments.stage1k import CHILDREN as HUB_CHILDREN
from mintnet.experiments.stage1k import INDIRECT_EDGES as HUB_INDIRECT_EDGES
from mintnet.experiments.stage1k import TRUE_EDGES as HUB_TRUE_EDGES
from mintnet.experiments.stage1l import INDIRECT_EDGES as OVERLAP_INDIRECT_EDGES
from mintnet.experiments.stage1l import TRUE_EDGES as OVERLAP_TRUE_EDGES
from mintnet.pipeline import sequential_screen_and_prune_detailed
from mintnet.simulation import sample_hub, sample_overlapping_triangles

SHAPES: tuple[str, ...] = ("hub", "overlap")


@dataclass(frozen=True)
class Stage4bConfig:
    sample_sizes: tuple[int, ...]
    hub_strength: float
    alphas: tuple[float, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_true_edge_prune_fpr: float
    required_margin: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4b_config(path: Path) -> Stage4bConfig:
    """Load a Stage 4b configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4b configuration must be a mapping")

    return Stage4bConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        hub_strength=float(values["hub_strength"]),
        alphas=_values(values, "alphas", float),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        required_margin=float(values["required_margin"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, shape_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, shape_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4bConfig) -> Path:
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


def _resolved_config(config: Stage4bConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "hub_strength": config.hub_strength,
        "alphas": list(config.alphas),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "required_margin": config.required_margin,
    }


def _write_evidence(config: Stage4bConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4b_charter.md"
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


def _sample(shape: str, n: int, config: Stage4bConfig, rng: np.random.Generator) -> np.ndarray:
    if shape == "hub":
        return sample_hub(n, config.hub_strength, children=len(HUB_CHILDREN), rng=rng)
    return sample_overlapping_triangles(n, rng)


def _ground_truth(shape: str) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    if shape == "hub":
        return HUB_TRUE_EDGES, HUB_INDIRECT_EDGES
    return OVERLAP_TRUE_EDGES, OVERLAP_INDIRECT_EDGES


def _score(final: np.ndarray, true_edges: tuple[tuple[int, int], ...], indirect_edges: tuple[tuple[int, int], ...]) -> dict[str, float]:
    true_retained = sum(1 for i, j in true_edges if final[i, j])
    indirect_pruned = sum(1 for i, j in indirect_edges if not final[i, j])
    return {
        "indirect_prune_tpr": indirect_pruned / len(indirect_edges),
        "true_edge_prune_fpr": 1.0 - (true_retained / len(true_edges)),
    }


def run_stage4b(config: Stage4bConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 4b conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for shape_index, shape in enumerate(SHAPES):
        true_edges, indirect_edges = _ground_truth(shape)
        for sample_index, n in enumerate(config.sample_sizes):
            for replicate in range(config.replicates):
                seed = _condition_seed(config.master_seed, shape_index, sample_index, replicate)
                started = time.perf_counter()
                try:
                    data = _sample(shape, n, config, np.random.default_rng(seed))
                    status, error = "ok", ""
                except Exception as exc:  # raw evidence must retain pipeline failures
                    data = None
                    status, error = "error", f"{type(exc).__name__}: {exc}"

                for alpha in config.alphas:
                    metrics = {"indirect_prune_tpr": np.nan, "true_edge_prune_fpr": np.nan}
                    row_status, row_error = status, error
                    tested_pairs = confirmed_pairs = np.nan
                    if data is not None:
                        try:
                            final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                            metrics = _score(final, true_edges, indirect_edges)
                            tested_pairs = sum(1 for d in decisions if d.tested_neighbors)
                            confirmed_pairs = sum(1 for d in decisions if d.confirmed)
                        except Exception as exc:  # retain pruning and scoring failures by alpha
                            row_status = "error"
                            row_error = f"{type(exc).__name__}: {exc}"
                    rows.append(
                        {
                            "shape": shape,
                            "n": n,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": seed,
                            **metrics,
                            "conditionally_tested_pairs": tested_pairs,
                            "confirmed_pairs": confirmed_pairs,
                            "elapsed_seconds": time.perf_counter() - started,
                            "status": row_status,
                            "error": row_error,
                        }
                    )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage4b_reporting import write_stage4b_report

    write_stage4b_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4b(load_stage4b_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
