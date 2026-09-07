"""Deterministic raw-evidence runner for the frozen Stage 4e candidacy-
conditional overlap metric experiment. See docs/stage4e_charter.md.

Reuses Stage 1L's overlap DGP and ground truth
(`mintnet.simulation.sample_overlapping_triangles`, `mintnet.
experiments.stage1l.TRUE_EDGES`/`INDIRECT_EDGES`), Stage 4b/4d's exact
seed derivation (so this charter's draws are the identical data Stage
4d already analyzed, not a fresh independent sample), and Stage 4a's
sequential engine's detailed variant
(`mintnet.pipeline.sequential_screen_and_prune_detailed`) unmodified.
Only the metric extraction (per-cross-branch-pair candidacy and
conditioning correctness, not the old composite TPR) and the runner/
reporting are new.
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

from mintnet.experiments.stage1l import INDIRECT_EDGES as OVERLAP_INDIRECT_EDGES
from mintnet.experiments.stage1l import TRUE_EDGES as OVERLAP_TRUE_EDGES
from mintnet.experiments.stage4b import SHAPES
from mintnet.pipeline import sequential_screen_and_prune_detailed
from mintnet.simulation import sample_overlapping_triangles

_OVERLAP_SHAPE_INDEX = SHAPES.index("overlap")


@dataclass(frozen=True)
class Stage4eConfig:
    sample_sizes: tuple[int, ...]
    alphas: tuple[float, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_conditional_accuracy: float
    maximum_true_edge_prune_fpr: float
    required_margin: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4e_config(path: Path) -> Stage4eConfig:
    """Load a Stage 4e configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4e configuration must be a mapping")

    return Stage4eConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        alphas=_values(values, "alphas", float),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_conditional_accuracy=float(values["minimum_conditional_accuracy"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        required_margin=float(values["required_margin"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, sample_index: int, replicate: int) -> int:
    # Matches Stage 4b/4d's exact seed derivation (shape_index fixed to
    # overlap's own index) so this charter's draws are the identical data
    # Stage 4d already analyzed, not a fresh independent sample.
    sequence = np.random.SeedSequence([master_seed, _OVERLAP_SHAPE_INDEX, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4eConfig) -> Path:
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


def _resolved_config(config: Stage4eConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "alphas": list(config.alphas),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_conditional_accuracy": config.minimum_conditional_accuracy,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "required_margin": config.required_margin,
    }


def _write_evidence(config: Stage4eConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4e_charter.md"
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


def _pair_label(i: int, j: int) -> str:
    return f"{i}{j}"


def run_stage4e(config: Stage4eConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 4e conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, sample_index, replicate)
            started = time.perf_counter()
            try:
                data = sample_overlapping_triangles(n, np.random.default_rng(seed))
                status, error = "ok", ""
            except Exception as exc:  # raw evidence must retain pipeline failures
                data = None
                status, error = "error", f"{type(exc).__name__}: {exc}"

            for alpha in config.alphas:
                row: dict[str, object] = {}
                row_status, row_error = status, error
                true_edge_fpr = np.nan
                for i, j in OVERLAP_INDIRECT_EDGES:
                    row[f"candidate_{_pair_label(i, j)}"] = np.nan
                    row[f"correctly_pruned_{_pair_label(i, j)}"] = np.nan
                if data is not None:
                    try:
                        final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                        by_pair = {(d.i, d.j): d for d in decisions}
                        true_retained = sum(1 for i, j in OVERLAP_TRUE_EDGES if final[i, j])
                        true_edge_fpr = 1.0 - (true_retained / len(OVERLAP_TRUE_EDGES))
                        for i, j in OVERLAP_INDIRECT_EDGES:
                            decision = by_pair.get((i, j))
                            label = _pair_label(i, j)
                            if decision is None:
                                row[f"candidate_{label}"] = False
                                row[f"correctly_pruned_{label}"] = np.nan
                            else:
                                row[f"candidate_{label}"] = True
                                row[f"correctly_pruned_{label}"] = not decision.confirmed
                    except Exception as exc:  # retain pruning and scoring failures by alpha
                        row_status = "error"
                        row_error = f"{type(exc).__name__}: {exc}"

                rows.append(
                    {
                        "n": n,
                        "alpha": alpha,
                        "replicate": replicate,
                        "seed": seed,
                        **row,
                        "true_edge_prune_fpr": true_edge_fpr,
                        "elapsed_seconds": time.perf_counter() - started,
                        "status": row_status,
                        "error": row_error,
                    }
                )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage4e_reporting import write_stage4e_report

    write_stage4e_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4e(load_stage4e_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
