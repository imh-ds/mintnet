"""Deterministic raw-evidence runner for the frozen Stage 3 bootstrap-
reproducibility experiment. See docs/stage3_charter.md.

Two data-generating processes:

- **primary (gated)**: Stage 2b's disjoint chain/fork/triangle network
  (`mintnet.simulation.sample_screening_network`), already PROCEED at
  both `N` (D-014) -- this charter tests whether bootstrap-resampled
  edge stability separates true from false edges on top of that
  already-validated point estimate.
- **secondary (diagnostic only, not gated)**: Stage 2d's shared-node-
  overlap network at `N=750`, the specific condition D-018 found
  REASSESS on (overlap indirect-edge pruning TPR `~.59`) -- used only to
  answer the outline's Section 17.5 key failure test: does bootstrap
  stability stay high for edges the pipeline is already known to prune
  incorrectly?

Raw evidence is long-format: one row per (dgp, n, replicate, pair) with
`status="ok"`, or one row per (dgp, n, replicate) with `status="error"`
and no pair (a whole-replicate failure -- data sampling or the point
estimate itself raising -- is recorded once, not duplicated across all
105 pairs).
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

from mintnet.bootstrap import compute_edge_stability
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.experiments.stage2b import INDIRECT_EDGES as PRIMARY_INDIRECT_EDGES
from mintnet.experiments.stage2b import TRUE_DIRECT_EDGES as PRIMARY_TRUE_DIRECT_EDGES
from mintnet.experiments.stage2d import CHAIN_INDIRECT as SECONDARY_CHAIN_INDIRECT
from mintnet.experiments.stage2d import FORK_INDIRECT as SECONDARY_FORK_INDIRECT
from mintnet.experiments.stage2d import NOISE_COUNT as SECONDARY_NOISE_COUNT
from mintnet.experiments.stage2d import OVERLAP_INDIRECT as SECONDARY_OVERLAP_INDIRECT
from mintnet.experiments.stage2d import P as SECONDARY_P
from mintnet.experiments.stage2d import TRUE_DIRECT_EDGES as SECONDARY_TRUE_DIRECT_EDGES
from mintnet.pipeline import compose_screen_then_prune
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import (
    sample_chain,
    sample_measured_fork,
    sample_overlapping_triangles,
    sample_screening_network,
)

PRIMARY_P = 15


def _sample_secondary_network(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    """Stage 2d's DGP: chain (0-2), measured fork (3-5), shared-node overlap
    (6-10, node 8 shared), and noise (11-14). See docs/stage2d_charter.md."""
    chain = sample_chain(n, strength, rng)
    fork = sample_measured_fork(n, strength, rng)
    overlap = sample_overlapping_triangles(n, rng)
    noise = rng.normal(size=(n, SECONDARY_NOISE_COUNT))
    return np.column_stack([chain, fork, overlap, noise])


def _primary_category(i: int, j: int) -> str:
    pair = (i, j) if i < j else (j, i)
    if pair in PRIMARY_TRUE_DIRECT_EDGES:
        return "true_direct"
    if pair in PRIMARY_INDIRECT_EDGES:
        return "indirect"
    return "null"


def _secondary_category(i: int, j: int) -> str:
    pair = (i, j) if i < j else (j, i)
    if pair in SECONDARY_TRUE_DIRECT_EDGES:
        return "true_direct"
    if pair in SECONDARY_CHAIN_INDIRECT:
        return "indirect_chain"
    if pair in SECONDARY_FORK_INDIRECT:
        return "indirect_fork"
    if pair in SECONDARY_OVERLAP_INDIRECT:
        return "indirect_overlap"
    return "null"


@dataclass(frozen=True)
class Stage3Config:
    primary_sample_sizes: tuple[int, ...]
    primary_strength: float
    primary_triangle_family: str
    primary_noise_count: int
    primary_screening_alpha: float
    primary_replicates: int
    primary_development_replicates: tuple[int, int]
    primary_validation_replicates: tuple[int, int]
    secondary_sample_size: int
    secondary_strength: float
    secondary_screening_alpha: float
    secondary_replicates: int
    bootstraps: int
    master_seed: int
    pi_min_candidates: tuple[float, ...]
    minimum_stability_recall: float
    maximum_stability_fdr: float
    false_edge_rate_tolerance: float
    source_path: Path | None = None


def load_stage3_config(path: Path) -> Stage3Config:
    """Load a Stage 3 configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 3 configuration must be a mapping")

    primary = values["primary"]
    secondary = values["secondary"]

    return Stage3Config(
        primary_sample_sizes=tuple(int(v) for v in primary["sample_sizes"]),
        primary_strength=float(primary["strength"]),
        primary_triangle_family=str(primary["triangle_family"]),
        primary_noise_count=int(primary["noise_count"]),
        primary_screening_alpha=float(primary["screening_alpha"]),
        primary_replicates=int(primary["replicates"]),
        primary_development_replicates=tuple(int(v) for v in primary["development_replicates"]),
        primary_validation_replicates=tuple(int(v) for v in primary["validation_replicates"]),
        secondary_sample_size=int(secondary["sample_size"]),
        secondary_strength=float(secondary["strength"]),
        secondary_screening_alpha=float(secondary.get("screening_alpha", primary["screening_alpha"])),
        secondary_replicates=int(secondary["replicates"]),
        bootstraps=int(values["bootstraps"]),
        master_seed=int(values["master_seed"]),
        pi_min_candidates=tuple(float(v) for v in values["pi_min_candidates"]),
        minimum_stability_recall=float(values["minimum_stability_recall"]),
        maximum_stability_fdr=float(values["maximum_stability_fdr"]),
        false_edge_rate_tolerance=float(values["false_edge_rate_tolerance"]),
        source_path=path.resolve(),
    )


