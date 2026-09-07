"""Deterministic raw-evidence runner for the frozen Stage 4n cascading-
error stress test for overlap. See docs/stage4n_charter.md.

Runs both engines on identical simulated data every replicate (the
shared-node-overlap motif -- Stage 1L's own fixture, 5 real columns,
column 2 shared between two triangles -- plus 0 or 5 pure-noise columns
from a separate RNG stream, so the overlap draw is bit-identical across
the paired noise conditions). No engine change: `mintnet.pipeline.
sequential_screen_and_prune_detailed` and `mintnet.pipeline.
compose_screen_then_prune` are both reused unmodified, mirroring Stage
4c/4m's own mechanism exactly, generalized to overlap's 6 true direct
edges (pooled, since none is a single designated weak edge) and adding
a Q4 check for a cascading pathway unique to overlap's own structure
(the opposite-triangle nodes), independent of noise.
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

from mintnet.experiments.stage1l import TRUE_EDGES
from mintnet.pipeline import compose_screen_then_prune, sequential_screen_and_prune_detailed
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import sample_overlapping_triangles

_OVERLAP_STREAM = 1
_NOISE_STREAM = 2
_NOISE_START_INDEX = 5  # overlap's own 5 real columns occupy indices 0-4

# The opposite-triangle real nodes for each direct edge -- overlap's own
# columns 0,1,2 form one triangle, 2,3,4 the other, column 2 shared.
OPPOSITE_NODES: dict[tuple[int, int], tuple[int, int]] = {
    (0, 1): (3, 4),
    (0, 2): (3, 4),
    (1, 2): (3, 4),
    (2, 3): (0, 1),
    (2, 4): (0, 1),
    (3, 4): (0, 1),
}


@dataclass(frozen=True)
class Stage4nConfig:
    sample_sizes: tuple[int, ...]
    alphas: tuple[float, ...]
    noise_counts: tuple[int, ...]
    replicates: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4n_config(path: Path) -> Stage4nConfig:
    """Load a Stage 4n configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4n configuration must be a mapping")

    return Stage4nConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        alphas=_values(values, "alphas", float),
        noise_counts=_values(values, "noise_counts", int),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, stream: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, stream, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4nConfig) -> Path:
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


def _resolved_config(config: Stage4nConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "alphas": list(config.alphas),
        "noise_counts": list(config.noise_counts),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
    }


def _write_evidence(config: Stage4nConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4n_charter.md"
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


def _sample(n: int, noise_count: int, master_seed: int, sample_index: int, replicate: int) -> np.ndarray:
    overlap_seed = _condition_seed(master_seed, _OVERLAP_STREAM, sample_index, replicate)
    data = sample_overlapping_triangles(n, np.random.default_rng(overlap_seed))
    if noise_count == 0:
        return data
    noise_seed = _condition_seed(master_seed, _NOISE_STREAM, sample_index, replicate)
    noise = np.random.default_rng(noise_seed).normal(size=(n, noise_count))
    return np.column_stack([data, noise])


def _sequential_outcome(data: np.ndarray, alpha: float) -> dict[str, object]:
    final, decisions = sequential_screen_and_prune_detailed(data, alpha)
    by_pair = {(d.i, d.j): d for d in decisions}
    metrics: dict[str, object] = {}
    for i, j in TRUE_EDGES:
        label = _pair_label(i, j)
        decision = by_pair.get((i, j))
        opposite = OPPOSITE_NODES[(i, j)]
        if decision is None:
            metrics[f"sequential_candidate_{label}"] = False
            metrics[f"sequential_retained_{label}"] = bool(final[i, j])
            metrics[f"sequential_tested_neighbors_{label}"] = ""
            metrics[f"sequential_noise_neighbor_used_{label}"] = False
            metrics[f"sequential_opposite_neighbor_used_{label}"] = False
        else:
            tested = decision.tested_neighbors
            metrics[f"sequential_candidate_{label}"] = True
            metrics[f"sequential_retained_{label}"] = bool(final[i, j])
            metrics[f"sequential_tested_neighbors_{label}"] = ",".join(str(k) for k in tested)
            metrics[f"sequential_noise_neighbor_used_{label}"] = any(k >= _NOISE_START_INDEX for k in tested)
            metrics[f"sequential_opposite_neighbor_used_{label}"] = any(k in opposite for k in tested)
    return metrics


def _conservative_outcome(data: np.ndarray, alpha: float) -> dict[str, object]:
    evidence = compute_pairwise_screening_evidence(data)
    flagged = screen_uncorrected(evidence, alpha)
    final, shapes = compose_screen_then_prune(data, flagged, alpha)
    metrics: dict[str, object] = {}
    for i, j in TRUE_EDGES:
        label = _pair_label(i, j)
        component = next((c for c in shapes if {i, j} <= c), None)
        is_validated_shape = bool(shapes[component]["is_validated_shape"]) if component is not None else False
        metrics[f"conservative_candidate_{label}"] = bool(flagged[i, j])
        metrics[f"conservative_retained_{label}"] = bool(final[i, j])
        metrics[f"conservative_component_size_{label}"] = len(component) if component is not None else 0
        metrics[f"conservative_component_is_validated_clique_{label}"] = is_validated_shape
    return metrics


def _empty_metrics() -> dict[str, object]:
    metrics: dict[str, object] = {}
    for i, j in TRUE_EDGES:
        label = _pair_label(i, j)
        metrics[f"sequential_candidate_{label}"] = np.nan
        metrics[f"sequential_retained_{label}"] = np.nan
        metrics[f"sequential_tested_neighbors_{label}"] = ""
        metrics[f"sequential_noise_neighbor_used_{label}"] = np.nan
        metrics[f"sequential_opposite_neighbor_used_{label}"] = np.nan
        metrics[f"conservative_candidate_{label}"] = np.nan
        metrics[f"conservative_retained_{label}"] = np.nan
        metrics[f"conservative_component_size_{label}"] = np.nan
        metrics[f"conservative_component_is_validated_clique_{label}"] = np.nan
    return metrics


def run_stage4n(
    config: Stage4nConfig, output_dir: Path,
    stage4c_summary_path: Path | None = None, stage4m_summary_path: Path | None = None,
) -> pd.DataFrame:
    """Run configured Stage 4n conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        for noise_count in config.noise_counts:
            for replicate in range(config.replicates):
                started = time.perf_counter()
                try:
                    data = _sample(n, noise_count, config.master_seed, sample_index, replicate)
                    status, error = "ok", ""
                except Exception as exc:  # raw evidence must retain pipeline failures
                    data = None
                    status, error = "error", f"{type(exc).__name__}: {exc}"

                for alpha in config.alphas:
                    row_status, row_error = status, error
                    metrics = _empty_metrics()
                    if data is not None:
                        try:
                            metrics.update(_sequential_outcome(data, alpha))
                            metrics.update(_conservative_outcome(data, alpha))
                        except Exception as exc:  # retain pruning failures by alpha
                            row_status = "error"
                            row_error = f"{type(exc).__name__}: {exc}"

                    rows.append(
                        {
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
    from mintnet.experiments.stage4n_reporting import write_stage4n_report

    write_stage4n_report(raw, config, output_dir, stage4c_summary_path, stage4m_summary_path)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stage4c-summary", required=False, type=Path, default=None)
    parser.add_argument("--stage4m-summary", required=False, type=Path, default=None)
    arguments = parser.parse_args()
    run_stage4n(
        load_stage4n_config(arguments.config), arguments.output,
        arguments.stage4c_summary, arguments.stage4m_summary,
    )


if __name__ == "__main__":
    main()
