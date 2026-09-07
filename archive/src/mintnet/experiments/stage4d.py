"""Hybrid raw-evidence runner for the frozen Stage 4d sequential-engine
floor-search charter. See docs/stage4d_charter.md.

Simulates fresh data only for the five new, previously-untested sample
sizes (N=300/500/600/650/700). N=750 is reused verbatim from Stage 4b's
raw evidence as the known bookend, mirroring Stage 1i/2i's own
bookend-reuse pattern exactly.
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

from mintnet.experiments.stage4b import SHAPES, Stage4bConfig, _ground_truth, _sample, _score
from mintnet.pipeline import sequential_screen_and_prune_detailed

BOOKEND_N = 750


@dataclass(frozen=True)
class Stage4dConfig:
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


def load_stage4d_config(path: Path) -> Stage4dConfig:
    """Load a Stage 4d configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4d configuration must be a mapping")

    return Stage4dConfig(
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
    # Keyed on each sample size's position in *this config's* sample_sizes
    # list -- only used to simulate the five new sample sizes; N=750 is
    # never regenerated here, it is read from Stage 4b's own evidence.
    sequence = np.random.SeedSequence([master_seed, shape_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4dConfig) -> Path:
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


def _resolved_config(config: Stage4dConfig) -> dict[str, object]:
    return {
        "sample_sizes": sorted(set(config.sample_sizes) | {BOOKEND_N}),
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


def _write_evidence(
    config: Stage4dConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    bookend_raw_evidence_path: Path,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4d_charter.md"
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    metadata = {
        "charter_sha256": charter_hash,
        "bookend_raw_evidence_path": str(bookend_raw_evidence_path),
        "bookend_raw_evidence_sha256": hashlib.sha256(bookend_raw_evidence_path.read_bytes()).hexdigest(),
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _simulate(config: Stage4dConfig) -> pd.DataFrame:
    """Simulate raw evidence for exactly the sample sizes in config.sample_sizes."""
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
    return pd.DataFrame(rows)


def run_stage4d(config: Stage4dConfig, bookend_raw_evidence_path: Path, output_dir: Path) -> pd.DataFrame:
    """Simulate the five new sample sizes and merge in Stage 4b's N=750 bookend."""
    run_started = time.perf_counter()
    new_raw = _simulate(config)

    bookend_raw = pd.read_csv(bookend_raw_evidence_path)
    bookend_raw = bookend_raw.loc[bookend_raw["n"] == BOOKEND_N].copy()

    raw = pd.concat([new_raw, bookend_raw], ignore_index=True)
    _write_evidence(config, output_dir, raw, bookend_raw_evidence_path, time.perf_counter() - run_started)
    from mintnet.experiments.stage4d_reporting import write_stage4d_report

    report_config = Stage4bConfig(
        sample_sizes=tuple(sorted(set(config.sample_sizes) | {BOOKEND_N})),
        hub_strength=config.hub_strength,
        alphas=config.alphas,
        replicates=config.replicates,
        master_seed=config.master_seed,
        development_replicates=config.development_replicates,
        validation_replicates=config.validation_replicates,
        minimum_indirect_prune_tpr=config.minimum_indirect_prune_tpr,
        maximum_true_edge_prune_fpr=config.maximum_true_edge_prune_fpr,
        required_margin=config.required_margin,
    )
    write_stage4d_report(raw, report_config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--bookend-raw-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4d(load_stage4d_config(arguments.config), arguments.bookend_raw_evidence, arguments.output)


if __name__ == "__main__":
    main()
