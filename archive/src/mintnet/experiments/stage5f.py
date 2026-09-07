"""Deterministic raw-evidence runner for the frozen Stage 5f diagnostic:
does MINT's DPI step's clique-shape scope explain part of D-051's
PC-vs-MINT precision gap? See docs/stage5f_charter.md.

Pure attribution, additive instrumentation only -- `compose_screen_then_prune`
itself is called unmodified. Every final edge is categorized after the
fact using the same `shapes` dict the function already returns: an
edge is `dpi_conditioned` if its connected candidate-edge component was
a validated 3/4/5-node clique (DPI actually examined it), or
`passthrough_unconditioned` if the component was never eligible for
DPI at all (including an isolated two-node component), so the edge
survived into the final graph without ever being tested.
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
from mintnet.experiments.stage5a import _DGP_REGISTRY, _condition_seed, _true_adjacency
from mintnet.pipeline import compose_screen_then_prune
from mintnet.pipeline.compose import connected_components
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

DGPS: tuple[str, ...] = ("chain_fork_hub", "overlap")
BUCKETS: tuple[str, ...] = (
    "dpi_conditioned_true_edge",
    "dpi_conditioned_false_edge",
    "passthrough_true_edge",
    "passthrough_false_edge",
)


@dataclass(frozen=True)
class Stage5fConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha: float
    replicates: int
    master_seed: int
    source_path: Path | None = None


def load_stage5f_config(path: Path) -> Stage5fConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 5f configuration must be a mapping")
    return Stage5fConfig(
        sample_sizes=tuple(int(v) for v in values["sample_sizes"]),
        strength=float(values["strength"]),
        screening_alpha=float(values["screening_alpha"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


def _repository_root(config: Stage5fConfig) -> Path:
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


def _attribute_final_edges(
    flagged: np.ndarray, final: np.ndarray, shapes: dict[frozenset[int], dict[str, object]], truth: np.ndarray
) -> dict[str, int]:
    """Categorize every surviving final edge by whether DPI ever examined
    its component, cross-referenced against ground truth. Pure post-hoc
    attribution using `compose_screen_then_prune`'s own unmodified output
    -- no DPI logic is re-implemented or altered here."""
    counts = {bucket: 0 for bucket in BUCKETS}
    node_to_component: dict[int, frozenset[int]] = {}
    for component in connected_components(flagged):
        for node in component:
            node_to_component[node] = component

    p = final.shape[0]
    for i in range(p):
        for j in range(i + 1, p):
            if not final[i, j]:
                continue
            component = node_to_component.get(i)
            is_conditioned = bool(component is not None and shapes[component]["is_validated_shape"])
            is_true_edge = bool(truth[i, j])
            key = ("dpi_conditioned" if is_conditioned else "passthrough") + (
                "_true_edge" if is_true_edge else "_false_edge"
            )
            counts[key] += 1
    return counts


def _run_cell(task: tuple[int, str, int, int, float, Stage5fConfig]) -> list[dict[str, object]]:
    dgp_index, dgp_name, sample_index, n, dpi_alpha, config = task
    dgp = _DGP_REGISTRY[dgp_name]
    sample: Callable = dgp["sample"]  # type: ignore[assignment]
    p = int(dgp["p"])
    truth = _true_adjacency(dgp["true_edges"], p)  # type: ignore[arg-type]

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _condition_seed(config.master_seed, dgp_index, sample_index, replicate)
        row: dict[str, object] = {
            "dgp": dgp_name,
            "n": n,
            "replicate": replicate,
            "seed": seed,
            "status": "ok",
            "error": "",
            **{bucket: 0 for bucket in BUCKETS},
        }
        try:
            data = sample(n, config.strength, np.random.default_rng(seed))
            evidence = compute_pairwise_screening_evidence(data)
            flagged = screen_uncorrected(evidence, config.screening_alpha)
            final, shapes = compose_screen_then_prune(data, flagged, dpi_alpha)
            counts = _attribute_final_edges(flagged, final, shapes, truth)
            row.update(counts)
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


def _resolved_config(config: Stage5fConfig, alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "screening_alpha": config.screening_alpha,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "d012_alpha_by_n": alpha_by_n,
    }


def _write_evidence(
    config: Stage5fConfig, output_dir: Path, raw: pd.DataFrame, alpha_by_n: dict[int, float], runtime_seconds: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage5f_charter.md"
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


def run_stage5f(config: Stage5fConfig, output_dir: Path, max_workers: int | None = None) -> pd.DataFrame:
    import os
    from concurrent.futures import ProcessPoolExecutor

    run_started = time.perf_counter()
    selected = select_form(fit_candidate_forms())
    alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    tasks = [
        (dgp_index, dgp_name, sample_index, n, alpha_by_n[n], config)
        for dgp_index, dgp_name in enumerate(DGPS)
        for sample_index, n in enumerate(config.sample_sizes)
    ]

    if max_workers is None:
        max_workers = min(len(tasks), max(1, (os.cpu_count() or 1) - 1))

    rows: list[dict[str, object]] = []
    if max_workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for cell_rows in executor.map(_run_cell, tasks):
                rows.extend(cell_rows)
    else:
        for task in tasks:
            rows.extend(_run_cell(task))

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, alpha_by_n, time.perf_counter() - run_started)

    from mintnet.experiments.stage5f_reporting import write_stage5f_report

    write_stage5f_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    arguments = parser.parse_args()
    run_stage5f(load_stage5f_config(arguments.config), arguments.output, max_workers=arguments.workers)


if __name__ == "__main__":
    main()
