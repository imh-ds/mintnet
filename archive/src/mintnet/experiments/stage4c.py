"""Deterministic raw-evidence runner for the frozen Stage 4c cascading-
error stress test. See docs/stage4c_charter.md.

Runs both engines on identical simulated data every replicate (the
"strong" asymmetric triangle -- Stage 1's own fixture, weak true edge
(1,2) -- plus 0 or 5 pure-noise columns from a separate RNG stream, so
the triangle draw is bit-identical across the paired noise conditions).
No engine change: `mintnet.pipeline.sequential_screen_and_prune_detailed`
and `mintnet.pipeline.compose_screen_then_prune` are both reused
unmodified.
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
from mintnet.simulation import sample_precision_triangle

_WEAK_EDGE = (1, 2)
_TRIANGLE_STREAM = 1
_NOISE_STREAM = 2


@dataclass(frozen=True)
class Stage4cConfig:
    sample_sizes: tuple[int, ...]
    alphas: tuple[float, ...]
    noise_counts: tuple[int, ...]
    replicates: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4c_config(path: Path) -> Stage4cConfig:
    """Load a Stage 4c configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4c configuration must be a mapping")

    return Stage4cConfig(
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


def _repository_root(config: Stage4cConfig) -> Path:
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


def _resolved_config(config: Stage4cConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "alphas": list(config.alphas),
        "noise_counts": list(config.noise_counts),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
    }


def _write_evidence(config: Stage4cConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4c_charter.md"
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


def _sample(n: int, noise_count: int, master_seed: int, sample_index: int, replicate: int) -> np.ndarray:
    triangle_seed = _condition_seed(master_seed, _TRIANGLE_STREAM, sample_index, replicate)
    triangle = sample_precision_triangle("strong", n, np.random.default_rng(triangle_seed))
    if noise_count == 0:
        return triangle
    noise_seed = _condition_seed(master_seed, _NOISE_STREAM, sample_index, replicate)
    noise = np.random.default_rng(noise_seed).normal(size=(n, noise_count))
    return np.column_stack([triangle, noise])


def _sequential_outcome(data: np.ndarray, alpha: float) -> dict[str, object]:
    final, decisions = sequential_screen_and_prune_detailed(data, alpha)
    i, j = _WEAK_EDGE
    decision = next((d for d in decisions if (d.i, d.j) == (i, j)), None)
    if decision is None:
        return {
            "sequential_candidate": False,
            "sequential_retained": bool(final[i, j]),
            "sequential_tested_neighbors": "",
            "sequential_noise_neighbor_used": False,
        }
    tested = decision.tested_neighbors
    return {
        "sequential_candidate": True,
        "sequential_retained": bool(final[i, j]),
        "sequential_tested_neighbors": ",".join(str(k) for k in tested),
        "sequential_noise_neighbor_used": any(k >= 3 for k in tested),
    }


def _conservative_outcome(data: np.ndarray, alpha: float) -> dict[str, object]:
    evidence = compute_pairwise_screening_evidence(data)
    flagged = screen_uncorrected(evidence, alpha)
    final, shapes = compose_screen_then_prune(data, flagged, alpha)
    i, j = _WEAK_EDGE
    component = next((c for c in shapes if {i, j} <= c), None)
    is_validated_shape = bool(shapes[component]["is_validated_shape"]) if component is not None else False
    return {
        "conservative_candidate": bool(flagged[i, j]),
        "conservative_retained": bool(final[i, j]),
        "conservative_component_size": len(component) if component is not None else 0,
        "conservative_component_is_validated_clique": is_validated_shape,
    }


def run_stage4c(config: Stage4cConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 4c conditions and persist only raw evidence."""
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
                    metrics: dict[str, object] = {
                        "sequential_candidate": np.nan,
                        "sequential_retained": np.nan,
                        "sequential_tested_neighbors": "",
                        "sequential_noise_neighbor_used": np.nan,
                        "conservative_candidate": np.nan,
                        "conservative_retained": np.nan,
                        "conservative_component_size": np.nan,
                        "conservative_component_is_validated_clique": np.nan,
                    }
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
    from mintnet.experiments.stage4c_reporting import write_stage4c_report

    write_stage4c_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4c(load_stage4c_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
