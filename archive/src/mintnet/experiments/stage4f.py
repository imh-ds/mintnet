"""Deterministic raw-evidence runner for the frozen Stage 4f diagnostic
charter (candidacy-accuracy anomaly). See docs/stage4f_charter.md.

Purely diagnostic -- no engine change. Computes marginal screening
evidence (`mintnet.screening.compute_pairwise_screening_evidence`) and,
for each of the 4 cross-branch overlap pairs that clears the marginal
alpha threshold, the partial correlation conditioning on node 2 (the
shared node) via `mintnet.dpi.multi_conditional.
compute_partial_correlation_evidence`, independently of
`mintnet.pipeline.sequential_screen_and_prune_detailed` -- a documented
simplification (node 2 is the neighbor these pairs are tested against in
practice for this no-noise DGP, but this charter does not re-run the
live engine to confirm that per replicate).

Reuses Stage 1L's overlap DGP/ground truth and Stage 4b/4d/4e's exact
seed derivation for direct comparability.
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

from mintnet.dpi.multi_conditional import compute_partial_correlation_evidence
from mintnet.experiments.stage1l import INDIRECT_EDGES as OVERLAP_INDIRECT_EDGES
from mintnet.experiments.stage4b import SHAPES
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected
from mintnet.simulation import sample_overlapping_triangles

_OVERLAP_SHAPE_INDEX = SHAPES.index("overlap")
_SHARED_NODE = 2


@dataclass(frozen=True)
class Stage4fConfig:
    sample_sizes: tuple[int, ...]
    alphas: tuple[float, ...]
    replicates: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_stage4f_config(path: Path) -> Stage4fConfig:
    """Load a Stage 4f configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4f configuration must be a mapping")

    return Stage4fConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        alphas=_values(values, "alphas", float),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, sample_index: int, replicate: int) -> int:
    # Matches Stage 4b/4d/4e's exact seed derivation for overlap's shape
    # index, so this charter examines the identical draws already analyzed.
    sequence = np.random.SeedSequence([master_seed, _OVERLAP_SHAPE_INDEX, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4fConfig) -> Path:
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


def _resolved_config(config: Stage4fConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "alphas": list(config.alphas),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
    }


def _write_evidence(config: Stage4fConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4f_charter.md"
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


def run_stage4f(config: Stage4fConfig, output_dir: Path) -> pd.DataFrame:
    """Run configured Stage 4f conditions and persist only raw evidence."""
    run_started = time.perf_counter()
    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, sample_index, replicate)
            started = time.perf_counter()
            try:
                data = sample_overlapping_triangles(n, np.random.default_rng(seed))
                evidence = compute_pairwise_screening_evidence(data)
                status, error = "ok", ""
            except Exception as exc:  # raw evidence must retain pipeline failures
                data = None
                evidence = None
                status, error = "error", f"{type(exc).__name__}: {exc}"

            for alpha in config.alphas:
                for i, j in OVERLAP_INDIRECT_EDGES:
                    row_status, row_error = status, error
                    r_marginal = np.nan
                    candidate = np.nan
                    r_partial = np.nan
                    correctly_pruned = np.nan
                    if evidence is not None:
                        try:
                            flagged = screen_uncorrected(evidence, alpha)
                            r_marginal = float(evidence.correlation[i, j])
                            candidate = bool(flagged[i, j])
                            if candidate:
                                test = compute_partial_correlation_evidence(data, i, j, [_SHARED_NODE])
                                r_partial = test.partial_correlation
                                correctly_pruned = test.p_value > alpha
                        except Exception as exc:  # retain scoring failures by alpha/pair
                            row_status = "error"
                            row_error = f"{type(exc).__name__}: {exc}"

                    rows.append(
                        {
                            "n": n,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": seed,
                            "i": i,
                            "j": j,
                            "r_marginal": r_marginal,
                            "candidate": candidate,
                            "r_partial": r_partial,
                            "correctly_pruned": correctly_pruned,
                            "elapsed_seconds": time.perf_counter() - started,
                            "status": row_status,
                            "error": row_error,
                        }
                    )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    from mintnet.experiments.stage4f_reporting import write_stage4f_report

    write_stage4f_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4f(load_stage4f_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
