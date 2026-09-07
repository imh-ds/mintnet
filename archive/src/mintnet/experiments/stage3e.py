"""Deterministic raw-evidence runner for the frozen Stage 3e p=30
overlap stability-filtering-rescue experiment. See docs/stage3e_charter.md.

Reuses Stage 3b's config schema, seeding, and category logic unmodified
(`mintnet.experiments.stage3b.Stage3bConfig`, `load_stage3b_config`,
`_condition_seed`, `_category` -- the ground-truth categories live in
columns 0-10 and are unaffected by `p`), Stage 2h's `p=30` overlap DGP
sampler (`_sample_network`, `P`), and Stage 3's generic per-replicate
runner (`_run_one_replicate`). Only the write-evidence and report-writer
are new, so this charter's evidence hashes docs/stage3e_charter.md
rather than Stage 3b's, per the project's provenance discipline.
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

import pandas as pd
import yaml

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage2h import P, _sample_network
from mintnet.experiments.stage3 import _run_one_replicate
from mintnet.experiments.stage3b import (
    _BOOTSTRAP_STREAM,
    _DATA_STREAM,
    Stage3bConfig,
    _category,
    _condition_seed,
    load_stage3b_config,
)


def _repository_root(config: Stage3bConfig) -> Path:
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


def _resolved_config(config: Stage3bConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "screening_alpha": config.screening_alpha,
        "replicates": config.replicates,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "bootstraps": config.bootstraps,
        "master_seed": config.master_seed,
        "pi_min_candidates": list(config.pi_min_candidates),
        "minimum_overlap_indirect_tpr": config.minimum_overlap_indirect_tpr,
        "maximum_true_edge_fpr": config.maximum_true_edge_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
    }


def _write_evidence(config: Stage3bConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage3e_charter.md"
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


def run_stage3e(config: Stage3bConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 3e conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    selected_form = select_form(fit_candidate_forms())

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        dpi_alpha = selected_form.predict(float(n))
        for replicate in range(config.replicates):
            data_seed = _condition_seed(config.master_seed, _DATA_STREAM, sample_index, replicate)
            bootstrap_seed = _condition_seed(config.master_seed, _BOOTSTRAP_STREAM, sample_index, replicate)
            rows.extend(
                _run_one_replicate(
                    dgp="overlap_p30",
                    n=n,
                    replicate=replicate,
                    data_seed=data_seed,
                    bootstrap_seed=bootstrap_seed,
                    screening_alpha=config.screening_alpha,
                    dpi_alpha=dpi_alpha,
                    bootstraps=config.bootstraps,
                    p=P,
                    category_fn=_category,
                    sample_fn=lambda rng, n=n: _sample_network(n, config.strength, rng),
                )
            )

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage3e_reporting import write_stage3e_report

    write_stage3e_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage3e(load_stage3b_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
