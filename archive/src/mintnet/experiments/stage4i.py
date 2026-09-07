"""Deterministic raw-evidence runner for the frozen Stage 4i alpha(N)
repair experiment (sequential engine, overlap shape). See
docs/stage4i_charter.md.

Reuses Stage 1L's overlap DGP/ground truth, Stage 4b/d/e/f/g's exact
seed derivation, and Stage 4a's sequential engine
(`sequential_screen_and_prune_detailed`) unmodified. Fits via
`mintnet.experiments.stage4i_fit` (Stage 4g's own selection rule, with
`N=750` moved out of the fitting set).

**Implementation-time correction to the charter's own text (discovered
before any evidence existed, documented here rather than silently
patched, per this project's established practice):**
`docs/stage4i_charter.md` proposed reusing Stage 4g's already-generated
evidence verbatim for the five non-750 held-out `N`. Computing the
refit formula first (as this module does below) showed this is not
sound: the refit predicts a *different* alpha at every held-out `N`
than Stage 4g's original formula did -- most importantly, it flips
`N=725` from positive (`.0015`, Stage 4g's own PROCEED cell) to
negative (`-.0023`), which Stage 4g's raw evidence was never simulated
under. Reusing that evidence verbatim would silently test the wrong
alpha. This module instead **freshly simulates all six held-out `N`**
under the refit formula's own single predicted alpha per `N`, exactly
mirroring Stage 4g's own precedent of always fresh-simulating held-out
cells rather than reusing anything for them. Note this reproduces
Stage 4g's own underlying sampled data bit-for-bit at the five shared
`N` (seed derivation depends only on `master_seed`, shape index, `N`'s
position in the sample-size list, and replicate -- never on alpha), so
the two runs differ only in which alpha screens that data, not in the
data itself.
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
from mintnet.experiments.stage1l import INDIRECT_EDGES as OVERLAP_INDIRECT_EDGES
from mintnet.experiments.stage1l import TRUE_EDGES as OVERLAP_TRUE_EDGES
from mintnet.experiments.stage4b import SHAPES
from mintnet.experiments.stage4i_fit import compute_fitting_points, fitting_point_self_check
from mintnet.pipeline import sequential_screen_and_prune_detailed
from mintnet.simulation import sample_overlapping_triangles

_OVERLAP_SHAPE_INDEX = SHAPES.index("overlap")


@dataclass(frozen=True)
class Stage4iConfig:
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


def load_stage4i_config(path: Path) -> Stage4iConfig:
    """Load a Stage 4i configuration, retaining the path used to resolve it."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 4i configuration must be a mapping")

    return Stage4iConfig(
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


def _condition_seed(master_seed: int, sample_index: int, replicate: int) -> int:
    # Matches Stage 4b/4d/4e/4f/4g's exact seed derivation for overlap's
    # shape index -- identical (n, replicate) positions reproduce Stage
    # 4g's own sampled data bit-for-bit; only the screening alpha differs.
    sequence = np.random.SeedSequence([master_seed, _OVERLAP_SHAPE_INDEX, sample_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage4iConfig) -> Path:
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


def _resolved_config(
    config: Stage4iConfig, selected_form_name: str, predicted_alpha_by_n: dict[int, float]
) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
        "development_replicates": list(config.development_replicates),
        "validation_replicates": list(config.validation_replicates),
        "minimum_conditional_accuracy": config.minimum_conditional_accuracy,
        "maximum_true_edge_prune_fpr": config.maximum_true_edge_prune_fpr,
        "required_margin": config.required_margin,
        "selected_form": selected_form_name,
        "predicted_alpha_by_n": predicted_alpha_by_n,
    }


def _write_evidence(
    config: Stage4iConfig,
    output_dir: Path,
    raw: pd.DataFrame,
    fitting_points: tuple[tuple[float, float], ...],
    self_check: tuple[dict[str, object], ...],
    selected_form_name: str,
    predicted_alpha_by_n: dict[int, float],
    stage4e_raw_path: Path,
    runtime_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config, selected_form_name, predicted_alpha_by_n), stream, sort_keys=True)
    (output_dir / "fitting_points.json").write_text(
        json.dumps(
            {
                "points": [{"n": n, "alpha_star": a} for n, a in fitting_points],
                "fitting_point_self_check": list(self_check),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage4i_charter.md"
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    metadata = {
        "charter_sha256": charter_hash,
        "stage4e_raw_evidence_path": str(stage4e_raw_path),
        "stage4e_raw_evidence_sha256": hashlib.sha256(stage4e_raw_path.read_bytes()).hexdigest(),
        "git_commit": _git_commit(repository_root),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _pair_label(i: int, j: int) -> str:
    return f"{i}{j}"


def run_stage4i(config: Stage4iConfig, stage4e_raw_path: Path, output_dir: Path) -> pd.DataFrame:
    """Refit alpha(N) with N=750 held out, self-check the refit formula at
    its own fitting points, then freshly simulate and validate at all
    configured held-out sample sizes (including 750)."""
    run_started = time.perf_counter()

    fitting_points = compute_fitting_points(stage4e_raw_path)
    forms = fit_candidate_forms(fitting_points)
    selected = select_form(forms)
    self_check = fitting_point_self_check(selected, fitting_points)
    predicted_alpha_by_n = {n: selected.predict(float(n)) for n in config.sample_sizes}

    rows: list[dict[str, object]] = []
    for sample_index, n in enumerate(config.sample_sizes):
        alpha = predicted_alpha_by_n[n]
        for replicate in range(config.replicates):
            seed = _condition_seed(config.master_seed, sample_index, replicate)
            started = time.perf_counter()
            row: dict[str, object] = {}
            row_status, row_error = "ok", ""
            true_edge_fpr = np.nan
            for i, j in OVERLAP_INDIRECT_EDGES:
                row[f"candidate_{_pair_label(i, j)}"] = np.nan
                row[f"correctly_pruned_{_pair_label(i, j)}"] = np.nan
            try:
                if not (0.0 < alpha < 1.0):
                    raise ValueError(f"predicted alpha {alpha!r} is not a valid probability")
                data = sample_overlapping_triangles(n, np.random.default_rng(seed))
                final, decisions = sequential_screen_and_prune_detailed(data, alpha)
                by_pair = {(d.i, d.j): d for d in decisions}
                true_retained = sum(1 for i, j in OVERLAP_TRUE_EDGES if final[i, j])
                true_edge_fpr = 1.0 - (true_retained / len(OVERLAP_TRUE_EDGES))
                for i, j in OVERLAP_INDIRECT_EDGES:
                    decision = by_pair.get((i, j))
                    label = _pair_label(i, j)
                    if decision is None:
                        row[f"candidate_{label}"] = False
                        row[f"correctly_pruned_{label}"] = np.nan
                    else:
                        row[f"candidate_{label}"] = True
                        row[f"correctly_pruned_{label}"] = not decision.confirmed
            except Exception as exc:  # raw evidence must retain pipeline/formula failures
                row_status, row_error = "error", f"{type(exc).__name__}: {exc}"

            rows.append(
                {
                    "n": n,
                    "alpha": alpha,
                    "replicate": replicate,
                    "seed": seed,
                    **row,
                    "true_edge_prune_fpr": true_edge_fpr,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": row_status,
                    "error": row_error,
                }
            )
    raw = pd.DataFrame(rows)
    _write_evidence(
        config, output_dir, raw, fitting_points, self_check, selected.name, predicted_alpha_by_n,
        stage4e_raw_path, time.perf_counter() - run_started,
    )
    from mintnet.experiments.stage4i_reporting import write_stage4i_report

    write_stage4i_report(raw, config, fitting_points, self_check, selected, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stage4e-raw-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage4i(load_stage4i_config(arguments.config), arguments.stage4e_raw_evidence, arguments.output)


if __name__ == "__main__":
    main()
