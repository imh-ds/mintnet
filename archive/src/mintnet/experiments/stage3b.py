"""Deterministic raw-evidence runner for the frozen Stage 3b stability-
filtering experiment. See docs/stage3b_charter.md.

Reuses Stage 2d's shared-node-overlap DGP (the specific network D-018
found REASSESS on at `N=750`) and Stage 3's generic per-replicate
pipeline-plus-bootstrap runner (`mintnet.experiments.stage3._run_one_replicate`,
imported rather than duplicated -- it is DGP-agnostic, parameterized by
`category_fn`/`sample_fn`). Raw evidence is long-format, identical in
shape to Stage 3's: one row per (n, replicate, pair) with `status="ok"`,
or one row per (n, replicate) with `status="error"`.

The stability *filter* itself (drop an edge if `pi_final < pi_min`) is
pure post-hoc arithmetic on already-computed `final_point`/`pi_final`
columns -- it is applied in `mintnet.experiments.stage3b_reporting`, not
here, so every candidate `pi_min` can be evaluated from one run's raw
evidence without resampling per threshold.
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

from mintnet.experiments.stage2d import CHAIN_INDIRECT, FORK_INDIRECT, NOISE_COUNT, OVERLAP_INDIRECT, P, TRUE_DIRECT_EDGES
from mintnet.experiments.stage3 import _run_one_replicate
from mintnet.simulation import sample_chain, sample_measured_fork, sample_overlapping_triangles


def _sample_network(n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    """Stage 2d's DGP: chain (0-2), measured fork (3-5), shared-node overlap
    (6-10, node 8 shared), and noise (11-14). See docs/stage2d_charter.md."""
    chain = sample_chain(n, strength, rng)
    fork = sample_measured_fork(n, strength, rng)
    overlap = sample_overlapping_triangles(n, rng)
    noise = rng.normal(size=(n, NOISE_COUNT))
    return np.column_stack([chain, fork, overlap, noise])


def _category(i: int, j: int) -> str:
    pair = (i, j) if i < j else (j, i)
    if pair in TRUE_DIRECT_EDGES:
        return "true_direct"
    if pair in CHAIN_INDIRECT:
        return "indirect_chain"
    if pair in FORK_INDIRECT:
        return "indirect_fork"
    if pair in OVERLAP_INDIRECT:
        return "indirect_overlap"
    return "null"


@dataclass(frozen=True)
class Stage3bConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha: float
    replicates: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    bootstraps: int
    master_seed: int
    pi_min_candidates: tuple[float, ...]
    minimum_overlap_indirect_tpr: float
    maximum_true_edge_fpr: float
    false_edge_rate_tolerance: float
    source_path: Path | None = None


def load_stage3b_config(path: Path) -> Stage3bConfig:
    """Load a Stage 3b configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 3b configuration must be a mapping")

    return Stage3bConfig(
        sample_sizes=tuple(int(v) for v in values["sample_sizes"]),
        strength=float(values["strength"]),
        screening_alpha=float(values["screening_alpha"]),
        replicates=int(values["replicates"]),
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        bootstraps=int(values["bootstraps"]),
        master_seed=int(values["master_seed"]),
        pi_min_candidates=tuple(float(v) for v in values["pi_min_candidates"]),
        minimum_overlap_indirect_tpr=float(values["minimum_overlap_indirect_tpr"]),
        maximum_true_edge_fpr=float(values["maximum_true_edge_fpr"]),
        false_edge_rate_tolerance=float(values["false_edge_rate_tolerance"]),
        source_path=path.resolve(),
    )


# Fixed integer stream tags -- not Python's built-in hash(), which is
# randomized per-process and would silently break reproducibility.
_DATA_STREAM = 1
_BOOTSTRAP_STREAM = 2


def _condition_seed(master_seed: int, stream: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, stream, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage3bConfig) -> Path:
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


def _resolved_config(config: Stage3bConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "noise_count": NOISE_COUNT,
        "screening_alpha": config.screening_alpha,
        "replicates": config.replicates,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "bootstraps": config.bootstraps,
        "master_seed": config.master_seed,
        "pi_min_candidates": list(config.pi_min_candidates),
        "minimum_overlap_indirect_tpr": config.minimum_overlap_indirect_tpr,
        "maximum_true_edge_fpr": config.maximum_true_edge_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
    }


def _write_evidence(config: Stage3bConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage3b_charter.md"
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


def run_stage3b(config: Stage3bConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 3b conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form

    selected_form = select_form(fit_candidate_forms())

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        dpi_alpha = selected_form.predict(float(n))
        for replicate in range(config.replicates):
            data_seed = _condition_seed(config.master_seed, _DATA_STREAM, sample_index, replicate)
            bootstrap_seed = _condition_seed(config.master_seed, _BOOTSTRAP_STREAM, sample_index, replicate)
            rows.extend(
                _run_one_replicate(
                    dgp="overlap",
                    n=n,
                    replicate=replicate,
                    data_seed=data_seed,
                    bootstrap_seed=bootstrap_seed,
                    screening_alpha=config.screening_alpha,
                    dpi_alpha=dpi_alpha,
                    bootstraps=config.bootstraps,
                    p=P,
                    category_fn=_category,
                    sample_fn=lambda rng, n=n: _sample_network(n, config.strength, rng),
                )
            )

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage3b_reporting import write_stage3b_report

    write_stage3b_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage3b(load_stage3b_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
