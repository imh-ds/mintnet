"""Deterministic raw-evidence runner for the frozen Stage 6a
conditioning-set architecture experiment. See docs/stage6a_charter.md.

Compares `mintnet.pipeline.compose_screen_then_prune` (full-component
conditioning, unmodified) against
`mintnet.pipeline.growing_subset_dpi.growing_subset_dpi` (a PC-style
growing-conditioning-set search over MINT's own screened candidate
graph) on identical drawn data every replicate. No new estimator --
both methods use the same Fisher-z partial-correlation primitive.
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
from typing import Callable

import numpy as np
import pandas as pd
import yaml

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage5a import _DGP_REGISTRY as _COMPOSED_DGP_REGISTRY
from mintnet.experiments.stage5a import _condition_seed as _composed_condition_seed
from mintnet.experiments.stage5a import _graph_metrics, _true_adjacency
from mintnet.pipeline import compose_screen_then_prune, growing_subset_dpi
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation.motifs import sample_hub, sample_overlapping_triangles, sample_precision_triangle

METHODS: tuple[str, ...] = ("full_component", "growing_subset")

_ISOLATION_TAG = 601  # disjoint from every prior charter's own seed derivation
_TRIANGLE_TRUE_EDGES: frozenset[tuple[int, int]] = frozenset({(0, 1), (0, 2), (1, 2)})
_HUB_TRUE_EDGES: frozenset[tuple[int, int]] = frozenset({(0, 1), (0, 2), (0, 3)})
_OVERLAP_ISOLATED_TRUE_EDGES: frozenset[tuple[int, int]] = frozenset(
    {(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)}
)

ISOLATION_SHAPES: tuple[str, ...] = (
    "triangle_balanced",
    "triangle_moderate",
    "triangle_strong",
    "hub",
    "overlap_isolated",
)
COMPOSED_SHAPES: tuple[str, ...] = ("chain_fork_hub", "overlap")


def _sample_triangle_balanced(n: int, _strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_precision_triangle("balanced", n, rng)


def _sample_triangle_moderate(n: int, _strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_precision_triangle("moderate", n, rng)


def _sample_triangle_strong(n: int, _strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_precision_triangle("strong", n, rng)


def _sample_hub(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_hub(n, strength, 3, rng)


def _sample_overlap_isolated(n: int, _strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_overlapping_triangles(n, rng)


_ISOLATION_DGP_REGISTRY: dict[str, dict[str, object]] = {
    "triangle_balanced": {"sample": _sample_triangle_balanced, "p": 3, "true_edges": _TRIANGLE_TRUE_EDGES},
    "triangle_moderate": {"sample": _sample_triangle_moderate, "p": 3, "true_edges": _TRIANGLE_TRUE_EDGES},
    "triangle_strong": {"sample": _sample_triangle_strong, "p": 3, "true_edges": _TRIANGLE_TRUE_EDGES},
    "hub": {"sample": _sample_hub, "p": 4, "true_edges": _HUB_TRUE_EDGES},
    "overlap_isolated": {"sample": _sample_overlap_isolated, "p": 5, "true_edges": _OVERLAP_ISOLATED_TRUE_EDGES},
}


def _isolation_condition_seed(master_seed: int, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, _ISOLATION_TAG, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


@dataclass(frozen=True)
class Stage6aConfig:
    isolation_sample_sizes: tuple[int, ...]
    isolation_strength: float
    composed_sample_sizes: tuple[int, ...]
    composed_strength: float
    composed_screening_alpha: float
    max_conditioning_size: int
    replicates: int
    isolation_master_seed: int
    composed_master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    source_path: Path | None = None


def load_stage6a_config(path: Path) -> Stage6aConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 6a configuration must be a mapping")
    return Stage6aConfig(
        isolation_sample_sizes=tuple(int(v) for v in values["isolation_sample_sizes"]),
        isolation_strength=float(values["isolation_strength"]),
        composed_sample_sizes=tuple(int(v) for v in values["composed_sample_sizes"]),
        composed_strength=float(values["composed_strength"]),
        composed_screening_alpha=float(values["composed_screening_alpha"]),
        max_conditioning_size=int(values["max_conditioning_size"]),
        replicates=int(values["replicates"]),
        isolation_master_seed=int(values["isolation_master_seed"]),
        composed_master_seed=int(values["composed_master_seed"]),
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        source_path=path.resolve(),
    )


def _repository_root(config: Stage6aConfig) -> Path:
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


def _run_isolation_cell(
    task: tuple[int, str, int, int, float, Stage6aConfig]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    dgp_index, shape, sample_index, n, dpi_alpha, config = task
    dgp = _ISOLATION_DGP_REGISTRY[shape]
    sample: Callable = dgp["sample"]  # type: ignore[assignment]
    p = int(dgp["p"])
    truth = _true_adjacency(dgp["true_edges"], p)  # type: ignore[arg-type]

    metric_rows: list[dict[str, object]] = []
    size_rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _isolation_condition_seed(config.isolation_master_seed, dgp_index, sample_index, replicate)
        try:
            data = sample(n, config.isolation_strength, np.random.default_rng(seed))
            flagged = np.ones((p, p), dtype=bool)
            np.fill_diagonal(flagged, False)
            status, error = "ok", ""
        except Exception as exc:
            data, flagged = None, None
            status, error = "error", f"{type(exc).__name__}: {exc}"

        metric_rows.extend(
            _score_both_methods(
                "isolation", shape, n, replicate, seed, data, flagged, truth, dpi_alpha, config, status, error
            )
        )
        if data is not None and flagged is not None:
            size_rows.extend(_size_rows("isolation", shape, n, replicate, seed, data, flagged, truth, dpi_alpha, config))
    return metric_rows, size_rows


def _run_composed_cell(
    task: tuple[int, str, int, int, float, Stage6aConfig]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    dgp_index, shape, sample_index, n, dpi_alpha, config = task
    dgp = _COMPOSED_DGP_REGISTRY[shape]
    sample: Callable = dgp["sample"]  # type: ignore[assignment]
    p = int(dgp["p"])
    truth = _true_adjacency(dgp["true_edges"], p)  # type: ignore[arg-type]

    metric_rows: list[dict[str, object]] = []
    size_rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _composed_condition_seed(config.composed_master_seed, dgp_index, sample_index, replicate)
        try:
            data = sample(n, config.composed_strength, np.random.default_rng(seed))
            evidence = compute_pairwise_screening_evidence(data)
            flagged = screen_uncorrected(evidence, config.composed_screening_alpha)
            status, error = "ok", ""
        except Exception as exc:
            data, flagged = None, None
            status, error = "error", f"{type(exc).__name__}: {exc}"

        metric_rows.extend(
            _score_both_methods(
                "composed", shape, n, replicate, seed, data, flagged, truth, dpi_alpha, config, status, error
            )
        )
        if data is not None and flagged is not None:
            size_rows.extend(_size_rows("composed", shape, n, replicate, seed, data, flagged, truth, dpi_alpha, config))
    return metric_rows, size_rows


def _score_both_methods(
    tier: str,
    shape: str,
    n: int,
    replicate: int,
    seed: int,
    data: np.ndarray | None,
    flagged: np.ndarray | None,
    truth: np.ndarray,
    dpi_alpha: float,
    config: Stage6aConfig,
    status: str,
    error: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for method in METHODS:
        started = time.perf_counter()
        row_status, row_error = status, error
        metrics: dict[str, object] = {
            "precision": np.nan, "recall": np.nan, "f1": np.nan, "shd": np.nan, "n_estimated_edges": np.nan,
        }
        if data is not None and flagged is not None:
            try:
                if method == "full_component":
                    estimated, _shapes = compose_screen_then_prune(data, flagged, dpi_alpha)
                else:
                    result = growing_subset_dpi(
                        data, flagged, dpi_alpha, max_conditioning_size=config.max_conditioning_size
                    )
                    estimated = result.adjacency
                metrics = _graph_metrics(estimated, truth)
            except Exception as exc:
                row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

        rows.append(
            {
                "tier": tier, "shape": shape, "method": method, "n": n, "replicate": replicate, "seed": seed,
                **metrics, "elapsed_seconds": time.perf_counter() - started, "status": row_status, "error": row_error,
            }
        )
    return rows


def _size_rows(
    tier: str,
    shape: str,
    n: int,
    replicate: int,
    seed: int,
    data: np.ndarray,
    flagged: np.ndarray,
    truth: np.ndarray,
    dpi_alpha: float,
    config: Stage6aConfig,
) -> list[dict[str, object]]:
    result = growing_subset_dpi(data, flagged, dpi_alpha, max_conditioning_size=config.max_conditioning_size)
    p = flagged.shape[0]
    rows: list[dict[str, object]] = []
    for i in range(p):
        for j in range(i + 1, p):
            if not flagged[i, j]:
                continue
            size = result.conditioning_size_used[(i, j)]
            rows.append(
                {
                    "tier": tier, "shape": shape, "n": n, "replicate": replicate, "seed": seed,
                    "i": i, "j": j, "is_true_edge": bool(truth[i, j]),
                    "final_status": "retained" if result.adjacency[i, j] else "pruned",
                    "conditioning_size": size, "cap_reached": bool(result.cap_reached[(i, j)]),
                }
            )
    return rows


def _resolved_config(config: Stage6aConfig, isolation_alpha_by_n: dict, composed_alpha_by_n: dict) -> dict[str, object]:
    return {
        "isolation_sample_sizes": list(config.isolation_sample_sizes),
        "isolation_strength": config.isolation_strength,
        "composed_sample_sizes": list(config.composed_sample_sizes),
        "composed_strength": config.composed_strength,
        "composed_screening_alpha": config.composed_screening_alpha,
        "max_conditioning_size": config.max_conditioning_size,
        "replicates": config.replicates,
        "isolation_master_seed": config.isolation_master_seed,
        "composed_master_seed": config.composed_master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "isolation_alpha_by_n": isolation_alpha_by_n,
        "composed_alpha_by_n": composed_alpha_by_n,
    }


def _write_evidence(
    config: Stage6aConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    sizes: pd.DataFrame,
    isolation_alpha_by_n: dict,
    composed_alpha_by_n: dict,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    sizes.to_csv(output_dir / "conditioning_sizes.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, isolation_alpha_by_n, composed_alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage6a_charter.md"
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


def _dispatch_task(kind_task: tuple[str, tuple]) -> tuple[list[dict], list[dict]]:
    """Top-level (picklable) dispatch for `ProcessPoolExecutor` -- a
    closure defined inside `run_stage6a` would not be picklable."""
    kind, task = kind_task
    return _run_isolation_cell(task) if kind == "isolation" else _run_composed_cell(task)


def run_stage6a(config: Stage6aConfig, output_dir: Path, max_workers: int | None = None) -> pd.DataFrame:
    import os
    from concurrent.futures import ProcessPoolExecutor

    run_started = time.perf_counter()
    selected = select_form(fit_candidate_forms())
    isolation_alpha_by_n = {n: selected.predict(float(n)) for n in config.isolation_sample_sizes}
    composed_alpha_by_n = {n: selected.predict(float(n)) for n in config.composed_sample_sizes}

    isolation_tasks = [
        (dgp_index, shape, sample_index, n, isolation_alpha_by_n[n], config)
        for dgp_index, shape in enumerate(ISOLATION_SHAPES)
        for sample_index, n in enumerate(config.isolation_sample_sizes)
    ]
    composed_tasks = [
        (dgp_index, shape, sample_index, n, composed_alpha_by_n[n], config)
        for dgp_index, shape in enumerate(COMPOSED_SHAPES)
        for sample_index, n in enumerate(config.composed_sample_sizes)
    ]

    all_tasks = [("isolation", t) for t in isolation_tasks] + [("composed", t) for t in composed_tasks]
    if max_workers is None:
        max_workers = min(len(all_tasks), max(1, (os.cpu_count() or 1) - 1))

    metric_rows: list[dict[str, object]] = []
    size_rows: list[dict[str, object]] = []

    if max_workers > 1 and len(all_tasks) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for m_rows, s_rows in executor.map(_dispatch_task, all_tasks):
                metric_rows.extend(m_rows)
                size_rows.extend(s_rows)
    else:
        for kind_task in all_tasks:
            m_rows, s_rows = _dispatch_task(kind_task)
            metric_rows.extend(m_rows)
            size_rows.extend(s_rows)

    raw = pd.DataFrame(metric_rows)
    sizes = pd.DataFrame(size_rows)
    _write_evidence(config, output_dir, raw, sizes, isolation_alpha_by_n, composed_alpha_by_n, time.perf_counter() - run_started)

    from mintnet.experiments.stage6a_reporting import write_stage6a_report

    write_stage6a_report(raw, sizes, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    arguments = parser.parse_args()
    run_stage6a(load_stage6a_config(arguments.config), arguments.output, max_workers=arguments.workers)


if __name__ == "__main__":
    main()
