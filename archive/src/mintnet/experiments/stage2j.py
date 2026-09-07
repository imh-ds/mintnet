"""Deterministic raw-evidence runner for the frozen Stage 2j p=5/p=10
composed-pipeline floor-check experiment. See docs/stage2j_charter.md.

Reuses Stage 1j's DPI alpha(N) fit (`fit_candidate_forms`, `select_form`),
Stage 2d's motif samplers (`mintnet.simulation.sample_chain`,
`sample_overlapping_triangles`), and the generic screening/composition
primitives (`mintnet.screening.compute_pairwise_screening_evidence`,
`screen_uncorrected`, `mintnet.pipeline.compose_screen_then_prune`). The
DGP layouts (overlap+chain at p=10; overlap-only, zero noise, at p=5)
are new to this charter -- no prior charter fits at p<15 -- so this
module defines its own ground-truth pair sets, screening-alpha
selection, and composition scoring rather than reusing Stage2/2d/2e's
p=15/p=30 layouts.

Two phases, per the charter:
1. Screening-alpha selection at p=10 only (re-derived, since D-023 found
   the null-pair count changes which alpha is selected). p=5 has zero
   null pairs -- selection is meaningless there -- so it reuses D-013's
   original alpha=.001, fixed, not re-derived.
2. Composed-pipeline evaluation at both p=10 (selected alpha) and p=5
   (fixed alpha), at N=[750, 1500].
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
from mintnet.pipeline import compose_screen_then_prune
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import sample_chain, sample_overlapping_triangles

# p=10 layout: overlap (0-4, node 2 shared), chain (5-7), noise (8-9).
P10 = 10
OVERLAP_DIRECT_10: frozenset[tuple[int, int]] = frozenset({(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)})
OVERLAP_INDIRECT_10: tuple[tuple[int, int], ...] = ((0, 3), (0, 4), (1, 3), (1, 4))
CHAIN_DIRECT_10: frozenset[tuple[int, int]] = frozenset({(5, 6), (6, 7)})
CHAIN_INDIRECT_10: tuple[tuple[int, int], ...] = ((5, 7),)
TRUE_CANDIDATE_PAIRS_10: frozenset[tuple[int, int]] = frozenset(
    set(combinations((0, 1, 2, 3, 4), 2)) | {(5, 6), (5, 7), (6, 7)}
)
TRUE_DIRECT_EDGES_10: frozenset[tuple[int, int]] = OVERLAP_DIRECT_10 | CHAIN_DIRECT_10

# p=5 layout: overlap only (0-4, node 2 shared). Zero noise columns --
# every one of the C(5,2)=10 pairs is either a true direct or indirect
# edge, so there are no null pairs at this p (see charter's disclosed
# limitation).
P5 = 5
OVERLAP_DIRECT_5 = OVERLAP_DIRECT_10
OVERLAP_INDIRECT_5 = OVERLAP_INDIRECT_10
TRUE_CANDIDATE_PAIRS_5: frozenset[tuple[int, int]] = frozenset(set(combinations(range(5), 2)))
TRUE_DIRECT_EDGES_5 = OVERLAP_DIRECT_5

_SELECTION_STREAM = 1
_P10_STREAM = 2
_P5_STREAM = 3


def _sample_p10(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    overlap = sample_overlapping_triangles(n, rng)
    chain = sample_chain(n, strength, rng)
    noise = rng.normal(size=(n, 2))
    return np.column_stack([overlap, chain, noise])


def _sample_p5(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_overlapping_triangles(n, rng)


@dataclass(frozen=True)
class Stage2jConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha_grid: tuple[float, ...]
    fixed_alpha_p5: float
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    minimum_recall: float
    maximum_fdr: float
    minimum_indirect_tpr: float
    maximum_true_edge_fpr: float
    false_edge_rate_tolerance: float
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage2j_config(path: Path) -> Stage2jConfig:
    """Load a Stage 2j configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 2j configuration must be a mapping")

    return Stage2jConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        screening_alpha_grid=_values(values, "screening_alpha_grid", float),
        fixed_alpha_p5=float(values["fixed_alpha_p5"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_recall=float(values["minimum_recall"]),
        maximum_fdr=float(values["maximum_fdr"]),
        minimum_indirect_tpr=float(values["minimum_indirect_tpr"]),
        maximum_true_edge_fpr=float(values["maximum_true_edge_fpr"]),
        false_edge_rate_tolerance=float(values["false_edge_rate_tolerance"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, stream: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, stream, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage2jConfig) -> Path:
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


def _resolved_config(config: Stage2jConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "screening_alpha_grid": list(config.screening_alpha_grid),
        "fixed_alpha_p5": config.fixed_alpha_p5,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_recall": config.minimum_recall,
        "maximum_fdr": config.maximum_fdr,
        "minimum_indirect_tpr": config.minimum_indirect_tpr,
        "maximum_true_edge_fpr": config.maximum_true_edge_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
    }


def _write_evidence(
    config: Stage2jConfig,
    output_dir: Path,
    selection_raw: pd.DataFrame,
    composition_raw: pd.DataFrame,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    selection_raw.to_csv(output_dir / "screening_selection_metrics.csv", index=False)
    composition_raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage2j_charter.md"
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


def _score_screening(flagged: np.ndarray, p: int, true_pairs: frozenset[tuple[int, int]]) -> dict[str, float]:
    all_pairs = set(combinations(range(p), 2))
    null_pairs = all_pairs - true_pairs
    true_positives = sum(1 for i, j in true_pairs if flagged[i, j])
    false_positives = sum(1 for i, j in null_pairs if flagged[i, j])
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "total_flagged": true_positives + false_positives,
        "true_pair_count": len(true_pairs),
        "null_pair_count": len(null_pairs),
    }


def _tpr(final: np.ndarray, edges: tuple[tuple[int, int], ...]) -> float:
    pruned = sum(1 for i, j in edges if not final[i, j])
    return pruned / len(edges)


def _score_composition(
    screened: np.ndarray,
    final: np.ndarray,
    p: int,
    true_candidate_pairs: frozenset[tuple[int, int]],
    true_direct_edges: frozenset[tuple[int, int]],
    chain_indirect: tuple[tuple[int, int], ...] | None,
    overlap_indirect: tuple[tuple[int, int], ...],
) -> dict[str, float]:
    all_pairs = set(combinations(range(p), 2))
    null_pairs = all_pairs - true_candidate_pairs

    true_retained = sum(1 for i, j in true_direct_edges if final[i, j])
    true_edge_fpr = 1.0 - (true_retained / len(true_direct_edges))

    if null_pairs:
        screening_false = sum(1 for i, j in null_pairs if screened[i, j])
        final_false = sum(1 for i, j in null_pairs if final[i, j])
        screening_rate = screening_false / len(null_pairs)
        final_rate = final_false / len(null_pairs)
    else:
        screening_rate = float("nan")
        final_rate = float("nan")

    return {
        "chain_indirect_tpr": _tpr(final, chain_indirect) if chain_indirect else float("nan"),
        "overlap_indirect_tpr": _tpr(final, overlap_indirect),
        "true_edge_prune_fpr": true_edge_fpr,
        "screening_false_edge_rate": screening_rate,
        "final_false_edge_rate": final_rate,
    }


def _run_selection_phase(config: Stage2jConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, _SELECTION_STREAM, sample_index, replicate)
            started = time.perf_counter()
            try:
                data = _sample_p10(n, config.strength, np.random.default_rng(seed))
                evidence = compute_pairwise_screening_evidence(data)
                status, error = "ok", ""
            except Exception as exc:  # raw evidence must retain pipeline failures
                evidence = None
                status, error = "error", f"{type(exc).__name__}: {exc}"

            for alpha in config.screening_alpha_grid:
                row_status, row_error = status, error
                metrics: dict[str, float] = {
                    "true_positives": np.nan,
                    "false_positives": np.nan,
                    "total_flagged": np.nan,
                    "true_pair_count": np.nan,
                    "null_pair_count": np.nan,
                }
                if evidence is not None:
                    try:
                        flagged = screen_uncorrected(evidence, alpha)
                        metrics = _score_screening(flagged, P10, TRUE_CANDIDATE_PAIRS_10)
                    except Exception as exc:  # retain scoring failures by alpha
                        row_status = "error"
                        row_error = f"{type(exc).__name__}: {exc}"
                rows.append(
                    {
                        "n": n,
                        "replicate": replicate,
                        "seed": seed,
                        "alpha": alpha,
                        **metrics,
                        "elapsed_seconds": time.perf_counter() - started,
                        "status": row_status,
                        "error": row_error,
                    }
                )
    return pd.DataFrame(rows)


def _run_composition_phase(
    config: Stage2jConfig, selected_alpha_by_n: dict[int, float | None], selected_form
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        dpi_alpha = selected_form.predict(float(n))
        alpha_p10 = selected_alpha_by_n.get(n)

        for replicate in range(config.replicates):
            for p, stream, screening_alpha, sampler in (
                (P10, _P10_STREAM, alpha_p10, lambda rng: _sample_p10(n, config.strength, rng)),
                (P5, _P5_STREAM, config.fixed_alpha_p5, lambda rng: _sample_p5(n, rng)),
            ):
                seed = _condition_seed(config.master_seed, stream, sample_index, replicate)
                started = time.perf_counter()
                row_status, row_error = "ok", ""
                metrics: dict[str, float] = {
                    "chain_indirect_tpr": np.nan,
                    "overlap_indirect_tpr": np.nan,
                    "true_edge_prune_fpr": np.nan,
                    "screening_false_edge_rate": np.nan,
                    "final_false_edge_rate": np.nan,
                }
                overlap_clean_clique = np.nan
                if screening_alpha is None:
                    row_status, row_error = "error", "no eligible development alpha"
                else:
                    try:
                        data = sampler(np.random.default_rng(seed))
                        evidence = compute_pairwise_screening_evidence(data)
                        screened = screen_uncorrected(evidence, screening_alpha)
                        final, _shapes = compose_screen_then_prune(data, screened, dpi_alpha)
                        if p == P10:
                            metrics = _score_composition(
                                screened, final, p, TRUE_CANDIDATE_PAIRS_10, TRUE_DIRECT_EDGES_10,
                                CHAIN_INDIRECT_10, OVERLAP_INDIRECT_10,
                            )
                            overlap_pairs = OVERLAP_INDIRECT_10
                        else:
                            metrics = _score_composition(
                                screened, final, p, TRUE_CANDIDATE_PAIRS_5, TRUE_DIRECT_EDGES_5,
                                None, OVERLAP_INDIRECT_5,
                            )
                            overlap_pairs = OVERLAP_INDIRECT_5
                        overlap_clean_clique = float(all(screened[i, j] for i, j in overlap_pairs))
                    except Exception as exc:  # raw evidence must retain pipeline failures
                        row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

                rows.append(
                    {
                        "p": p,
                        "n": n,
                        "replicate": replicate,
                        "seed": seed,
                        "screening_alpha": screening_alpha,
                        "dpi_alpha": dpi_alpha,
                        **metrics,
                        "overlap_clean_clique": overlap_clean_clique,
                        "elapsed_seconds": time.perf_counter() - started,
                        "status": row_status,
                        "error": row_error,
                    }
                )
    return pd.DataFrame(rows)


def run_stage2j(config: Stage2jConfig, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run configured Stage 2j conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    selected_form = select_form(fit_candidate_forms())

    selection_raw = _run_selection_phase(config)

    from mintnet.experiments.stage2j_reporting import select_alpha_p10

    selected_alpha_by_n = {n: select_alpha_p10(selection_raw, n, config) for n in config.sample_sizes}

    composition_raw = _run_composition_phase(config, selected_alpha_by_n, selected_form)

    _write_evidence(config, output_dir, selection_raw, composition_raw, time.perf_counter() - run_started)

    from mintnet.experiments.stage2j_reporting import write_stage2j_report

    write_stage2j_report(selection_raw, composition_raw, config, output_dir)
    return selection_raw, composition_raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage2j(load_stage2j_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