# Fixed integer stream tags distinguishing independent seed streams -- not
# Python's built-in hash(), which is randomized per-process (PYTHONHASHSEED)
# and would silently break run-to-run reproducibility.
_PRIMARY_DATA_STREAM = 1
_PRIMARY_BOOTSTRAP_STREAM = 2
_SECONDARY_DATA_STREAM = 3
_SECONDARY_BOOTSTRAP_STREAM = 4


def _condition_seed(master_seed: int, stream: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, stream, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage3Config) -> Path:
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


def _resolved_config(config: Stage3Config) -> dict[str, object]:
    return {
        "primary": {
            "sample_sizes": list(config.primary_sample_sizes),
            "strength": config.primary_strength,
            "triangle_family": config.primary_triangle_family,
            "noise_count": config.primary_noise_count,
            "screening_alpha": config.primary_screening_alpha,
            "replicates": config.primary_replicates,
            "development_replicates": list(config.primary_development_replicates),
            "validation_replicates": list(config.primary_validation_replicates),
        },
        "secondary": {
            "sample_size": config.secondary_sample_size,
            "strength": config.secondary_strength,
            "screening_alpha": config.secondary_screening_alpha,
            "replicates": config.secondary_replicates,
        },
        "bootstraps": config.bootstraps,
        "master_seed": config.master_seed,
        "pi_min_candidates": list(config.pi_min_candidates),
        "minimum_stability_recall": config.minimum_stability_recall,
        "maximum_stability_fdr": config.maximum_stability_fdr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
    }


