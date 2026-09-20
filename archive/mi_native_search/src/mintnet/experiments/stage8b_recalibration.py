"""Chain/fork margin recalibration -- fits and validates the Stage 8b
isotonic mapping entirely from Stage 8a's own already-collected
raw_metrics.csv (see docs/stage8b_charter.md, D-066). No new
significance-test evidence is generated; this mirrors
scripts/stage7e_alpha_refinement.py's own zero-new-compute reuse
pattern, applied to fitting a calibration mapping instead of
re-thresholding a gate.
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

import pandas as pd
import yaml

from mintnet.confidence.recalibration import (
    evaluate_recalibrated_ece,
    fit_calibration_curves,
    save_curves,
)
from mintnet.experiments.stage8a_calibration_reporting import compute_ece

_GATED_MOTIFS = ("chain", "fork")


@dataclass(frozen=True)
class Stage8bConfig:
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    ece_tolerance: float
    bin_count: int
    source_path: Path | None = None


def load_config(path: Path) -> Stage8bConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 8b configuration must be a mapping")
    return Stage8bConfig(
        development_replicates=tuple(int(v) for v in values["development_replicates"]),
        validation_replicates=tuple(int(v) for v in values["validation_replicates"]),
        ece_tolerance=float(values["ece_tolerance"]),
        bin_count=int(values["bin_count"]),
        source_path=path.resolve(),
    )


@dataclass(frozen=True)
class Stage8bDecision:
    status: str  # "PROCEED" or "REASSESS"
    ece_tolerance: float
    gated_motifs: list[str]
    validation_ece_by_cell: dict[str, float]
    max_gated_ece: float
    descriptive_ece_by_cell: dict[str, float]


def evaluate_stage8b_gate(
    raw: pd.DataFrame,
    curves: dict[tuple[str, int], "object"],
    config: Stage8bConfig,
) -> tuple[Stage8bDecision, pd.DataFrame]:
    bins = evaluate_recalibrated_ece(raw, curves, config.validation_replicates, config.bin_count)
    ece = compute_ece(bins)

    gated = {key: value for key, value in ece.items() if key[0] in _GATED_MOTIFS}
    max_gated_ece = max((value for value in gated.values() if value == value), default=float("nan"))
    status = "PROCEED" if max_gated_ece <= config.ece_tolerance else "REASSESS"

    decision = Stage8bDecision(
        status=status,
        ece_tolerance=config.ece_tolerance,
        gated_motifs=list(_GATED_MOTIFS),
        validation_ece_by_cell={f"{motif}_n{n}": value for (motif, n), value in gated.items()},
        max_gated_ece=max_gated_ece,
        descriptive_ece_by_cell={f"{motif}_n{n}": value for (motif, n), value in ece.items()},
    )
    return decision, bins


def _repository_root(config: Stage8bConfig) -> Path:
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


def run_stage8b(raw_path: Path, config: Stage8bConfig, output_dir: Path) -> tuple[pd.DataFrame, Stage8bDecision]:
    started = time.perf_counter()
    raw = pd.read_csv(raw_path)

    curves = fit_calibration_curves(raw, config.development_replicates)
    decision, bins = evaluate_stage8b_gate(raw, curves, config)

    output_dir.mkdir(parents=True, exist_ok=True)
    save_curves(curves, output_dir / "calibration_curves.json")
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
    charter = repository_root / "docs/stage8b_charter.md"
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
    return raw, decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path, help="path to Stage 8a's own raw_metrics.csv")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    _, decision = run_stage8b(arguments.raw, load_config(arguments.config), arguments.output)
    print(f"Decision: {decision.status}")
    print(f"Max gated (chain/fork) validation ECE: {decision.max_gated_ece:.4f}")


if __name__ == "__main__":
    main()
