"""Deterministic raw-evidence runner for the frozen Stage 2b composition experiment."""

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

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.pipeline import compose_screen_then_prune
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import TRUE_PAIR_INDICES, sample_screening_network

TRUE_DIRECT_EDGES: frozenset[tuple[int, int]] = frozenset(
    {(0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (6, 8), (7, 8)}
)
INDIRECT_EDGES: frozenset[tuple[int, int]] = frozenset({(0, 2), (3, 5)})
MOTIF_COMPONENTS: dict[str, frozenset[int]] = {
    "chain": frozenset({0, 1, 2}),
    "fork": frozenset({3, 4, 5}),
    "triangle": frozenset({6, 7, 8}),
}


@dataclass(frozen=True)
class Stage2bConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    triangle_family: str
    noise_count: int
    screening_alpha: float
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_true_edge_prune_fpr: float
    false_edge_rate_tolerance: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float] | type[str]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage2b_config(path: Path) -> Stage2bConfig:
    """Load a Stage 2b configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 2b configuration must be a mapping")

    return Stage2bConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        triangle_family=str(values["triangle_family"]),
        noise_count=int(values["noise_count"]),
        screening_alpha=float(values["screening_alpha"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        false_edge_rate_tolerance=float(values["false_edge_rate_tolerance"]),
        source_path=path.resolve(),
    )


def _condition_seed(config: Stage2bConfig, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.master_seed, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


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
    charter = repository_root / "docs/stage2b_charter.md"
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


def _score(screened: np.ndarray, final: np.ndarray, p: int) -> dict[str, float]:
    all_pairs = set(combinations(range(p), 2))
    null_pairs = all_pairs - TRUE_PAIR_INDICES

    indirect_pruned = sum(1 for i, j in INDIRECT_EDGES if not final[i, j])
    true_retained = sum(1 for i, j in TRUE_DIRECT_EDGES if final[i, j])
    screening_false = sum(1 for i, j in null_pairs if screened[i, j])
    final_false = sum(1 for i, j in null_pairs if final[i, j])

    return {
        "indirect_prune_tpr": indirect_pruned / len(INDIRECT_EDGES),
        "true_edge_prune_fpr": 1.0 - (true_retained / len(TRUE_DIRECT_EDGES)),
        "screening_false_edge_rate": screening_false / len(null_pairs),
        "final_false_edge_rate": final_false / len(null_pairs),
    }


def run_stage2b(config: Stage2bConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 2b conditions and persist only raw evidence."""
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
    from mintnet.experiments.stage2b_reporting import write_stage2b_report

    write_stage2b_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage2b(load_stage2b_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