def _write_evidence(config: Stage3Config, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage3_charter.md"
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


def _run_one_replicate(
    *,
    dgp: str,
    n: int,
    replicate: int,
    data_seed: int,
    bootstrap_seed: int,
    screening_alpha: float,
    dpi_alpha: float,
    bootstraps: int,
    p: int,
    category_fn,
    sample_fn,
) -> list[dict[str, object]]:
    try:
        data = sample_fn(np.random.default_rng(data_seed))
        evidence = compute_pairwise_screening_evidence(data)
        screened_point = screen_uncorrected(evidence, screening_alpha)
        final_point, _ = compose_screen_then_prune(data, screened_point, dpi_alpha)
        stability = compute_edge_stability(
            data, screening_alpha, dpi_alpha, bootstraps, np.random.default_rng(bootstrap_seed)
        )
    except Exception as exc:  # raw evidence must retain pipeline failures
        return [
            {
                "dgp": dgp,
                "n": n,
                "replicate": replicate,
                "data_seed": data_seed,
                "bootstrap_seed": bootstrap_seed,
                "dpi_alpha": dpi_alpha,
                "i": -1,
                "j": -1,
                "category": "",
                "screened_point": np.nan,
                "final_point": np.nan,
                "pi_candidate": np.nan,
                "pi_final": np.nan,
                "successful_bootstraps": 0,
                "failed_bootstraps": 0,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        ]

    rows: list[dict[str, object]] = []
    for i, j in combinations(range(p), 2):
        rows.append(
            {
                "dgp": dgp,
                "n": n,
                "replicate": replicate,
                "data_seed": data_seed,
                "bootstrap_seed": bootstrap_seed,
                "dpi_alpha": dpi_alpha,
                "i": i,
                "j": j,
                "category": category_fn(i, j),
                "screened_point": bool(screened_point[i, j]),
                "final_point": bool(final_point[i, j]),
                "pi_candidate": float(stability.pi_candidate[i, j]),
                "pi_final": float(stability.pi_final[i, j]),
                "successful_bootstraps": stability.successful_bootstraps,
                "failed_bootstraps": stability.failed_bootstraps,
                "status": "ok",
                "error": "",
            }
        )
    return rows


def run_stage3(config: Stage3Config, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 3 conditions (both DGPs) and persist only raw evidence."""
    run_started = time.perf_counter()
    selected_form = select_form(fit_candidate_forms())

    rows: list[dict[str, object]] = []

    for sample_index, n in enumerate(config.primary_sample_sizes):
        dpi_alpha = selected_form.predict(float(n))
        for replicate in range(config.primary_replicates):
            data_seed = _condition_seed(config.master_seed, _PRIMARY_DATA_STREAM, sample_index, replicate)
            bootstrap_seed = _condition_seed(config.master_seed, _PRIMARY_BOOTSTRAP_STREAM, sample_index, replicate)
            rows.extend(
                _run_one_replicate(
                    dgp="primary",
                    n=n,
                    replicate=replicate,
                    data_seed=data_seed,
                    bootstrap_seed=bootstrap_seed,
                    screening_alpha=config.primary_screening_alpha,
                    dpi_alpha=dpi_alpha,
                    bootstraps=config.bootstraps,
                    p=PRIMARY_P,
                    category_fn=_primary_category,
                    sample_fn=lambda rng: sample_screening_network(
                        n, config.primary_strength, config.primary_triangle_family, config.primary_noise_count, rng
                    ),
                )
            )

    secondary_n = config.secondary_sample_size
    secondary_dpi_alpha = selected_form.predict(float(secondary_n))
    for replicate in range(config.secondary_replicates):
        data_seed = _condition_seed(config.master_seed, _SECONDARY_DATA_STREAM, 0, replicate)
        bootstrap_seed = _condition_seed(config.master_seed, _SECONDARY_BOOTSTRAP_STREAM, 0, replicate)
        rows.extend(
            _run_one_replicate(
                dgp="secondary_overlap_diagnostic",
                n=secondary_n,
                replicate=replicate,
                data_seed=data_seed,
                bootstrap_seed=bootstrap_seed,
                screening_alpha=config.secondary_screening_alpha,
                dpi_alpha=secondary_dpi_alpha,
                bootstraps=config.bootstraps,
                p=SECONDARY_P,
                category_fn=_secondary_category,
                sample_fn=lambda rng: _sample_secondary_network(secondary_n, config.secondary_strength, rng),
            )
        )

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage3_reporting import write_stage3_report

    write_stage3_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage3(load_stage3_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
