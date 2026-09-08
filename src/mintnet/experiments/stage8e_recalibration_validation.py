"""Validates the composed-tier false-edge recalibration mapping D-068
first explored descriptively. See docs/stage8e_charter.md.

Reuses Stage 8c's own already-collected (enriched) raw_metrics.csv
entirely -- zero new significance-test evidence, mirroring
scripts/stage7e_alpha_refinement.py's and stage8b_recalibration.py's
own zero-new-compute reuse pattern. Promotes D-068's own exploratory
`exploratory_false_edge_recalibration` procedure (fit per (dgp, N) on
development replicates, evaluate on validation replicates) from a
descriptive report into an explicit PROCEED/REASSESS gate, and
persists the fitted curves as a bundled artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mintnet.confidence.recalibration import calibrated_margin, fit_isotonic_curve, save_curves
from mintnet.experiments.stage8a_calibration_reporting import bin_table, compute_ece
from mintnet.experiments.stage8c_composed_calibration_reporting import explode_edges


@dataclass(frozen=True)
class Stage8eConfig:
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    ece_tolerance: float
    bin_count: int
    source_path: Path | None = None


def load_config(path: Path) -> Stage8eConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 8e configuration must be a mapping")
    return Stage8eConfig(
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        ece_tolerance=float(values["ece_tolerance"]),
        bin_count=int(values["bin_count"]),
        source_path=path.resolve(),
    )


@dataclass(frozen=True)
class Stage8eDecision:
    status: str  # "PROCEED" or "REASSESS"
    ece_tolerance: float
    validation_ece_by_cell: dict[str, float]
    max_ece: float


def fit_composed_false_edge_curves(
    exploded: pd.DataFrame, development_replicates: tuple[int, int]
) -> dict[tuple[str, int], "object"]:
    dev_low, dev_high = development_replicates
    false_edges = exploded.loc[
        (exploded["status"] == "ok") & (~exploded["is_true_edge"]) & exploded["margin"].notna()
    ]
    development = false_edges.loc[(false_edges["replicate"] >= dev_low) & (false_edges["replicate"] <= dev_high)]

    curves = {}
    for (dgp, n), group in development.groupby(["dgp", "n"]):
        curves[(dgp, int(n))] = fit_isotonic_curve(
            group["margin"].to_numpy(dtype=float), group["correct"].to_numpy(dtype=float)
        )
    return curves


def evaluate_stage8e_gate(
    exploded: pd.DataFrame, curves: dict, config: Stage8eConfig
) -> tuple[Stage8eDecision, pd.DataFrame]:
    val_low, val_high = config.validation_replicates
    false_edges = exploded.loc[
        (exploded["status"] == "ok") & (~exploded["is_true_edge"]) & exploded["margin"].notna()
    ]
    validation = false_edges.loc[(false_edges["replicate"] >= val_low) & (false_edges["replicate"] <= val_high)].copy()

    validation["recalibrated"] = [
        calibrated_margin(margin, int(n), dgp, curves=curves)
        for margin, n, dgp in zip(validation["margin"], validation["n"], validation["dgp"])
    ]
    relabeled = validation.rename(columns={"dgp": "motif"})
    relabeled["margin"] = relabeled["recalibrated"]
    edges = np.linspace(0.0, 1.0, config.bin_count + 1)
    relabeled["bin"] = pd.cut(relabeled["margin"], bins=edges, include_lowest=True, labels=False)
    bins = bin_table(relabeled, config.bin_count)
    ece = compute_ece(bins)

    max_ece = max((v for v in ece.values() if v == v), default=float("nan"))
    status = "PROCEED" if max_ece <= config.ece_tolerance else "REASSESS"
    decision = Stage8eDecision(
        status=status,
        ece_tolerance=config.ece_tolerance,
        validation_ece_by_cell={f"{dgp}_n{n}": v for (dgp, n), v in ece.items()},
        max_ece=max_ece,
    )
    return decision, bins


def _repository_root(config: Stage8eConfig) -> Path:
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


def run_stage8e(raw_path: Path, config: Stage8eConfig, output_dir: Path) -> tuple[Stage8eDecision, dict]:
    started = time.perf_counter()
    raw = pd.read_csv(raw_path)
    exploded = explode_edges(raw)

    curves = fit_composed_false_edge_curves(exploded, config.development_replicates)
    decision, bins = evaluate_stage8e_gate(exploded, curves, config)

    output_dir.mkdir(parents=True, exist_ok=True)
    save_curves(curves, output_dir / "composed_false_edge_curves.json")
    bins.to_csv(output_dir / "validation_bin_table.csv", index=False)
    (output_dir / "decision.json").write_text(json.dumps(asdict(decision), indent=2) + "\n", encoding="utf-8")
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(
            {
                "development_replicates": list(config.development_replicates),
                "validation_replicates": list(config.validation_replicates),
                "ece_tolerance": config.ece_tolerance,
                "bin_count": config.bin_count,
                "source_raw_path": str(raw_path),
            },
            stream,
            sort_keys=True,
        )

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage8e_charter.md"
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    metadata = {
        "charter_sha256": charter_hash,
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": time.perf_counter() - started,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return decision, curves


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path, help="path to Stage 8c's own (enriched) raw_metrics.csv")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    decision, _ = run_stage8e(arguments.raw, load_config(arguments.config), arguments.output)
    print(f"Decision: {decision.status}")
    print(f"Max validation ECE: {decision.max_ece:.4f}")


if __name__ == "__main__":
    main()
