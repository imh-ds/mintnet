"""Deterministic, shardable raw-evidence runner for the frozen Stage 8f
collider-conditioning-bias diagnostic. See docs/stage8f_charter.md.

Three fixtures, all newly introduced by this charter (not reused from
any existing motif or composed-network module):

- ``step1``: `mintnet.simulation.motifs.sample_collider` (3 columns,
  ``X1, X2 -> X3``). Tests H1 -- does conditioning on the sole collider
  ``X3`` alone induce an elevated rejection rate for the known-false
  ``X1``-``X2`` edge?
- ``step2_collider``: a 4-column extension (``X1``, ``X2``, the same
  collider ``X3``, and an independent decoy ``W``). Tests the size-2
  conditioning set ``{X3, W}`` jointly.
- ``step2_control``: identical to ``step2_collider`` except the third
  column is a second independent decoy ``V`` (no causal link to
  ``X1``/``X2`` at all), not a collider. Tests the same size-2
  conditioning-set *shape* with no collider present, as H2's own
  matched control.

Implementation-time note, disclosed before any evidence exists (this
project's own established practice for a deviation discovered while
building, not after results -- see stage5a.py's own precedent): the
charter's own text frames Step 2 as "the size-2 subset `growing_subset_
dpi`'s own OR-rule actually tests once size 1 fails to prune." Building
it, this does not hold for `step2_control`: its own decoy `W` is
genuinely independent of `X1`/`X2`, so a real OR-rule search would
correctly prune at conditioning size 1 (via the `{W}`-alone subset)
before ever reaching size 2 -- which would make it impossible to ever
compare the two conditions at a *matched* conditioning-set size through
the end-to-end pipeline at all. This runner instead tests the exact
size-2 conditioning set directly via `compute_partial_correlation_
evidence(data, 0, 1, (2, 3))`, the same "isolated significance-test
comparison, not a full `growing_subset_dpi` component search" framing
Step 1 already uses -- consistent with, not a departure from, the
charter's own stated methodology.

``step2_control`` loops across the same `strengths` grid as the other
two fixtures purely to keep the combination-key schema uniform for
shard aggregation -- the control DGP itself does not depend on
`strength` at all (`V` is a plain independent decoy).
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
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.simulation.motifs import sample_collider

FIXTURES: tuple[str, ...] = ("step1", "step2_collider", "step2_control")
_FIXTURE_CONDITIONING: dict[str, tuple[int, ...]] = {
    "step1": (2,),
    "step2_collider": (2, 3),
    "step2_control": (2, 3),
}


def _sample_step2(n: int, strength: float, rng: np.random.Generator, *, collider: bool) -> np.ndarray:
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    if collider:
        x3 = strength * x1 + strength * x2 + np.sqrt(1.0 - 2.0 * strength**2) * rng.normal(size=n)
    else:
        x3 = rng.normal(size=n)  # decoy V -- no causal link to x1/x2
    w = rng.normal(size=n)  # decoy W -- no causal link to anything
    return np.column_stack((x1, x2, x3, w))


def _sample_fixture(fixture: str, n: int, strength: float, rng: np.random.Generator) -> np.ndarray:
    if fixture == "step1":
        return sample_collider(n, strength, rng)
    if fixture == "step2_collider":
        return _sample_step2(n, strength, rng, collider=True)
    if fixture == "step2_control":
        return _sample_step2(n, strength, rng, collider=False)
    raise ValueError(f"unknown fixture: {fixture!r}")


@dataclass(frozen=True)
class Stage8fConfig:
    sample_sizes: tuple[int, ...]
    strengths: tuple[float, ...]
    replicates: int
    batch_size: int
    master_seed: int
    source_path: Path | None = None


def _values(values: dict[str, object], key: str, cast: type[int] | type[float]) -> tuple:
    return tuple(cast(value) for value in values[key])


def load_config(path: Path) -> Stage8fConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 8f configuration must be a mapping")

    return Stage8fConfig(
        sample_sizes=_values(values, "sample_sizes", int),
        strengths=_values(values, "strengths", float),
        replicates=int(values["replicates"]),
        batch_size=int(values["batch_size"]),
        master_seed=int(values["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("fixture", "n", "strength", "replicate")


def _n_batches(config: Stage8fConfig) -> int:
    return -(-config.replicates // config.batch_size)  # ceil division


def expected_combinations(config: Stage8fConfig) -> set[tuple[str, int, float, int]]:
    return {
        (fixture, n, strength, replicate)
        for fixture in FIXTURES
        for n in config.sample_sizes
        for strength in config.strengths
        for replicate in range(config.replicates)
    }


def expected_row_count(config: Stage8fConfig) -> int:
    return len(expected_combinations(config))


def _condition_seed(
    config: Stage8fConfig, fixture_index: int, sample_index: int, strength_index: int, replicate: int
) -> int:
    sequence = np.random.SeedSequence([config.master_seed, fixture_index, sample_index, strength_index, replicate])
    return int(sequence.generate_state(1)[0])


def _repository_root(config: Stage8fConfig) -> Path:
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


def _resolved_config(config: Stage8fConfig) -> dict[str, object]:
    return {
        "sample_sizes": list(config.sample_sizes),
        "strengths": list(config.strengths),
        "replicates": config.replicates,
        "batch_size": config.batch_size,
        "master_seed": config.master_seed,
    }


def _write_evidence(config: Stage8fConfig, output_dir: Path, raw: pd.DataFrame, runtime_seconds: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(_resolved_config(config), stream, sort_keys=True)

    repository_root = _repository_root(config)
    charter = repository_root / "docs/stage8f_charter.md"
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
    fixture: str, fixture_index: int, n: int, sample_index: int, strength: float, strength_index: int,
    replicate: int, alpha: float, config: Stage8fConfig,
) -> dict[str, object]:
    seed = _condition_seed(config, fixture_index, sample_index, strength_index, replicate)
    started = time.perf_counter()
    p_value = np.nan
    rejected = np.nan
    status, error = "ok", ""
    try:
        data = _sample_fixture(fixture, n, strength, np.random.default_rng(seed))
        conditioning = _FIXTURE_CONDITIONING[fixture]
        evidence = compute_partial_correlation_evidence(data, 0, 1, conditioning)
        p_value = float(evidence.p_value)
        rejected = bool(p_value <= alpha)
    except Exception as exc:  # raw evidence must retain pipeline failures
        status, error = "error", f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started

    return {
        "fixture": fixture, "n": n, "strength": strength, "alpha": alpha, "replicate": replicate,
        "seed": seed, "conditioning_size": len(_FIXTURE_CONDITIONING[fixture]),
        "p_value": p_value, "rejected": rejected, "elapsed_seconds": elapsed, "status": status, "error": error,
    }


def run_stage8f(
    config: Stage8fConfig,
    output_dir: Path,
    fixtures: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    strengths: tuple[float, ...] | None = None,
    batches: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`fixtures`/`sample_sizes`/`strengths`/`batches` restrict which
    cells run, for a single-cell CI shard -- replicate ranges are
    always derived from `config.batch_size` against the FULL replicate
    count, and seeds key off `FIXTURES.index(...)`/
    `config.sample_sizes.index(...)`/`config.strengths.index(...)`/
    `replicate` (all full-grid quantities), so a shard's results match
    an unsharded run's for the same replicates."""
    run_started = time.perf_counter()
    alpha_formula = select_form(fit_candidate_forms())
    target_fixtures = fixtures if fixtures is not None else FIXTURES
    target_sizes = sample_sizes if sample_sizes is not None else config.sample_sizes
    target_strengths = strengths if strengths is not None else config.strengths
    target_batches = batches if batches is not None else tuple(range(_n_batches(config)))

    rows: list[dict[str, object]] = []
    for fixture in target_fixtures:
        fixture_index = FIXTURES.index(fixture)
        for n in target_sizes:
            sample_index = config.sample_sizes.index(n)
            alpha = float(alpha_formula.predict(float(n)))
            for strength in target_strengths:
                strength_index = config.strengths.index(strength)
                for batch in target_batches:
                    start_replicate = batch * config.batch_size
                    end_replicate = min(start_replicate + config.batch_size, config.replicates)
                    for replicate in range(start_replicate, end_replicate):
                        rows.append(
                            _run_one_replicate(
                                fixture, fixture_index, n, sample_index, strength, strength_index,
                                replicate, alpha, config,
                            )
                        )

    raw = pd.DataFrame(rows)
    _write_evidence(config, output_dir, raw, time.perf_counter() - run_started)
    if write_report:
        from mintnet.experiments.stage8f_collider_diagnosis_reporting import write_report as write_stage8f_report

        write_stage8f_report(raw, config, output_dir)
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--fixtures", type=str, default=None,
        help="comma-separated subset of fixtures (e.g. step1,step2_collider; default: all)",
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None, help="comma-separated subset of N values (default: all)"
    )
    parser.add_argument(
        "--strengths", type=str, default=None, help="comma-separated subset of strength values (default: all)"
    )
    parser.add_argument(
        "--batches", type=str, default=None, help="comma-separated subset of batch indices (default: all)"
    )
    parser.add_argument("--no-report", action="store_true", help="skip the descriptive report (use for CI shards)")
    arguments = parser.parse_args()

    fixtures = tuple(arguments.fixtures.split(",")) if arguments.fixtures else None
    sample_sizes = tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    strengths = tuple(float(v) for v in arguments.strengths.split(",")) if arguments.strengths else None
    batches = tuple(int(v) for v in arguments.batches.split(",")) if arguments.batches else None

    run_stage8f(
        load_config(arguments.config), arguments.output,
        fixtures=fixtures, sample_sizes=sample_sizes, strengths=strengths, batches=batches,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
