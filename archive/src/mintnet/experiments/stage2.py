"""Deterministic raw-evidence runner for the frozen Stage 2 screening experiment."""

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
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mintnet.screening import (
    benjamini_hochberg_threshold,
    compute_pairwise_screening_evidence,
    screen_uncorrected,
)
from mintnet.simulation import TRUE_PAIR_INDICES, sample_screening_network


@dataclass(frozen=True)
class Stage2Config:
    sample_sizes: tuple[int, ...]
    strength: float
    triangle_family: str
    noise_count: int
    uncorrected_alphas: tuple[float, ...]
    bh_q_values: tuple[float, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_recall: float
    maximum_fdr: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float] | type[str]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage2_config(path: Path) -> Stage2Config:
    """Load a Stage 2 configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 2 configuration must be a mapping")

    return Stage2Config(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        triangle_family=str(values["triangle_family"]),
        noise_count=int(values["noise_count"]),
        uncorrected_alphas=_values(values, "uncorrected_alphas", float),
        bh_q_values=_values(values, "bh_q_values", float),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_recall=float(values["minimum_recall"]),
        maximum_fdr=float(values["maximum_fdr"]),
        source_path=path.resolve(),
    )


def _condition_seed(config: Stage2Config, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.master_seed, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage2Config) -> Path:
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


def _resolved_config(config: Stage2Config) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "triangle_family": config.triangle_family,
        "noise_count": config.noise_count,
        "uncorrected_alphas": list(config.uncorrected_alphas),
        "bh_q_values": list(config.bh_q_values),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_recall": config.minimum_recall,
        "maximum_fdr": config.maximum_fdr,
    }


def _write_evidence(config: Stage2Config, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage2_charter.md"
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


def _score_flagged(flagged: np.ndarray, p: int) -> dict[str, float]:
    all_pairs = set(combinations(range(p), 2))
    null_pairs = all_pairs - TRUE_PAIR_INDICES
    true_positives = sum(1 for i, j in TRUE_PAIR_INDICES if flagged[i, j])
    false_positives = sum(1 for i, j in null_pairs if flagged[i, j])
    total_flagged = true_positives + false_positives
    return {
        # Raw counts, kept so the FDR gate can be computed pooled across
        # replicates (sum FP / sum total flagged, per the charter's
        # "fraction of all flagged pairs" definition) rather than as a mean
        # of per-replicate ratios, which is a different (and biased, for
        # replicates with few or zero flagged pairs) quantity.
        "true_positives": true_positives,
        "false_positives": false_positives,
        "total_flagged": total_flagged,
        "true_pair_count": len(TRUE_PAIR_INDICES),
        "null_pair_count": len(null_pairs),
        "recall": true_positives / len(TRUE_PAIR_INDICES),
        "false_discovery_rate": (false_positives / total_flagged) if total_flagged > 0 else 0.0,
        "per_edge_fpr": false_positives / len(null_pairs),
        "any_false_edge": float(false_positives > 0),
    }


def run_stage2(config: Stage2Config, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 2 conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    p = 9 + config.noise_count
    rules: list[tuple[str, float]] = [("uncorrected", a) for a in config.uncorrected_alphas]
    rules += [("bh", q) for q in config.bh_q_values]

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        for replicate in range(config.replicates):
            seed = _condition_seed(config, sample_index, replicate)
            started = time.perf_counter()
            try:
                data = sample_screening_network(
                    n, config.strength, config.triangle_family, config.noise_count,
                    np.random.default_rng(seed),
                )
                evidence = compute_pairwise_screening_evidence(data)
                status, error = "ok", ""
            except Exception as exc:  # raw evidence must retain pipeline failures
                evidence = None
                status, error = "error", f"{type(exc).__name__}: {exc}"

            for rule_kind, threshold in rules:
                row_status, row_error = status, error
                metrics: dict[str, float] = {
                    "true_positives": np.nan,
                    "false_positives": np.nan,
                    "total_flagged": np.nan,
                    "true_pair_count": np.nan,
                    "null_pair_count": np.nan,
                    "recall": np.nan,
                    "false_discovery_rate": np.nan,
                    "per_edge_fpr": np.nan,
                    "any_false_edge": np.nan,
                }
                if evidence is not None:
                    try:
                        flagged = (
                            screen_uncorrected(evidence, threshold)
                            if rule_kind == "uncorrected"
                            else benjamini_hochberg_threshold(evidence, threshold)
                        )
                        metrics = _score_flagged(flagged, p)
                    except Exception as exc:  # retain scoring failures by rule
                        row_status = "error"
                        row_error = f"{type(exc).__name__}: {exc}"
                rows.append(
                    {
                        "n": n,
                        "replicate": replicate,
                        "seed": seed,
                        "rule_kind": rule_kind,
                        "threshold": threshold,
                        **metrics,
                        "elapsed_seconds": time.perf_counter() - started,
                        "status": row_status,
                        "error": row_error,
                    }
                )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage2_reporting import write_stage2_report

    write_stage2_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage2(load_stage2_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
