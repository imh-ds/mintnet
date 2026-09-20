"""Deterministic raw-evidence runner for the frozen Stage 4l composed-
pipeline-with-noise experiment for chain/fork/hub (sequential engine,
p=15). See docs/stage4l_charter.md.

A new p=15 composed network -- deliberately not Stage 2d's own (which
uses chain, fork, and the shared-node-overlap shape, not hub) -- built
from the three structurally-symmetric motifs Stage 4k validated in
isolation (D-040), plus 6 noise columns. Reuses D-012's already-frozen
alpha(N) formula unmodified (`mintnet.experiments.stage1j_fit.
fit_candidate_forms`/`select_form`, the same formula and the same
predicted values Stage 4k already used), Stage 1's motif simulators,
and Stage 4a's sequential engine (`sequential_screen_and_prune_
detailed`) unmodified.
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
from mintnet.pipeline import sequential_screen_and_prune_detailed
from mintnet.simulation import sample_chain, sample_hub, sample_measured_fork

CHAIN_INDIRECT: tuple[tuple[int, int], ...] = ((0, 2),)
FORK_INDIRECT: tuple[tuple[int, int], ...] = ((3, 5),)
HUB_INDIRECT: tuple[tuple[int, int], ...] = ((7, 8),)
TRUE_DIRECT_EDGES: frozenset[tuple[int, int]] = frozenset(
    {(0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (6, 8)}
)
TRUE_CANDIDATE_PAIRS: frozenset[tuple[int, int]] = frozenset(
    set(combinations((0, 1, 2), 2)) | set(combinations((3, 4, 5), 2)) | set(combinations((6, 7, 8), 2))
)
NOISE_COUNT = 6
P = 9 + NOISE_COUNT


def _sample_network(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    chain = sample_chain(n, strength, rng)
    fork = sample_measured_fork(n, strength, rng)
    hub = sample_hub(n, strength, children=2, rng=rng)
    noise = rng.normal(size=(n, NOISE_COUNT))
    return np.column_stack([chain, fork, hub, noise])


def _score(screened: np.ndarray, final: np.ndarray, p: int) -> dict[str, float]:
    all_pairs = set(combinations(range(p), 2))
    null_pairs = all_pairs - TRUE_CANDIDATE_PAIRS

    def _tpr(edges: tuple[tuple[int, int], ...]) -> float:
        pruned = sum(1 for i, j in edges if not final[i, j])
        return pruned / len(edges)

    true_retained = sum(1 for i, j in TRUE_DIRECT_EDGES if final[i, j])
    screening_false = sum(1 for i, j in null_pairs if screened[i, j])
    final_false = sum(1 for i, j in null_pairs if final[i, j])

    return {
        "chain_indirect_tpr": _tpr(CHAIN_INDIRECT),
        "fork_indirect_tpr": _tpr(FORK_INDIRECT),
        "hub_indirect_tpr": _tpr(HUB_INDIRECT),
        "true_edge_prune_fpr": 1.0 - (true_retained / len(TRUE_DIRECT_EDGES)),
        "screening_false_edge_rate": screening_false / len(null_pairs),
        "final_false_edge_rate": final_false / len(null_pairs),
    }


@dataclass(frozen=True)
class Stage4lConfig:
    strengths: tuple[float, ...]
    sample_sizes: tuple[int, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_indirect_prune_tpr: float
    maximum_true_edge_prune_fpr: float
    false_edge_rate_tolerance: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4l_config(path: Path) -> Stage4lConfig:
    """Load a Stage 4l configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4l configuration must be a mapping")

    return Stage4lConfig(
        strengths=_values(values, "strengths", float),
        sample_sizes=_values(values, "sample_sizes", int),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        false_edge_rate_tolerance=float(values["false_edge_rate_tolerance"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, strength_index: int, sample_index: int, replicate: int) -> int:
    # A stream tag distinct from every prior Stage 4 charter.
    sequence = np.random.SeedSequence([master_seed, strength_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4lConfig) -> Path:
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


def _resolved_config(config: Stage4lConfig, formula_name: str, alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "strengths": list(config.strengths),
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
        "d012_formula": formula_name,
        "alpha_by_n": alpha_by_n,
    }


def _write_evidence(
    config: Stage4lConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    formula_name: str,
    alpha_by_n: dict[int, float],
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, formula_name, alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4l_charter.md"
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


_MOTIF_INDIRECT = {"chain": CHAIN_INDIRECT[0], "fork": FORK_INDIRECT[0], "hub": HUB_INDIRECT[0]}


def run_stage4l(config: Stage4lConfig, output_dir: Path, stage4k_raw_path: Path | None = None) -> pd.DataFrame:
    """Sweep the sequential engine across strength x N on the new,
    composed, noisy p=15 chain/fork/hub network, reusing D-012's already-
    frozen alpha(N) formula unmodified -- the same formula, and the same
    predicted values, Stage 4k already used in isolation."""
    run_started = time.perf_counter()

    forms = fit_candidate_forms()
    selected = select_form(forms)
    alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for strength_index, strength in enumerate(config.strengths):
        for sample_index, n in enumerate(config.sample_sizes):
            alpha = alpha_by_n[n]
            for replicate in range(config.replicates):
                seed = _condition_seed(config.master_seed, strength_index, sample_index, replicate)
                started = time.perf_counter()
                row_status, row_error = "ok", ""
                metrics: dict[str, object] = {
                    "chain_indirect_tpr": np.nan,
                    "fork_indirect_tpr": np.nan,
                    "hub_indirect_tpr": np.nan,
                    "true_edge_prune_fpr": np.nan,
                    "screening_false_edge_rate": np.nan,
                    "final_false_edge_rate": np.nan,
                }
                pair_row: dict[str, object] = {}
                for motif, (i, j) in _MOTIF_INDIRECT.items():
                    label = _pair_label(i, j)
                    pair_row[f"candidate_{label}"] = np.nan
                    pair_row[f"correctly_pruned_{label}"] = np.nan
                    pair_row[f"tested_neighbors_{label}"] = ""
                try:
                    data = _sample_network(n, strength, np.random.default_rng(seed))
                    final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                    by_pair = {(d.i, d.j): d for d in decisions}
                    screened = np.zeros((P, P), dtype=bool)
                    for d in decisions:
                        screened[d.i, d.j] = screened[d.j, d.i] = True
                    metrics = _score(screened, final, P)
                    for motif, (i, j) in _MOTIF_INDIRECT.items():
                        label = _pair_label(i, j)
                        decision = by_pair.get((i, j))
                        if decision is None:
                            pair_row[f"candidate_{label}"] = False
                            pair_row[f"correctly_pruned_{label}"] = np.nan
                            pair_row[f"tested_neighbors_{label}"] = ""
                        else:
                            pair_row[f"candidate_{label}"] = True
                            pair_row[f"correctly_pruned_{label}"] = not decision.confirmed
                            pair_row[f"tested_neighbors_{label}"] = ",".join(str(k) for k in decision.tested_neighbors)
                except Exception as exc:  # raw evidence must retain pipeline failures
                    row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

                rows.append(
                    {
                        "strength": strength,
                        "n": n,
                        "alpha": alpha,
                        "replicate": replicate,
                        "seed": seed,
                        **metrics,
                        **pair_row,
                        "elapsed_seconds": time.perf_counter() - started,
                        "status": row_status,
                        "error": row_error,
                    }
                )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, selected.name, alpha_by_n, time.perf_counter() - run_started)
    from mintnet.experiments.stage4l_reporting import write_stage4l_report

    write_stage4l_report(raw, config, output_dir, stage4k_raw_path)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stage4k-raw-evidence", required=False, type=Path, default=None)
    arguments = parser.parse_args()
    run_stage4l(load_stage4l_config(arguments.config), arguments.output, arguments.stage4k_raw_evidence)


if __name__ == "__main__":
    main()
