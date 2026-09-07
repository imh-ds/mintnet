"""Deterministic raw-evidence runner for the frozen Stage 4h composed-
pipeline-with-noise experiment (sequential engine, p=15). See
docs/stage4h_charter.md.

Reuses Stage 2d's exact p=15 DGP and ground truth
(`mintnet.experiments.stage2d._sample_network`, `TRUE_CANDIDATE_PAIRS`,
`TRUE_DIRECT_EDGES`, `CHAIN_INDIRECT`, `FORK_INDIRECT`,
`OVERLAP_INDIRECT`, `_score`) unmodified, Stage 4g's fitted alpha(N)
formula (re-derived deterministically from Stage 4e's own raw evidence,
not re-selected), and Stage 4a's sequential engine
(`sequential_screen_and_prune_detailed`) unmodified. Only the runner and
reporting -- including the required candidacy/conditional-accuracy
decomposition for the 4 overlap cross-branch pairs -- are new.
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

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage2d import (
    CHAIN_INDIRECT,
    FORK_INDIRECT,
    NOISE_COUNT,
    OVERLAP_INDIRECT,
    P,
    TRUE_CANDIDATE_PAIRS,
    TRUE_DIRECT_EDGES,
    _sample_network,
    _score,
)
from mintnet.experiments.stage4g_fit import compute_fitting_points
from mintnet.pipeline import sequential_screen_and_prune_detailed

_STREAM = 3  # distinct from Stage 4b/d/e/f/g/c's own stream tags


@dataclass(frozen=True)
class Stage4hConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_true_edge_prune_fpr: float
    false_edge_rate_tolerance: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4h_config(path: Path) -> Stage4hConfig:
    """Load a Stage 4h configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4h configuration must be a mapping")

    return Stage4hConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        false_edge_rate_tolerance=float(values["false_edge_rate_tolerance"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, _STREAM, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4hConfig) -> Path:
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


def _resolved_config(config: Stage4hConfig, predicted_alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "noise_count": NOISE_COUNT,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
        "predicted_alpha_by_n": predicted_alpha_by_n,
    }


def _write_evidence(
    config: Stage4hConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    predicted_alpha_by_n: dict[int, float],
    stage4e_raw_path: Path,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, predicted_alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4h_charter.md"
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    metadata = {
        "charter_sha256": charter_hash,
        "stage4e_raw_evidence_path": str(stage4e_raw_path),
        "stage4e_raw_evidence_sha256": hashlib.sha256(stage4e_raw_path.read_bytes()).hexdigest(),
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _pair_label(i: int, j: int) -> str:
    return f"{i}_{j}"


def run_stage4h(config: Stage4hConfig, stage4e_raw_path: Path, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 4h conditions and persist only raw evidence."""
    run_started = time.perf_counter()

    fitting_points = compute_fitting_points(stage4e_raw_path)
    forms = fit_candidate_forms(fitting_points)
    selected = select_form(forms)
    predicted_alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        alpha = predicted_alpha_by_n[n]
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, sample_index, replicate)
            started = time.perf_counter()
            row_status, row_error = "ok", ""
            metrics: dict[str, object] = {
                "chain_indirect_tpr": np.nan,
                "fork_indirect_tpr": np.nan,
                "overlap_indirect_tpr": np.nan,
                "true_edge_prune_fpr": np.nan,
                "screening_false_edge_rate": np.nan,
                "final_false_edge_rate": np.nan,
            }
            pair_row: dict[str, object] = {}
            for i, j in OVERLAP_INDIRECT:
                label = _pair_label(i, j)
                pair_row[f"candidate_{label}"] = np.nan
                pair_row[f"correctly_pruned_{label}"] = np.nan
                pair_row[f"tested_neighbors_{label}"] = ""
            try:
                data = _sample_network(n, config.strength, np.random.default_rng(seed))
                final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                by_pair = {(d.i, d.j): d for d in decisions}
                screened = np.zeros((P, P), dtype=bool)
                for d in decisions:
                    screened[d.i, d.j] = screened[d.j, d.i] = True
                metrics = _score(screened, final, P)
                for i, j in OVERLAP_INDIRECT:
                    label = _pair_label(i, j)
                    decision = by_pair.get((i, j))
                    if decision is None:
                        pair_row[f"candidate_{label}"] = False
                        pair_row[f"correctly_pruned_{label}"] = np.nan
                        pair_row[f"tested_neighbors_{label}"] = ""
                    else:
                        pair_row[f"candidate_{label}"] = True
                        pair_row[f"correctly_pruned_{label}"] = not decision.confirmed
                        pair_row[f"tested_neighbors_{label}"] = ",".join(str(k) for k in decision.tested_neighbors)
            except Exception as exc:  # raw evidence must retain pipeline failures
                row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "n": n,
                    "alpha": alpha,
                    "replicate": replicate,
                    "seed": seed,
                    **metrics,
                    **pair_row,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, predicted_alpha_by_n, stage4e_raw_path, time.perf_counter() - run_started)
    from mintnet.experiments.stage4h_reporting import write_stage4h_report

    write_stage4h_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stage4e-raw-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4h(load_stage4h_config(arguments.config), arguments.stage4e_raw_evidence, arguments.output)


if __name__ == "__main__":
    main()
