"""Deterministic raw-evidence runner for the frozen Stage 4a sequential/
greedy conditioning engine experiment. See docs/stage4a_charter.md.

Reuses Stage 1b's exact DGP, config schema, and seed derivation
unmodified (`mintnet.experiments.stage1b.Stage1bConfig`,
`load_stage1b_config`, `_condition_seed`) for direct, apples-to-apples
comparability against the conservative engine's own first isolation
result -- the only difference from Stage 1b is the pruning mechanism
itself (`mintnet.pipeline.sequential_screen_and_prune` in place of
`mintnet.dpi.prune_conditional_independence`). This module exists as its
own file, rather than reusing Stage 1b's `_write_evidence`/report-writer,
because those hardcode `docs/stage1b_charter.md` -- reusing them
unmodified would hash and label this charter's evidence as Stage 1b's,
which this project's provenance discipline does not permit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mintnet.experiments.stage1b import Stage1bConfig, _condition_seed, load_stage1b_config
from mintnet.metrics import score_motif
from mintnet.pipeline import sequential_screen_and_prune
from mintnet.simulation import sample_chain, sample_measured_fork, sample_precision_triangle


def _repository_root(config: Stage1bConfig) -> Path:
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


def _resolved_config(config: Stage1bConfig) -> dict[str, object]:
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


def _write_evidence(config: Stage1bConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4a_charter.md"
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


def _sample_motif(motif: str, family: str, n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    if motif == "chain":
        return sample_chain(n, strength, rng)
    if motif == "fork":
        return sample_measured_fork(n, strength, rng)
    return sample_precision_triangle(family, n, rng)


def run_stage4a(config: Stage1bConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 4a conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for motif_index, motif in enumerate(("chain", "fork", "triangle")):
        for sample_index, n in enumerate(config.sample_sizes):
            for strength_index, strength in enumerate(config.strengths):
                family = "gaussian" if motif != "triangle" else config.triangle_families[strength_index]
                for replicate in range(config.replicates):
                    seed = _condition_seed(config, motif_index, sample_index, strength_index, replicate)
                    started = time.perf_counter()
                    try:
                        data = _sample_motif(motif, family, n, strength, np.random.default_rng(seed))
                        status, error = "ok", ""
                    except Exception as exc:  # raw evidence must retain pipeline failures
                        data = None
                        status, error = "error", f"{type(exc).__name__}: {exc}"

                    for alpha in config.alphas:
                        metrics = {
                            "indirect_prune_tpr": np.nan,
                            "true_edge_prune_fpr": np.nan,
                            "perfect_recovery": np.nan,
                        }
                        retained_01 = retained_02 = retained_12 = np.nan
                        row_status, row_error = status, error
                        if data is not None:
                            try:
                                adjacency = sequential_screen_and_prune(data, alpha)
                                metrics = score_motif(adjacency, motif)
                                retained_01 = bool(adjacency[0, 1])
                                retained_02 = bool(adjacency[0, 2])
                                retained_12 = bool(adjacency[1, 2])
                            except Exception as exc:  # retain pruning and scoring failures by alpha
                                row_status = "error"
                                row_error = f"{type(exc).__name__}: {exc}"
                        rows.append(
                            {
                                "motif": motif,
                                "family": family,
                                "strength": strength,
                                "n": n,
                                "alpha": alpha,
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
    from mintnet.experiments.stage4a_reporting import write_stage4a_report

    write_stage4a_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4a(load_stage1b_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
