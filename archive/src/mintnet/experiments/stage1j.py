"""Deterministic raw-evidence runner for the frozen Stage 1j held-out validation.

Tests exactly one alpha per sample size -- the value predicted by the
formula selected in mintnet.experiments.stage1j_fit -- rather than
searching a grid. This mirrors how a production method would actually use
an alpha(N) rule: compute one value from N, no search.
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

from mintnet.dpi import compute_conditional_independence_evidence, prune_conditional_independence
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.metrics import score_motif
from mintnet.simulation import sample_chain, sample_measured_fork, sample_precision_triangle


@dataclass(frozen=True)
class Stage1jConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    triangle_families: tuple[str, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_triangle_true_edge_prune_fpr: float
    required_margin: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float] | type[str]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage1j_config(path: Path) -> Stage1jConfig:
    """Load a Stage 1j configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 1j configuration must be a mapping")

    config = Stage1jConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        triangle_families=_values(values, "triangle_families", str),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_triangle_true_edge_prune_fpr=float(values["maximum_triangle_true_edge_prune_fpr"]),
        required_margin=float(values["required_margin"]),
        source_path=path.resolve(),
    )
    if len(config.strengths) != len(config.triangle_families):
        raise ValueError("strengths and triangle_families must have equal length")
    return config


def _condition_seed(
    config: Stage1jConfig,
    motif_index: int,
    sample_index: int,
    strength_index: int,
    replicate: int,
) -> int:
    sequence = np.random.SeedSequence(
        [config.master_seed, motif_index, sample_index, strength_index, replicate]
    )
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage1jConfig) -> Path:
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


def _resolved_config(config: Stage1jConfig, selected_form_name: str, selected_alphas: dict[int, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strengths": list(config.strengths),
        "triangle_families": list(config.triangle_families),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_triangle_true_edge_prune_fpr": config.maximum_triangle_true_edge_prune_fpr,
        "required_margin": config.required_margin,
        "selected_form": selected_form_name,
        "predicted_alpha_by_n": selected_alphas,
    }


def _write_evidence(
    config: Stage1jConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    selected_form_name: str,
    selected_alphas: dict[int, float],
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, selected_form_name, selected_alphas), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage1j_charter.md"
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


def _sample_motif(
    motif: str, family: str, n: int, strength: float, rng: np.random.Generator
) -> np.ndarray:
    if motif == "chain":
        return sample_chain(n, strength, rng)
    if motif == "fork":
        return sample_measured_fork(n, strength, rng)
    return sample_precision_triangle(family, n, rng)


def run_stage1j(config: Stage1jConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 1j conditions and persist only raw evidence."""
    run_started = time.perf_counter()

    forms = fit_candidate_forms()
    selected = select_form(forms)
    predicted_alphas = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for motif_index, motif in enumerate(("chain", "fork", "triangle")):
        for sample_index, n in enumerate(config.sample_sizes):
            alpha = predicted_alphas[n]
            for strength_index, strength in enumerate(config.strengths):
                family = "gaussian" if motif != "triangle" else config.triangle_families[strength_index]
                for replicate in range(config.replicates):
                    seed = _condition_seed(
                        config, motif_index, sample_index, strength_index, replicate
                    )
                    started = time.perf_counter()
                    metrics = {
                        "indirect_prune_tpr": np.nan,
                        "true_edge_prune_fpr": np.nan,
                        "perfect_recovery": np.nan,
                    }
                    retained_01 = retained_02 = retained_12 = np.nan
                    partial_01 = partial_02 = partial_12 = np.nan
                    p_value_01 = p_value_02 = p_value_12 = np.nan
                    row_status, row_error = "ok", ""
                    try:
                        data = _sample_motif(
                            motif, family, n, strength, np.random.default_rng(seed)
                        )
                        evidence = compute_conditional_independence_evidence(data)
                        adjacency = prune_conditional_independence(data, alpha)
                        metrics = score_motif(adjacency, motif)
                        retained_01 = bool(adjacency[0, 1])
                        retained_02 = bool(adjacency[0, 2])
                        retained_12 = bool(adjacency[1, 2])
                        partial_01 = float(evidence.partial_correlation[0, 1])
                        partial_02 = float(evidence.partial_correlation[0, 2])
                        partial_12 = float(evidence.partial_correlation[1, 2])
                        p_value_01 = float(evidence.p_value[0, 1])
                        p_value_02 = float(evidence.p_value[0, 2])
                        p_value_12 = float(evidence.p_value[1, 2])
                    except Exception as exc:  # raw evidence must retain pipeline failures
                        row_status, row_error = "error", f"{type(exc).__name__}: {exc}"
                    rows.append(
                        {
                            "motif": motif,
                            "family": family,
                            "strength": strength,
                            "n": n,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": seed,
                            "retained_01": retained_01,
                            "retained_02": retained_02,
                            "retained_12": retained_12,
                            "partial_r_01": partial_01,
                            "partial_r_02": partial_02,
                            "partial_r_12": partial_12,
                            "p_value_01": p_value_01,
                            "p_value_02": p_value_02,
                            "p_value_12": p_value_12,
                            "confidence_01": (1.0 - p_value_01) if row_status == "ok" else np.nan,
                            "confidence_02": (1.0 - p_value_02) if row_status == "ok" else np.nan,
                            "confidence_12": (1.0 - p_value_12) if row_status == "ok" else np.nan,
                            **metrics,
                            "elapsed_seconds": time.perf_counter() - started,
                            "status": row_status,
                            "error": row_error,
                        }
                    )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, selected.name, predicted_alphas, time.perf_counter() - run_started)
    # Keep the raw-evidence runner independent at import time while ensuring
    # every CLI invocation leaves the aggregate R2j gate evidence alongside it.
    from mintnet.experiments.stage1j_reporting import write_stage1j_report

    write_stage1j_report(raw, config, selected, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage1j(load_stage1j_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
