"""Deterministic raw-evidence runner for the frozen Stage 6b
conditional-MI estimator validation. See docs/stage6b_charter.md.

Implementation-time scope correction, disclosed transparently, per the
charter's own explicit contingency ("extending to this project's usual
2,000 is deferred pending this charter's own runtime finding, not
assumed affordable"): a single local-permutation significance test
costs ~1.2s at N=300 and ~21s at N=1500 (199 permutations), dominated
by per-permutation nearest-neighbor query overhead, not tree
construction (measured directly before committing to a grid). The
charter's own full grid (N up to 1500, 500 replicates, B=199) would
take many hours to tens of hours for this first pass alone. This
runner uses a reduced first-pass grid instead -- `N = [300, 500, 750]`
(dropping `1500`), `replicates = 100` (development 0-49, validation
50-99), `permutations = 99` -- explicitly a scope reduction from the
charter's own stated grid, not a silent substitution: if this first
pass PROCEEDs, extending to the full grid (larger N, more replicates,
more permutations) is a natural, cheap follow-up once the mechanism's
basic validity is confirmed at this smaller, affordable scale.
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

from mintnet.mi.cmiknn import local_permutation_test
from mintnet.simulation.motifs import sample_hub, sample_measured_fork, sample_overlapping_triangles

_STAGE_TAG = 602

# Each condition: (label, |S|, sampler, (x_col, y_col, z_cols), kind)
# kind in {"null", "alt"} -- null: known-independent pair given Z;
# alt: known-direct-edge pair given Z. Reuses only already-validated
# DGP fixtures (mintnet.simulation.motifs), per the charter's own
# "Data-generating processes" section.


def _sample_bivariate_independent(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.normal(size=(n, 2))


def _sample_bivariate_correlated(n: int, rng: np.random.Generator, r: float = 0.6) -> np.ndarray:
    x = rng.normal(size=n)
    y = r * x + np.sqrt(1.0 - r**2) * rng.normal(size=n)
    return np.column_stack([x, y])


def _sample_fork(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_measured_fork(n, 0.6, rng)


def _sample_hub3(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_hub(n, 0.6, 3, rng)


def _sample_overlap(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_overlapping_triangles(n, rng)


CONDITIONS: tuple[dict[str, object], ...] = (
    {"label": "s0_null", "s": 0, "sample": _sample_bivariate_independent, "x": 0, "y": 1, "z": ()},
    {"label": "s0_alt", "s": 0, "sample": _sample_bivariate_correlated, "x": 0, "y": 1, "z": ()},
    # fork columns: 0=child1, 1=center, 2=child2. true edges (0,1),(1,2); indirect (0,2)
    {"label": "s1_null", "s": 1, "sample": _sample_fork, "x": 0, "y": 2, "z": (1,)},
    {"label": "s1_alt", "s": 1, "sample": _sample_fork, "x": 0, "y": 1, "z": (2,)},
    # hub columns: 0=hub, 1..3=children. true edges (0,i); indirect (i,j)
    {"label": "s2_null", "s": 2, "sample": _sample_hub3, "x": 1, "y": 2, "z": (0, 3)},
    {"label": "s2_alt", "s": 2, "sample": _sample_hub3, "x": 0, "y": 1, "z": (2, 3)},
    # overlap columns: true edges (0,1),(0,2),(1,2),(2,3),(2,4),(3,4); (0,3) is cross-triangle, no edge
    {"label": "s3_null", "s": 3, "sample": _sample_overlap, "x": 0, "y": 3, "z": (1, 2, 4)},
    {"label": "s3_alt", "s": 3, "sample": _sample_overlap, "x": 0, "y": 1, "z": (2, 3, 4)},
)


@dataclass(frozen=True)
class Stage6bConfig:
    sample_sizes: tuple[int, ...]
    replicates: int
    k: int
    k_perm: int
    permutations: int
    alphas: tuple[float, ...]
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    source_path: Path | None = None


def load_stage6b_config(path: Path) -> Stage6bConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 6b configuration must be a mapping")
    return Stage6bConfig(
        sample_sizes=tuple(int(v) for v in values["sample_sizes"]),
        replicates=int(values["replicates"]),
        k=int(values["k"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        alphas=tuple(float(v) for v in values["alphas"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, condition_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, _STAGE_TAG, condition_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage6bConfig) -> Path:
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


def _run_condition_cell(task: tuple[int, dict, int, int, Stage6bConfig]) -> list[dict[str, object]]:
    condition_index, condition, sample_index, n, config = task
    label = condition["label"]
    s = int(condition["s"])
    sample: Callable = condition["sample"]  # type: ignore[assignment]
    x_col = int(condition["x"])
    y_col = int(condition["y"])
    z_cols = condition["z"]  # type: ignore[assignment]

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _condition_seed(config.master_seed, condition_index, sample_index, replicate)
        rng = np.random.default_rng(seed)
        row: dict[str, object] = {
            "label": label, "s": s, "n": n, "replicate": replicate, "seed": seed,
            "status": "ok", "error": "", "estimate": np.nan, "p_value": np.nan,
        }
        try:
            data = sample(n, rng)
            x = data[:, x_col]
            y = data[:, y_col]
            z = data[:, list(z_cols)] if z_cols else None
            result = local_permutation_test(
                x, y, z, k=config.k, k_perm=config.k_perm, permutations=config.permutations, rng=rng
            )
            row["estimate"] = result.statistic
            row["p_value"] = result.p_value
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


def _resolved_config(config: Stage6bConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "k": config.k,
        "k_perm": config.k_perm,
        "permutations": config.permutations,
        "alphas": list(config.alphas),
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "note": (
            "Reduced first-pass grid (N<=750, replicates=100 by default config), a disclosed scope "
            "reduction from the frozen charter's own full grid (N up to 1500, 500 replicates) -- see "
            "stage6b.py's own module docstring for the measured timing that motivated it."
        ),
    }


def _write_evidence(config: Stage6bConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage6b_charter.md"
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


def run_stage6b(config: Stage6bConfig, output_dir: Path, max_workers: int | None = None) -> pd.DataFrame:
    import os
    from concurrent.futures import ProcessPoolExecutor

    run_started = time.perf_counter()
    tasks = [
        (condition_index, condition, sample_index, n, config)
        for condition_index, condition in enumerate(CONDITIONS)
        for sample_index, n in enumerate(config.sample_sizes)
    ]
    if max_workers is None:
        max_workers = min(len(tasks), max(1, (os.cpu_count() or 1) - 1))

    rows: list[dict[str, object]] = []
    if max_workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            for cell_rows in executor.map(_run_condition_cell, tasks):
                rows.extend(cell_rows)
    else:
        for task in tasks:
            rows.extend(_run_condition_cell(task))

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)

    from mintnet.experiments.stage6b_reporting import write_stage6b_report

    write_stage6b_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    arguments = parser.parse_args()
    run_stage6b(load_stage6b_config(arguments.config), arguments.output, max_workers=arguments.workers)


if __name__ == "__main__":
    main()
