"""Deterministic raw-evidence runner for the frozen Stage 4m cascading-
error stress test for chain/fork/hub. See docs/stage4m_charter.md.

Runs both engines on identical simulated data every replicate (one of
three motifs -- chain, fork, hub-2-children -- at a deliberately weak
strength=0.15, plus 0 or 5 pure-noise columns from a separate RNG
stream, so the motif draw is bit-identical across the paired noise
conditions). No engine change: `mintnet.pipeline.
sequential_screen_and_prune_detailed` and `mintnet.pipeline.
compose_screen_then_prune` are both reused unmodified, mirroring Stage
4c's own mechanism exactly, generalized from one asymmetric triangle to
three structurally-symmetric motifs (both direct edges tracked per
motif, since neither has a single designated "weak" edge).
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

from mintnet.pipeline import compose_screen_then_prune, sequential_screen_and_prune_detailed
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import sample_chain, sample_hub, sample_measured_fork

MOTIFS: tuple[str, ...] = ("chain", "fork", "hub")

_SAMPLERS = {
    "chain": lambda n, strength, rng: sample_chain(n, strength, rng),
    "fork": lambda n, strength, rng: sample_measured_fork(n, strength, rng),
    "hub": lambda n, strength, rng: sample_hub(n, strength, children=2, rng=rng),
}
_DIRECT_EDGES = {
    "chain": ((0, 1), (1, 2)),
    "fork": ((0, 1), (1, 2)),
    "hub": ((0, 1), (0, 2)),
}

_MOTIF_STREAM = 1
_NOISE_STREAM = 2


@dataclass(frozen=True)
class Stage4mConfig:
    strength: float
    sample_sizes: tuple[int, ...]
    alphas: tuple[float, ...]
    noise_counts: tuple[int, ...]
    replicates: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4m_config(path: Path) -> Stage4mConfig:
    """Load a Stage 4m configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4m configuration must be a mapping")

    return Stage4mConfig(
        strength=float(values["strength"]),
        sample_sizes=_values(values, "sample_sizes", int),
        alphas=_values(values, "alphas", float),
        noise_counts=_values(values, "noise_counts", int),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, motif_index: int, stream: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, motif_index, stream, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4mConfig) -> Path:
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


def _resolved_config(config: Stage4mConfig) -> dict[str, object]:
    return {
        "strength": config.strength,
        "sample_sizes": list(config.sample_sizes),
        "alphas": list(config.alphas),
        "noise_counts": list(config.noise_counts),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
    }


def _write_evidence(config: Stage4mConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4m_charter.md"
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
    return f"{i}{j}"


def _sample(
    motif: str, n: int, strength: float, noise_count: int, master_seed: int, motif_index: int,
    sample_index: int, replicate: int,
) -> np.ndarray:
    motif_seed = _condition_seed(master_seed, motif_index, _MOTIF_STREAM, sample_index, replicate)
    data = _SAMPLERS[motif](n, strength, np.random.default_rng(motif_seed))
    if noise_count == 0:
        return data
    noise_seed = _condition_seed(master_seed, motif_index, _NOISE_STREAM, sample_index, replicate)
    noise = np.random.default_rng(noise_seed).normal(size=(n, noise_count))
    return np.column_stack([data, noise])


def _sequential_outcome(data: np.ndarray, alpha: float, edges: tuple[tuple[int, int], ...]) -> dict[str, object]:
    final, decisions = sequential_screen_and_prune_detailed(data, alpha)
    by_pair = {(d.i, d.j): d for d in decisions}
    metrics: dict[str, object] = {}
    for i, j in edges:
        label = _pair_label(i, j)
        decision = by_pair.get((i, j))
        if decision is None:
            metrics[f"sequential_candidate_{label}"] = False
            metrics[f"sequential_retained_{label}"] = bool(final[i, j])
            metrics[f"sequential_tested_neighbors_{label}"] = ""
            metrics[f"sequential_noise_neighbor_used_{label}"] = False
        else:
            tested = decision.tested_neighbors
            metrics[f"sequential_candidate_{label}"] = True
            metrics[f"sequential_retained_{label}"] = bool(final[i, j])
            metrics[f"sequential_tested_neighbors_{label}"] = ",".join(str(k) for k in tested)
            metrics[f"sequential_noise_neighbor_used_{label}"] = any(k >= 3 for k in tested)
    return metrics


def _conservative_outcome(data: np.ndarray, alpha: float, edges: tuple[tuple[int, int], ...]) -> dict[str, object]:
    evidence = compute_pairwise_screening_evidence(data)
    flagged = screen_uncorrected(evidence, alpha)
    final, shapes = compose_screen_then_prune(data, flagged, alpha)
    metrics: dict[str, object] = {}
    for i, j in edges:
        label = _pair_label(i, j)
        component = next((c for c in shapes if {i, j} <= c), None)
        is_validated_shape = bool(shapes[component]["is_validated_shape"]) if component is not None else False
        metrics[f"conservative_candidate_{label}"] = bool(flagged[i, j])
        metrics[f"conservative_retained_{label}"] = bool(final[i, j])
        metrics[f"conservative_component_size_{label}"] = len(component) if component is not None else 0
        metrics[f"conservative_component_is_validated_clique_{label}"] = is_validated_shape
    return metrics


def _empty_metrics(edges: tuple[tuple[int, int], ...]) -> dict[str, object]:
    metrics: dict[str, object] = {}
    for i, j in edges:
        label = _pair_label(i, j)
        metrics[f"sequential_candidate_{label}"] = np.nan
        metrics[f"sequential_retained_{label}"] = np.nan
        metrics[f"sequential_tested_neighbors_{label}"] = ""
        metrics[f"sequential_noise_neighbor_used_{label}"] = np.nan
        metrics[f"conservative_candidate_{label}"] = np.nan
        metrics[f"conservative_retained_{label}"] = np.nan
        metrics[f"conservative_component_size_{label}"] = np.nan
        metrics[f"conservative_component_is_validated_clique_{label}"] = np.nan
    return metrics


def run_stage4m(config: Stage4mConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 4m conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for motif_index, motif in enumerate(MOTIFS):
        edges = _DIRECT_EDGES[motif]
        for sample_index, n in enumerate(config.sample_sizes):
            for noise_count in config.noise_counts:
                for replicate in range(config.replicates):
                    started = time.perf_counter()
                    try:
                        data = _sample(
                            motif, n, config.strength, noise_count, config.master_seed, motif_index,
                            sample_index, replicate,
                        )
                        status, error = "ok", ""
                    except Exception as exc:  # raw evidence must retain pipeline failures
                        data = None
                        status, error = "error", f"{type(exc).__name__}: {exc}"

                    for alpha in config.alphas:
                        row_status, row_error = status, error
                        metrics = _empty_metrics(edges)
                        if data is not None:
                            try:
                                metrics.update(_sequential_outcome(data, alpha, edges))
                                metrics.update(_conservative_outcome(data, alpha, edges))
                            except Exception as exc:  # retain pruning failures by alpha
                                row_status = "error"
                                row_error = f"{type(exc).__name__}: {exc}"

                        rows.append(
                            {
                                "motif": motif,
                                "n": n,
                                "noise_count": noise_count,
                                "alpha": alpha,
                                "replicate": replicate,
                                **metrics,
                                "elapsed_seconds": time.perf_counter() - started,
                                "status": row_status,
                                "error": row_error,
                            }
                        )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage4m_reporting import write_stage4m_report

    write_stage4m_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4m(load_stage4m_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
