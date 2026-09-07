"""Reporting-only runner for the frozen Stage 1g margin-robust selection charter.

Reuses Stage 1f's raw evidence unmodified rather than re-simulating: the
DGP, mechanism, seeds, and alpha grid are byte-for-byte identical to R2f
(docs/stage1f_charter.md); only the development-selection rule changes
(docs/stage1g_charter.md).
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

import pandas as pd
import yaml


@dataclass(frozen=True)
class Stage1gConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    triangle_families: tuple[str, ...]
    alphas: tuple[float, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_triangle_true_edge_prune_fpr: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float] | type[str]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage1g_config(path: Path) -> Stage1gConfig:
    """Load a Stage 1g configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 1g configuration must be a mapping")

    config = Stage1gConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        triangle_families=_values(values, "triangle_families", str),
        alphas=_values(values, "alphas", float),
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


def _repository_root(config: Stage1gConfig) -> Path:
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


def _resolved_config(config: Stage1gConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strengths": list(config.strengths),
        "triangle_families": list(config.triangle_families),
        "alphas": list(config.alphas),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_triangle_true_edge_prune_fpr": config.maximum_triangle_true_edge_prune_fpr,
    }


def _write_evidence(
    config: Stage1gConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    source_raw_metrics_path: Path,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage1g_charter.md"
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    source_hash = hashlib.sha256(source_raw_metrics_path.read_bytes()).hexdigest()
    metadata = {
        "charter_sha256": charter_hash,
        "source_raw_metrics_path": str(source_raw_metrics_path),
        "source_raw_metrics_sha256": source_hash,
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def run_stage1g(config: Stage1gConfig, raw_metrics_path: Path, output_dir: Path) -> pd.DataFrame:
    """Re-evaluate R2f's raw evidence under the frozen R2g per-cell selection rule."""
    run_started = time.perf_counter()
    raw = pd.read_csv(raw_metrics_path)
    _write_evidence(config, output_dir, raw, raw_metrics_path, time.perf_counter() - run_started)
    # Keep the reporting-only runner independent at import time while ensuring
    # every CLI invocation leaves the aggregate R2g gate evidence alongside it.
    from mintnet.experiments.stage1g_reporting import write_stage1g_report

    write_stage1g_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--raw-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage1g(load_stage1g_config(arguments.config), arguments.raw_evidence, arguments.output)


if __name__ == "__main__":
    main()
