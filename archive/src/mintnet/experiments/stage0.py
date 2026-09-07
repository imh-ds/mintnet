"""Deterministic runner for the Stage 0.1 Gaussian MI experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mintnet.mi.ksg import estimate_ksg_mi
from mintnet.simulation.gaussian import gaussian_mi, sample_bivariate_gaussian


@dataclass(frozen=True)
class Stage0Config:
    sample_sizes: tuple[int, ...]
    rhos: tuple[float, ...]
    k_values: tuple[int, ...]
    replicates: int
    master_seed: int
    development_replicates: tuple[int, int]
    validation_replicates: tuple[int, int]
    moderate_sample_sizes: tuple[int, ...]
    moderate_rhos: tuple[float, ...]
    max_absolute_bias: float
    max_rmse: float
    min_rank_spearman: float
    max_null_q95: float
    source_path: Path | None = None


def _tuple_of(mapping: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in mapping[key])


def load_stage0_config(path: Path) -> Stage0Config:
    """Load the frozen Stage 0 configuration from YAML."""
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 0 configuration must be a mapping")
    return Stage0Config(
        sample_sizes=_tuple_of(values, "sample_sizes", int),
        rhos=_tuple_of(values, "rhos", float),
        k_values=_tuple_of(values, "k_values", int),
        replicates=int(values["replicates"]),
        master_seed=int(values["master_seed"]),
        development_replicates=tuple(int(value) for value in values["development_replicates"]),
        validation_replicates=tuple(int(value) for value in values["validation_replicates"]),
        moderate_sample_sizes=_tuple_of(values, "moderate_sample_sizes", int),
        moderate_rhos=_tuple_of(values, "moderate_rhos", float),
        max_absolute_bias=float(values["max_absolute_bias"]),
        max_rmse=float(values["max_rmse"]),
        min_rank_spearman=float(values["min_rank_spearman"]),
        max_null_q95=float(values["max_null_q95"]),
        source_path=path.resolve(),
    )


def _condition_seed(config: Stage0Config, n_index: int, rho_index: int, replicate: int) -> int:
    return int(
        np.random.SeedSequence([config.master_seed, n_index, rho_index, replicate]).generate_state(1)[0]
    )


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_evidence(config: Stage0Config, output_dir: Path, raw: pd.DataFrame) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    resolved = asdict(replace(config, source_path=None))
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved, stream, sort_keys=True)

    charter = Path("docs/stage0_charter.md")
    charter_hash = hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else None
    metadata = {
        "charter_sha256": charter_hash,
        "git_commit": _git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def run_stage0(config: Stage0Config, output_dir: Path) -> pd.DataFrame:
    """Run every configured Gaussian condition and persist raw evidence."""
    rows: list[dict[str, object]] = []
    for n_index, n in enumerate(config.sample_sizes):
        for rho_index, rho in enumerate(config.rhos):
            true_mi = gaussian_mi(rho)
            for replicate in range(config.replicates):
                seed = _condition_seed(config, n_index, rho_index, replicate)
                sample = sample_bivariate_gaussian(n, rho, np.random.default_rng(seed))
                for k in config.k_values:
                    started = time.perf_counter()
                    try:
                        estimate = estimate_ksg_mi(sample[:, 0], sample[:, 1], k=k)
                        status, error = "ok", ""
                    except Exception as exc:  # evidence must preserve estimator failures
                        estimate, status, error = np.nan, "error", f"{type(exc).__name__}: {exc}"
                    rows.append(
                        {
                            "n": n,
                            "rho": rho,
                            "k": k,
                            "replicate": replicate,
                            "seed": seed,
                            "true_mi": true_mi,
                            "estimated_mi": estimate,
                            "elapsed_seconds": time.perf_counter() - started,
                            "status": status,
                            "error": error,
                        }
                    )
    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw)
    # Import here to keep the runner/reporting dependency one-directional at
    # module import time while ensuring the CLI leaves complete evidence.
    from mintnet.experiments.reporting import write_stage0_report

    write_stage0_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage0(load_stage0_config(arguments.config), arguments.output)


if __name__ == "__main__":
    main()
