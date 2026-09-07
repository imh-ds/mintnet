"""Deterministic raw-evidence runner for the frozen Stage 4q Part B
decomposed-metric re-scoring of the sequential engine on the overlap
network. See docs/stage4q_charter.md.

Reproduces Stage 4p's own sequential-engine-on-overlap draws bit-for-
bit (identical seed derivation, identical D-012 general alpha), but
additionally extracts the 4 overlap cross-branch pairs' per-pair
candidacy/confirmation detail -- exactly Stage 4h's own extraction --
so both the composite TPR (Stage 4p's own metric) and the proper
candidacy/conditional-accuracy decomposition (Stage 4e's own metric,
D-032's own correction) can be reported side by side.
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

from mintnet.experiments import stage2d
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage4p import DGPS, _condition_seed
from mintnet.pipeline import sequential_screen_and_prune_detailed

_OVERLAP_DGP_INDEX = DGPS.index("overlap")


@dataclass(frozen=True)
class Stage4qBConfig:
    sample_sizes: tuple[int, ...]
    strength: float
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


def load_stage4q_b_config(path: Path) -> Stage4qBConfig:
    """Load a Stage 4q Part B configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4q Part B configuration must be a mapping")

    return Stage4qBConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_conditional_accuracy=float(values["minimum_conditional_accuracy"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        required_margin=float(values["required_margin"]),
        source_path=path.resolve(),
    )


def _repository_root(config: Stage4qBConfig) -> Path:
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


def _resolved_config(config: Stage4qBConfig, alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_conditional_accuracy": config.minimum_conditional_accuracy,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "required_margin": config.required_margin,
        "d012_alpha_by_n": alpha_by_n,
    }


def _write_evidence(
    config: Stage4qBConfig, output_dir: Path, raw: pd.DataFrame, alpha_by_n: dict[int, float], runtime_seconds: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4q_charter.md"
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
    # Matches Stage 4h's own convention exactly (underscore-separated,
    # not concatenated -- composed p=15 indices can be two digits, e.g.
    # "6_10", where concatenation would be ambiguous).
    return f"{i}_{j}"


def run_stage4q_b(config: Stage4qBConfig, output_dir: Path) -> pd.DataFrame:
    """Re-score the sequential engine's overlap-network draws (Stage 4p's
    own seeds and alpha, bit-for-bit) with the proper candidacy/
    conditional-accuracy decomposition alongside the original composite
    TPR."""
    run_started = time.perf_counter()

    selected = select_form(fit_candidate_forms())
    alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        alpha = alpha_by_n[n]
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, _OVERLAP_DGP_INDEX, sample_index, replicate)
            started = time.perf_counter()
            row_status, row_error = "ok", ""
            composite: dict[str, object] = {
                "chain_indirect_tpr": np.nan,
                "fork_indirect_tpr": np.nan,
                "overlap_indirect_tpr": np.nan,
                "true_edge_prune_fpr": np.nan,
            }
            pair_row: dict[str, object] = {}
            for i, j in stage2d.OVERLAP_INDIRECT:
                label = _pair_label(i, j)
                pair_row[f"candidate_{label}"] = np.nan
                pair_row[f"correctly_pruned_{label}"] = np.nan
            try:
                data = stage2d._sample_network(n, config.strength, np.random.default_rng(seed))
                final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                by_pair = {(d.i, d.j): d for d in decisions}
                screened = np.zeros((stage2d.P, stage2d.P), dtype=bool)
                for d in decisions:
                    screened[d.i, d.j] = screened[d.j, d.i] = True
                score = stage2d._score(screened, final, stage2d.P)
                composite = {
                    "chain_indirect_tpr": score["chain_indirect_tpr"],
                    "fork_indirect_tpr": score["fork_indirect_tpr"],
                    "overlap_indirect_tpr": score["overlap_indirect_tpr"],
                    "true_edge_prune_fpr": score["true_edge_prune_fpr"],
                }
                for i, j in stage2d.OVERLAP_INDIRECT:
                    label = _pair_label(i, j)
                    decision = by_pair.get((i, j))
                    if decision is None:
                        pair_row[f"candidate_{label}"] = False
                        pair_row[f"correctly_pruned_{label}"] = np.nan
                    else:
                        pair_row[f"candidate_{label}"] = True
                        pair_row[f"correctly_pruned_{label}"] = not decision.confirmed
            except Exception as exc:  # raw evidence must retain pipeline failures
                row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "n": n,
                    "alpha": alpha,
                    "replicate": replicate,
                    "seed": seed,
                    **composite,
                    **pair_row,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, alpha_by_n, time.perf_counter() - run_started)
    from mintnet.experiments.stage4q_b_reporting import write_stage4q_b_report

    write_stage4q_b_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4q_b(load_stage4q_b_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
