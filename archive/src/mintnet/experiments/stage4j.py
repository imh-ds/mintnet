"""Deterministic raw-evidence runner for the frozen Stage 4j densely-
spaced alpha(N) refit experiment (sequential engine, overlap shape).
See docs/stage4j_charter.md.

Two simulation phases, per the charter:

1. `run_dense_fitting_simulation` -- a Stage 4e-shaped sweep (full alpha
   grid, `mintnet.experiments.stage1l`'s overlap DGP) restricted to four
   new, densely-spaced N inside the N=700-750 gap
   (`mintnet.experiments.stage4j_fit.DENSE_SAMPLE_SIZES`), needed
   because Stage 4e never simulated at these N.
2. `run_stage4j` -- fits the ten-point formula (six points reused
   verbatim from Stage 4e, four from phase 1), self-checks it, then
   freshly simulates and validates the nine held-out N per
   `mintnet.experiments.stage4j_fit.compute_fitting_points`.

Reuses Stage 1L's overlap DGP/ground truth, Stage 4b/d/e/f/g/i's exact
seed derivation, and Stage 4a's sequential engine
(`sequential_screen_and_prune_detailed`) unmodified.
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

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage1l import INDIRECT_EDGES as OVERLAP_INDIRECT_EDGES
from mintnet.experiments.stage1l import TRUE_EDGES as OVERLAP_TRUE_EDGES
from mintnet.experiments.stage4b import SHAPES
from mintnet.experiments.stage4g_fit import FITTING_ALPHAS
from mintnet.experiments.stage4j_fit import (
    DENSE_SAMPLE_SIZES,
    compute_fitting_points,
    fitting_point_self_check,
)
from mintnet.pipeline import sequential_screen_and_prune_detailed
from mintnet.simulation import sample_overlapping_triangles

_OVERLAP_SHAPE_INDEX = SHAPES.index("overlap")


@dataclass(frozen=True)
class Stage4jConfig:
    sample_sizes: tuple[int, ...]
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


def load_stage4j_config(path: Path) -> Stage4jConfig:
    """Load a Stage 4j configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4j configuration must be a mapping")

    return Stage4jConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_conditional_accuracy=float(values["minimum_conditional_accuracy"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        required_margin=float(values["required_margin"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, sample_index: int, replicate: int) -> int:
    # Matches Stage 4b/4d/4e/4f/4g/4i's exact seed derivation for overlap's
    # shape index. Position-based, not N-based: reusing a position that a
    # prior charter also used, at the same N, bit-for-bit reproduces that
    # charter's own draws -- an established, deliberate property, not a
    # collision, since the underlying sample size still differs whenever
    # the N being tested at that position differs.
    sequence = np.random.SeedSequence([master_seed, _OVERLAP_SHAPE_INDEX, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4jConfig) -> Path:
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


def _pair_label(i: int, j: int) -> str:
    return f"{i}{j}"


def _simulate_one_cell(n: int, alpha: float, seed: int) -> dict[str, object]:
    """Sample overlap data at N under the given seed, screen-and-prune at
    alpha, and return the per-cross-branch-pair candidacy/correctness
    columns plus true-edge FPR. Shared by both simulation phases below."""
    row: dict[str, object] = {}
    true_edge_fpr = np.nan
    for i, j in OVERLAP_INDIRECT_EDGES:
        row[f"candidate_{_pair_label(i, j)}"] = np.nan
        row[f"correctly_pruned_{_pair_label(i, j)}"] = np.nan
    data = sample_overlapping_triangles(n, np.random.default_rng(seed))
    final, decisions = sequential_screen_and_prune_detailed(data, alpha)
    by_pair = {(d.i, d.j): d for d in decisions}
    true_retained = sum(1 for i, j in OVERLAP_TRUE_EDGES if final[i, j])
    true_edge_fpr = 1.0 - (true_retained / len(OVERLAP_TRUE_EDGES))
    for i, j in OVERLAP_INDIRECT_EDGES:
        decision = by_pair.get((i, j))
        label = _pair_label(i, j)
        if decision is None:
            row[f"candidate_{label}"] = False
            row[f"correctly_pruned_{label}"] = np.nan
        else:
            row[f"candidate_{label}"] = True
            row[f"correctly_pruned_{label}"] = not decision.confirmed
    row["true_edge_prune_fpr"] = true_edge_fpr
    return row


def run_dense_fitting_simulation(config: Stage4jConfig, output_dir: Path) -> pd.DataFrame:
    """Stage 4e-shaped full-alpha-grid sweep restricted to the four new,
    densely-spaced N inside [700, 750] -- Stage 4e never simulated at
    these N, so this data must be generated fresh before any fitting."""
    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(DENSE_SAMPLE_SIZES):
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, sample_index, replicate)
            started = time.perf_counter()
            try:
                data = sample_overlapping_triangles(n, np.random.default_rng(seed))
                status, error = "ok", ""
            except Exception as exc:  # raw evidence must retain pipeline failures
                data = None
                status, error = "error", f"{type(exc).__name__}: {exc}"

            for alpha in FITTING_ALPHAS:
                row: dict[str, object] = {}
                row_status, row_error = status, error
                true_edge_fpr = np.nan
                for i, j in OVERLAP_INDIRECT_EDGES:
                    row[f"candidate_{_pair_label(i, j)}"] = np.nan
                    row[f"correctly_pruned_{_pair_label(i, j)}"] = np.nan
                if data is not None:
                    try:
                        final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                        by_pair = {(d.i, d.j): d for d in decisions}
                        true_retained = sum(1 for i, j in OVERLAP_TRUE_EDGES if final[i, j])
                        true_edge_fpr = 1.0 - (true_retained / len(OVERLAP_TRUE_EDGES))
                        for i, j in OVERLAP_INDIRECT_EDGES:
                            decision = by_pair.get((i, j))
                            label = _pair_label(i, j)
                            if decision is None:
                                row[f"candidate_{label}"] = False
                                row[f"correctly_pruned_{label}"] = np.nan
                            else:
                                row[f"candidate_{label}"] = True
                                row[f"correctly_pruned_{label}"] = not decision.confirmed
                    except Exception as exc:  # retain pruning/scoring failures by alpha
                        row_status = "error"
                        row_error = f"{type(exc).__name__}: {exc}"

                rows.append(
                    {
                        "n": n,
                        "alpha": alpha,
                        "replicate": replicate,
                        "seed": seed,
                        **row,
                        "true_edge_prune_fpr": true_edge_fpr,
                        "elapsed_seconds": time.perf_counter() - started,
                        "status": row_status,
                        "error": row_error,
                    }
                )
    dense_raw = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    dense_raw.to_csv(output_dir / "dense_fitting_raw.csv", index=False)
    return dense_raw


def _resolved_config(
    config: Stage4jConfig, selected_form_name: str, predicted_alpha_by_n: dict[int, float]
) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_conditional_accuracy": config.minimum_conditional_accuracy,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "required_margin": config.required_margin,
        "selected_form": selected_form_name,
        "predicted_alpha_by_n": predicted_alpha_by_n,
    }


def _write_evidence(
    config: Stage4jConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    fitting_points: tuple[tuple[float, float], ...],
    self_check: tuple[dict[str, object], ...],
    selected_form_name: str,
    predicted_alpha_by_n: dict[int, float],
    stage4e_raw_path: Path,
    dense_raw_path: Path,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, selected_form_name, predicted_alpha_by_n), stream, sort_keys=True)
    (output_dir / "fitting_points.json").write_text(
        json.dumps(
            {
                "points": [{"n": n, "alpha_star": a} for n, a in fitting_points],
                "fitting_point_self_check": list(self_check),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4j_charter.md"
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    metadata = {
        "charter_sha256": charter_hash,
        "stage4e_raw_evidence_path": str(stage4e_raw_path),
        "stage4e_raw_evidence_sha256": hashlib.sha256(stage4e_raw_path.read_bytes()).hexdigest(),
        "dense_fitting_raw_evidence_sha256": hashlib.sha256(dense_raw_path.read_bytes()).hexdigest(),
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def run_stage4j(config: Stage4jConfig, stage4e_raw_path: Path, output_dir: Path) -> pd.DataFrame:
    """Simulate the four dense fitting N, fit the ten-point formula,
    self-check it, then freshly simulate and validate the nine held-out N."""
    run_started = time.perf_counter()

    dense_raw = run_dense_fitting_simulation(config, output_dir)
    dense_raw_path = output_dir / "dense_fitting_raw.csv"

    fitting_points = compute_fitting_points(stage4e_raw_path, dense_raw_path)
    forms = fit_candidate_forms(fitting_points)
    selected = select_form(forms)
    self_check = fitting_point_self_check(selected, fitting_points)
    predicted_alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        alpha = predicted_alpha_by_n[n]
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, sample_index, replicate)
            started = time.perf_counter()
            row_status, row_error = "ok", ""
            cell: dict[str, object] = {}
            try:
                if not (0.0 < alpha < 1.0):
                    raise ValueError(f"predicted alpha {alpha!r} is not a valid probability")
                cell = _simulate_one_cell(n, alpha, seed)
            except Exception as exc:  # raw evidence must retain pipeline/formula failures
                row_status, row_error = "error", f"{type(exc).__name__}: {exc}"
                cell = {"true_edge_prune_fpr": np.nan}
                for i, j in OVERLAP_INDIRECT_EDGES:
                    cell[f"candidate_{_pair_label(i, j)}"] = np.nan
                    cell[f"correctly_pruned_{_pair_label(i, j)}"] = np.nan

            rows.append(
                {
                    "n": n,
                    "alpha": alpha,
                    "replicate": replicate,
                    "seed": seed,
                    **cell,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    raw = pd.DataFrame(rows)
    _write_evidence(
        config, output_dir, raw, fitting_points, self_check, selected.name, predicted_alpha_by_n,
        stage4e_raw_path, dense_raw_path, time.perf_counter() - run_started,
    )
    from mintnet.experiments.stage4j_reporting import write_stage4j_report

    write_stage4j_report(raw, config, fitting_points, self_check, selected, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stage4e-raw-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4j(load_stage4j_config(arguments.config), arguments.stage4e_raw_evidence, arguments.output)


if __name__ == "__main__":
    main()
