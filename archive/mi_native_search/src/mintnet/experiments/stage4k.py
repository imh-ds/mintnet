"""Deterministic raw-evidence runner for the frozen Stage 4k shape/
signal-strength sweep (sequential engine). See docs/stage4k_charter.md.

Reuses D-012's already-frozen alpha(N) formula unmodified
(`mintnet.experiments.stage1j_fit.fit_candidate_forms`/`select_form`,
re-derived deterministically from its own frozen six-point fitting
data, never re-fit), Stage 1's motif simulators
(`mintnet.simulation.sample_chain`/`sample_measured_fork`/`sample_hub`),
and Stage 4a's sequential engine
(`sequential_screen_and_prune_detailed`) unmodified. Only the runner
and reporting -- a per-motif candidacy/conditional-accuracy sweep
across a strength grid, deliberately reusing the existing formula
rather than fitting a new one -- are new.
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
from mintnet.pipeline import sequential_screen_and_prune_detailed
from mintnet.simulation import sample_chain, sample_hub, sample_measured_fork

MOTIFS: tuple[str, ...] = ("chain", "fork", "hub")


def _sample_chain(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_chain(n, strength, rng)


def _sample_fork(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_measured_fork(n, strength, rng)


def _sample_hub2(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    return sample_hub(n, strength, children=2, rng=rng)


_SAMPLERS = {"chain": _sample_chain, "fork": _sample_fork, "hub": _sample_hub2}

# Deliberately structurally symmetric across all three motifs: two direct
# edges, one weak indirect (marginal, shared-cause-induced) pair.
_DIRECT_EDGES = {
    "chain": ((0, 1), (1, 2)),
    "fork": ((0, 1), (1, 2)),
    "hub": ((0, 1), (0, 2)),
}
_INDIRECT_PAIR = {
    "chain": (0, 2),
    "fork": (0, 2),
    "hub": (1, 2),
}


@dataclass(frozen=True)
class Stage4kConfig:
    strengths: tuple[float, ...]
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


def load_stage4k_config(path: Path) -> Stage4kConfig:
    """Load a Stage 4k configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4k configuration must be a mapping")

    return Stage4kConfig(
        strengths=_values(values, "strengths", float),
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


def _condition_seed(master_seed: int, motif_index: int, strength_index: int, sample_index: int, replicate: int) -> int:
    # A stream tag distinct from every prior Stage 4 charter (motif and
    # strength indices added to the usual master_seed/sample_index/
    # replicate tuple).
    sequence = np.random.SeedSequence([master_seed, motif_index, strength_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4kConfig) -> Path:
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


def _resolved_config(config: Stage4kConfig, formula_name: str, alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "strengths": list(config.strengths),
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_conditional_accuracy": config.minimum_conditional_accuracy,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "required_margin": config.required_margin,
        "d012_formula": formula_name,
        "alpha_by_n": alpha_by_n,
    }


def _write_evidence(
    config: Stage4kConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    formula_name: str,
    formula_parameters: tuple[float, ...],
    alpha_by_n: dict[int, float],
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, formula_name, alpha_by_n), stream, sort_keys=True)
    (output_dir / "d012_formula.json").write_text(
        json.dumps(
            {"name": formula_name, "parameters": list(formula_parameters), "alpha_by_n": alpha_by_n}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4k_charter.md"
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


def run_stage4k(config: Stage4kConfig, output_dir: Path) -> pd.DataFrame:
    """Sweep the sequential engine across motif x strength x N, reusing
    D-012's already-frozen alpha(N) formula unmodified at every cell."""
    run_started = time.perf_counter()

    forms = fit_candidate_forms()
    selected = select_form(forms)
    alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for motif_index, motif in enumerate(MOTIFS):
        sampler = _SAMPLERS[motif]
        direct_edges = _DIRECT_EDGES[motif]
        indirect_i, indirect_j = _INDIRECT_PAIR[motif]
        for strength_index, strength in enumerate(config.strengths):
            for sample_index, n in enumerate(config.sample_sizes):
                alpha = alpha_by_n[n]
                for replicate in range(config.replicates):
                    seed = _condition_seed(config.master_seed, motif_index, strength_index, sample_index, replicate)
                    started = time.perf_counter()
                    row_status, row_error = "ok", ""
                    candidate = np.nan
                    correctly_pruned = np.nan
                    true_edge_fpr = np.nan
                    try:
                        data = sampler(n, strength, np.random.default_rng(seed))
                        final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                        by_pair = {(d.i, d.j): d for d in decisions}
                        true_retained = sum(1 for i, j in direct_edges if final[i, j])
                        true_edge_fpr = 1.0 - (true_retained / len(direct_edges))
                        decision = by_pair.get((indirect_i, indirect_j))
                        if decision is None:
                            candidate = False
                            correctly_pruned = np.nan
                        else:
                            candidate = True
                            correctly_pruned = not decision.confirmed
                    except Exception as exc:  # raw evidence must retain pipeline failures
                        row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

                    rows.append(
                        {
                            "motif": motif,
                            "n": n,
                            "strength": strength,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": seed,
                            "candidate": candidate,
                            "correctly_pruned": correctly_pruned,
                            "true_edge_prune_fpr": true_edge_fpr,
                            "elapsed_seconds": time.perf_counter() - started,
                            "status": row_status,
                            "error": row_error,
                        }
                    )
    raw = pd.DataFrame(rows)
    _write_evidence(
        config, output_dir, raw, selected.name, selected.parameters, alpha_by_n, time.perf_counter() - run_started
    )
    from mintnet.experiments.stage4k_reporting import write_stage4k_report

    write_stage4k_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4k(load_stage4k_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
