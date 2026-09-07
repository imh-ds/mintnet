"""Deterministic raw-evidence runner for the frozen Stage 4p canonical
N-grid public benchmark. See docs/stage4p_charter.md.

Runs both engines (conservative: `mintnet.pipeline.
compose_screen_then_prune`; sequential: `mintnet.pipeline.
sequential_screen_and_prune_detailed`) on identical simulated data every
replicate, for both existing p=15 composed networks (overlap-based,
`mintnet.experiments.stage2d`; hub-based, `mintnet.experiments.stage4l`),
across one fixed canonical N grid. Both engines use the same single
alpha-selection rule -- D-012's already-frozen general formula
(`mintnet.experiments.stage1j_fit`), not overlap's own specialized one
-- deliberately, for a fair, consistent comparison. No new DGP, no new
engine code, no new fitting.
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

from mintnet.experiments import stage2d, stage4l
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.pipeline import compose_screen_then_prune, sequential_screen_and_prune_detailed
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

ENGINES: tuple[str, ...] = ("conservative", "sequential")
DGPS: tuple[str, ...] = ("overlap", "hub")

_DGP_REGISTRY: dict[str, dict[str, object]] = {
    "overlap": {
        "sample": stage2d._sample_network,
        "p": stage2d.P,
        "score": stage2d._score,
        "third_key": "overlap_indirect_tpr",
    },
    "hub": {
        "sample": stage4l._sample_network,
        "p": stage4l.P,
        "score": stage4l._score,
        "third_key": "hub_indirect_tpr",
    },
}


@dataclass(frozen=True)
class Stage4pConfig:
    sample_sizes: tuple[int, ...]
    strength: float
    screening_alpha: float
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


def load_stage4p_config(path: Path) -> Stage4pConfig:
    """Load a Stage 4p configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4p configuration must be a mapping")

    return Stage4pConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strength=float(values["strength"]),
        screening_alpha=float(values["screening_alpha"]),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        minimum_indirect_prune_tpr=float(values["minimum_indirect_prune_tpr"]),
        maximum_true_edge_prune_fpr=float(values["maximum_true_edge_prune_fpr"]),
        false_edge_rate_tolerance=float(values["false_edge_rate_tolerance"]),
        source_path=path.resolve(),
    )


def _condition_seed(master_seed: int, dgp_index: int, sample_index: int, replicate: int) -> int:
    sequence = np.random.SeedSequence([master_seed, dgp_index, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4pConfig) -> Path:
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


def _resolved_config(config: Stage4pConfig, alpha_by_n: dict[int, float]) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strength": config.strength,
        "screening_alpha": config.screening_alpha,
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_indirect_prune_tpr": config.minimum_indirect_prune_tpr,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "false_edge_rate_tolerance": config.false_edge_rate_tolerance,
        "d012_alpha_by_n": alpha_by_n,
    }


def _write_evidence(
    config: Stage4pConfig, output_dir: Path, raw: pd.DataFrame, alpha_by_n: dict[int, float], runtime_seconds: float
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, alpha_by_n), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4p_charter.md"
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


def _conservative_screened_and_final(data: np.ndarray, screening_alpha: float, dpi_alpha: float) -> tuple[np.ndarray, np.ndarray]:
    evidence = compute_pairwise_screening_evidence(data)
    screened = screen_uncorrected(evidence, screening_alpha)
    final, _shapes = compose_screen_then_prune(data, screened, dpi_alpha)
    return screened, final


def _sequential_screened_and_final(data: np.ndarray, alpha: float, p: int) -> tuple[np.ndarray, np.ndarray]:
    final, decisions = sequential_screen_and_prune_detailed(data, alpha)
    screened = np.zeros((p, p), dtype=bool)
    for d in decisions:
        screened[d.i, d.j] = screened[d.j, d.i] = True
    return screened, final


def run_stage4p(config: Stage4pConfig, output_dir: Path) -> pd.DataFrame:
    """Run both engines on both p=15 networks across the canonical N
    grid, paired same-draw per (dgp, N, replicate), reusing D-012's
    already-frozen formula for both engines."""
    run_started = time.perf_counter()

    selected = select_form(fit_candidate_forms())
    alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for dgp_index, dgp_name in enumerate(DGPS):
        dgp = _DGP_REGISTRY[dgp_name]
        sample: Callable = dgp["sample"]  # type: ignore[assignment]
        p = int(dgp["p"])
        score: Callable = dgp["score"]  # type: ignore[assignment]
        third_key = str(dgp["third_key"])

        for sample_index, n in enumerate(config.sample_sizes):
            alpha = alpha_by_n[n]
            for replicate in range(config.replicates):
                seed = _condition_seed(config.master_seed, dgp_index, sample_index, replicate)
                try:
                    data = sample(n, config.strength, np.random.default_rng(seed))
                    status, error = "ok", ""
                except Exception as exc:  # raw evidence must retain pipeline failures
                    data = None
                    status, error = "error", f"{type(exc).__name__}: {exc}"

                for engine in ENGINES:
                    started = time.perf_counter()
                    row_status, row_error = status, error
                    metrics: dict[str, object] = {
                        "chain_indirect_tpr": np.nan,
                        "fork_indirect_tpr": np.nan,
                        "third_indirect_tpr": np.nan,
                        "true_edge_prune_fpr": np.nan,
                        "screening_false_edge_rate": np.nan,
                        "final_false_edge_rate": np.nan,
                    }
                    if data is not None:
                        try:
                            if engine == "conservative":
                                screened, final = _conservative_screened_and_final(data, config.screening_alpha, alpha)
                            else:
                                screened, final = _sequential_screened_and_final(data, alpha, p)
                            raw_metrics = score(screened, final, p)
                            metrics = {
                                "chain_indirect_tpr": raw_metrics["chain_indirect_tpr"],
                                "fork_indirect_tpr": raw_metrics["fork_indirect_tpr"],
                                "third_indirect_tpr": raw_metrics[third_key],
                                "true_edge_prune_fpr": raw_metrics["true_edge_prune_fpr"],
                                "screening_false_edge_rate": raw_metrics["screening_false_edge_rate"],
                                "final_false_edge_rate": raw_metrics["final_false_edge_rate"],
                            }
                        except Exception as exc:  # retain pruning/scoring failures by engine
                            row_status = "error"
                            row_error = f"{type(exc).__name__}: {exc}"

                    rows.append(
                        {
                            "dgp": dgp_name,
                            "engine": engine,
                            "n": n,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": seed,
                            **metrics,
                            "elapsed_seconds": time.perf_counter() - started,
                            "status": row_status,
                            "error": row_error,
                        }
                    )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, alpha_by_n, time.perf_counter() - run_started)
    from mintnet.experiments.stage4p_reporting import write_stage4p_report

    write_stage4p_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4p(load_stage4p_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
