"""Deterministic raw-evidence runner for the frozen Stage 1L shared-node-overlap experiment."""

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

from mintnet.dpi import prune_pair
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.simulation import sample_overlapping_triangles

TRUE_EDGES: tuple[tuple[int, int], ...] = ((0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4))
INDIRECT_EDGES: tuple[tuple[int, int], ...] = ((0, 3), (0, 4), (1, 3), (1, 4))


@dataclass(frozen=True)
class Stage1lConfig:
    sample_sizes: tuple[int, ...]
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


def load_stage1l_config(path: Path) -> Stage1lConfig:
    """Load a Stage 1L configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 1L configuration must be a mapping")

    return Stage1lConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        required_margin=float(values["required_margin"]),
        source_path=path.resolve(),
    )


def _condition_seed(config: Stage1lConfig, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.master_seed, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage1lConfig) -> Path:
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


def _resolved_config(config: Stage1lConfig, alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "required_margin": config.required_margin,
        "predicted_alpha_by_n": alpha_by_n,
    }


def _write_evidence(
    config: Stage1lConfig, output_dir: Path, raw: pd.DataFrame, alpha_by_n: dict[int, float], runtime_seconds: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage1l_charter.md"
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


def run_stage1l(config: Stage1lConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 1L conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    selected_form = select_form(fit_candidate_forms())
    alpha_by_n = {n: selected_form.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        alpha = alpha_by_n[n]
        for replicate in range(config.replicates):
            seed = _condition_seed(config, sample_index, replicate)
            started = time.perf_counter()
            row_status, row_error = "ok", ""
            indirect_pruned = true_retained = np.nan
            try:
                data = sample_overlapping_triangles(n, rng=np.random.default_rng(seed))
                indirect_pruned = 0
                for a, b in INDIRECT_EDGES:
                    others = [k for k in range(5) if k not in (a, b)]
                    retained = prune_pair(data, a, b, others, alpha)
                    if not retained:
                        indirect_pruned += 1
                true_retained = 0
                for a, b in TRUE_EDGES:
                    others = [k for k in range(5) if k not in (a, b)]
                    retained = prune_pair(data, a, b, others, alpha)
                    if retained:
                        true_retained += 1
            except Exception as exc:  # raw evidence must retain pipeline failures
                row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "n": n,
                    "replicate": replicate,
                    "seed": seed,
                    "alpha": alpha,
                    "indirect_prune_tpr": (indirect_pruned / len(INDIRECT_EDGES)) if row_status == "ok" else np.nan,
                    "true_edge_prune_fpr": (
                        1.0 - (true_retained / len(TRUE_EDGES)) if row_status == "ok" else np.nan
                    ),
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, alpha_by_n, time.perf_counter() - run_started)
    from mintnet.experiments.stage1l_reporting import write_stage1l_report

    write_stage1l_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage1l(load_stage1l_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
