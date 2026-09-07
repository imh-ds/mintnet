"""Deterministic raw-evidence runner for the frozen Stage 2c mixed-shape composition experiment.

DGP: chain (0-2), measured fork (3-5), a 4-node hub with 3 children
(6 = hub, 7-9 = children), and noise (10-14) -- a single p=15 network
containing both the 3-node triad shape and the 4-node hub-clique shape
at once. See docs/stage2c_charter.md.
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
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.pipeline import compose_screen_then_prune
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import sample_chain, sample_hub, sample_measured_fork

TRUE_CANDIDATE_PAIRS: frozenset[tuple[int, int]] = frozenset(
    {(0, 1), (0, 2), (1, 2), (3, 4), (3, 5), (4, 5)}
    | set(combinations((6, 7, 8, 9), 2))
)
TRUE_DIRECT_EDGES: frozenset[tuple[int, int]] = frozenset(
    {(0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (6, 8), (6, 9)}
)
INDIRECT_EDGES: frozenset[tuple[int, int]] = frozenset({(0, 2), (3, 5), (7, 8), (7, 9), (8, 9)})
MOTIF_COMPONENTS: dict[str, frozenset[int]] = {
    "chain": frozenset({0, 1, 2}),
    "fork": frozenset({3, 4, 5}),
    "hub": frozenset({6, 7, 8, 9}),
}
NOISE_COUNT = 5
P = 10 + NOISE_COUNT


def _sample_network(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    chain = sample_chain(n, strength, rng)
    fork = sample_measured_fork(n, strength, rng)
    hub = sample_hub(n, strength, children=3, rng=rng)
    noise = rng.normal(size=(n, NOISE_COUNT))
    return np.column_stack([chain, fork, hub, noise])


@dataclass(frozen=True)
class Stage2cConfig:
    sample_sizes: tuple[int, ...]
    strength: float
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


def load_stage2c_config(path: Path) -> Stage2cConfig:
    """Load a Stage 2c configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 2c configuration must be a mapping")

    return Stage2cConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
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


def _condition_seed(config: Stage2cConfig, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([config.master_seed, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage2cConfig) -> Path:
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


def _resolved_config(config: Stage2cConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "noise_count": NOISE_COUNT,
        "screening_alpha": config.screening_alpha,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
    }


def _write_evidence(config: Stage2cConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage2c_charter.md"
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
    null_pairs = all_pairs - TRUE_CANDIDATE_PAIRS

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


def run_stage2c(config: Stage2cConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 2c conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    p = P
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
            chain_is_triad = fork_is_triad = hub_is_validated = np.nan
            try:
                data = _sample_network(n, config.strength, np.random.default_rng(seed))
                evidence = compute_pairwise_screening_evidence(data)
                screened = screen_uncorrected(evidence, config.screening_alpha)
                final, shapes = compose_screen_then_prune(data, screened, dpi_alpha)
                metrics = _score(screened, final, p)

                def _validated(component: frozenset[int]) -> float:
                    shape = shapes.get(component)
                    return float(shape["is_validated_shape"]) if shape is not None else 0.0

                chain_is_triad = _validated(MOTIF_COMPONENTS["chain"])
                fork_is_triad = _validated(MOTIF_COMPONENTS["fork"])
                hub_is_validated = _validated(MOTIF_COMPONENTS["hub"])
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
                    "hub_is_validated": hub_is_validated,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage2c_reporting import write_stage2c_report

    write_stage2c_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage2c(load_stage2c_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
