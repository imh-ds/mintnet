"""Stage 7 isolation-tier timing/feasibility measurement -- NOT the
frozen charter's own full evidence run. Measures real wall-clock cost
of the ENTIRE growing-subset-DPI-with-CMI pipeline (not a single
significance test in isolation) per replicate, on each isolation-tier
motif, at `N in {750, 1500}` -- the up-front measurement
docs/stage7_charter.md's own "Compute-cost disclosure" section
requires before any replicate count for the real charter run is
finalized. Sharded to the finest useful grain (one replicate per
shard) since per-replicate cost itself varies enormously by motif (a
true edge costs the full combinatorial subset count up to the search
cap; a false edge typically resolves at one test) and by N.
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

from mintnet.pipeline.growing_subset_dpi_mi import growing_subset_dpi_mi
from mintnet.simulation.motifs import sample_hub, sample_overlapping_triangles, sample_precision_triangle

_STAGE_TAG = 700


def _sample_triad_balanced(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_precision_triangle("balanced", n, rng)


def _sample_triad_moderate(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_precision_triangle("moderate", n, rng)


def _sample_triad_strong(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_precision_triangle("strong", n, rng)


def _sample_hub3(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_hub(n, 0.5, 3, rng)


def _sample_overlap(n: int, rng: np.random.Generator) -> np.ndarray:
    return sample_overlapping_triangles(n, rng)


# Isolation tier, identical fixtures to Stage 6a/D-053's own isolation
# tier (docs/stage6a_charter.md) -- no screening, complete candidate
# graph, mechanism only.
MOTIFS: dict[str, Callable[[int, np.random.Generator], np.ndarray]] = {
    "triad_balanced": _sample_triad_balanced,
    "triad_moderate": _sample_triad_moderate,
    "triad_strong": _sample_triad_strong,
    "hub": _sample_hub3,
    "overlap": _sample_overlap,
}
MOTIF_NAMES: tuple[str, ...] = tuple(MOTIFS.keys())


@dataclass(frozen=True)
class Stage7TimingConfig:
    motifs: tuple[str, ...]
    sample_sizes: tuple[int, ...]
    replicates: int
    alpha: float
    k_cmi: int
    k_perm: int
    permutations: int
    master_seed: int
    source_path: Path | None = None


def load_config(path: Path) -> Stage7TimingConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    return Stage7TimingConfig(
        motifs=tuple(str(v) for v in values["motifs"]),
        sample_sizes=tuple(int(v) for v in values["sample_sizes"]),
        replicates=int(values["replicates"]),
        alpha=float(values["alpha"]),
        k_cmi=int(values["k_cmi"]),
        k_perm=int(values["k_perm"]),
        permutations=int(values["permutations"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("motif", "n", "replicate")


def expected_combinations(config: Stage7TimingConfig) -> set[tuple[str, int, int]]:
    return {(motif, n, r) for motif in config.motifs for n in config.sample_sizes for r in range(config.replicates)}


def expected_row_count(config: Stage7TimingConfig) -> int:
    return len(expected_combinations(config))


def _data_seed(master_seed: int, motif_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, _STAGE_TAG, motif_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _run_one_cell(motif: str, n: int, replicate: int, config: Stage7TimingConfig) -> dict[str, object]:
    motif_index = MOTIF_NAMES.index(motif)
    sample_index = config.sample_sizes.index(n)
    seed = _data_seed(config.master_seed, motif_index, sample_index, replicate)
    rng = np.random.default_rng(seed)

    row: dict[str, object] = {
        "motif": motif, "n": n, "replicate": replicate, "seed": seed,
        "status": "ok", "error": "", "wall_seconds": np.nan, "n_significance_tests": np.nan,
        "n_edges_retained": np.nan, "n_candidate_edges": np.nan,
    }
    try:
        data = MOTIFS[motif](n, rng)
        p = data.shape[1]
        flagged = np.ones((p, p), dtype=bool)
        np.fill_diagonal(flagged, False)
        n_candidate_edges = int(flagged.sum() // 2)

        started = time.perf_counter()
        result = growing_subset_dpi_mi(
            data, flagged, config.alpha,
            master_seed=config.master_seed, replicate=replicate,
            k_cmi=config.k_cmi, k_perm=config.k_perm, permutations=config.permutations,
        )
        elapsed = time.perf_counter() - started

        row["wall_seconds"] = elapsed
        row["n_significance_tests"] = result.n_significance_tests
        row["n_edges_retained"] = int(result.adjacency.sum() // 2)
        row["n_candidate_edges"] = n_candidate_edges
    except Exception as exc:
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def _repository_root(source_path: Path | None) -> Path:
    if source_path is not None:
        return source_path.resolve().parent.parent
    return Path(__file__).resolve().parents[3]


def _git_commit(repository_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_evidence(output_dir: Path, raw: pd.DataFrame, config: Stage7TimingConfig, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = {
        "motifs": list(config.motifs),
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "alpha": config.alpha,
        "k_cmi": config.k_cmi,
        "k_perm": config.k_perm,
        "permutations": config.permutations,
        "master_seed": config.master_seed,
        "note": (
            "Timing/feasibility measurement only, per docs/stage7_charter.md's own "
            "'Compute-cost disclosure' section -- not the frozen charter's own evidence run. "
            "alpha=0.05 here is a provisional choice for measurement purposes only, not this "
            "charter's own eventual selected alpha (which the real run's own development/"
            "validation sweep determines)."
        ),
    }
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    repository_root = _repository_root(config.source_path)
    charter = repository_root / "docs/stage7_charter.md"
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


_COLUMNS = (
    "motif", "n", "replicate", "seed", "status", "error",
    "wall_seconds", "n_significance_tests", "n_edges_retained", "n_candidate_edges",
)


def run_stage7_timing(
    config: Stage7TimingConfig,
    output_dir: Path,
    motifs: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    replicates: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`motifs`/`sample_sizes`/`replicates` restrict which cells run,
    for a single-cell CI shard -- seeds key off the full grid's own
    `motif`/`n` indices (via `MOTIF_NAMES`/`config.sample_sizes`), not
    a filtered subset's, so a shard's results match an unsharded run's
    for the same cell."""
    started = time.perf_counter()
    target_motifs = motifs if motifs is not None else config.motifs
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_replicates = replicates if replicates is not None else tuple(range(config.replicates))

    rows = [
        _run_one_cell(motif, n, replicate, config)
        for motif in target_motifs
        for n in target_sizes
        for replicate in target_replicates
    ]
    raw = pd.DataFrame(rows, columns=_COLUMNS) if not rows else pd.DataFrame(rows)
    _write_evidence(output_dir, raw, config, time.perf_counter() - started)

    if not write_report:
        return raw
    from mintnet.experiments.stage7_isolation_timing_reporting import write_report as write_timing_report

    write_timing_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--motifs", type=str, default=None, help="comma-separated subset of motifs (default: all)")
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--replicates", type=str, default=None, help="comma-separated subset of replicate indices (default: all)"
    )
    parser.add_argument(
        "--no-report", action="store_true", help="skip the descriptive report (use for CI shards)"
    )
    arguments = parser.parse_args()

    motifs = tuple(arguments.motifs.split(",")) if arguments.motifs else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    replicates = tuple(int(v) for v in arguments.replicates.split(",")) if arguments.replicates else None

    run_stage7_timing(
        load_config(arguments.config), arguments.output,
        motifs=motifs, sample_sizes=sample_sizes, replicates=replicates,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
