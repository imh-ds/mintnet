"""Deterministic raw-evidence runner for the frozen Stage 2f p=30
composed-pipeline experiment. See docs/stage2f_charter.md.

Reuses Stage 2b's config schema, seeding, scoring, and ground truth
unmodified (`mintnet.experiments.stage2b.Stage2bConfig`,
`load_stage2b_config`, `_condition_seed`, `_score`,
`TRUE_DIRECT_EDGES`/`INDIRECT_EDGES`/`MOTIF_COMPONENTS` -- all already
generic over `noise_count`/`p`, needing no DGP-specific change to run
at `p=30`). This module exists separately from
`mintnet.experiments.stage2b`, rather than as just a new config, for
the same provenance reason Stage 2e was split from Stage 2: Stage 2b's
own `_write_evidence` and report-writer hardcode `docs/stage2b_charter.md`
and "Stage 2b" naming.
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

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage2b import (
    MOTIF_COMPONENTS,
    Stage2bConfig,
    _condition_seed,
    _score,
    load_stage2b_config,
)
from mintnet.pipeline import compose_screen_then_prune
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import sample_screening_network


def _repository_root(config: Stage2bConfig) -> Path:
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


def _resolved_config(config: Stage2bConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "triangle_family": config.triangle_family,
        "noise_count": config.noise_count,
        "screening_alpha": config.screening_alpha,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
    }


def _write_evidence(config: Stage2bConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage2f_charter.md"
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


def run_stage2f(config: Stage2bConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 2f conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    p = 9 + config.noise_count
    selected_form = select_form(fit_candidate_forms())

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        dpi_alpha = selected_form.predict(float(n))
        for replicate in range(config.replicates):
            seed = _condition_seed(config, sample_index, replicate)
            started = time.perf_counter()
            row_status, row_error = "ok", ""
            metrics: dict[str, float] = {
                "indirect_prune_tpr": np.nan,
                "true_edge_prune_fpr": np.nan,
                "screening_false_edge_rate": np.nan,
                "final_false_edge_rate": np.nan,
            }
            chain_is_triad = fork_is_triad = triangle_is_triad = np.nan
            try:
                data = sample_screening_network(
                    n, config.strength, config.triangle_family, config.noise_count,
                    np.random.default_rng(seed),
                )
                evidence = compute_pairwise_screening_evidence(data)
                screened = screen_uncorrected(evidence, config.screening_alpha)
                final, shapes = compose_screen_then_prune(data, screened, dpi_alpha)
                metrics = _score(screened, final, p)

                def _validated(component: frozenset[int]) -> float:
                    shape = shapes.get(component)
                    return float(shape["is_validated_shape"]) if shape is not None else 0.0

                chain_is_triad = _validated(MOTIF_COMPONENTS["chain"])
                fork_is_triad = _validated(MOTIF_COMPONENTS["fork"])
                triangle_is_triad = _validated(MOTIF_COMPONENTS["triangle"])
            except Exception as exc:  # raw evidence must retain pipeline failures
                row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "n": n,
                    "replicate": replicate,
                    "seed": seed,
                    "dpi_alpha": dpi_alpha,
                    **metrics,
                    "chain_is_triad": chain_is_triad,
                    "fork_is_triad": fork_is_triad,
                    "triangle_is_triad": triangle_is_triad,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage2f_reporting import write_stage2f_report

    write_stage2f_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage2f(load_stage2b_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
