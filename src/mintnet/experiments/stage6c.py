"""Deterministic raw-evidence runner for the frozen Stage 6c null-
calibration study. See docs/stage6c_charter.md.

Three independent stages, run and inspected in sequence (Stage B needs
Stage A's own selected `k_CMI`; Stage C needs Stage B's own selected
`k_perm`) -- not a single blind pipeline, matching the charter's own
"only after identifying a reasonably calibrated configuration" order.
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

from mintnet.experiments.stage6b import CONDITIONS as _STAGE6B_CONDITIONS
from mintnet.mi.cmiknn import estimate_cmiknn, local_permutation_test

_STAGE_TAG_A = 6031
_STAGE_TAG_B = 6032
_STAGE_TAG_C = 6033

# Null conditions (true I(X;Y|Z) = 0 by construction), reused unchanged
# from Stage 6b's own CONDITIONS registry.
NULL_CONDITIONS: tuple[dict[str, object], ...] = tuple(
    c for c in _STAGE6B_CONDITIONS if str(c["label"]).endswith("_null")
)
ALT_CONDITIONS: tuple[dict[str, object], ...] = tuple(
    c for c in _STAGE6B_CONDITIONS if str(c["label"]).endswith("_alt")
)

K_PERM_LABELS: tuple[str, ...] = ("kperm3", "kperm5", "kperm10", "kperm20", "adaptive")


def resolve_k_perm(label: str, n: int) -> int:
    if label == "kperm3":
        return 3
    if label == "kperm5":
        return 5
    if label == "kperm10":
        return 10
    if label == "kperm20":
        return 20
    if label == "adaptive":
        return int(min(20, max(3, round(0.05 * n))))
    raise ValueError(f"unknown k_perm label: {label}")


def _seed(master_seed: int, tag: int, *ints: int) -> int:
    sequence = np.random.SeedSequence([master_seed, tag, *ints])
    return int(sequence.generate_state(1)[0])


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


def _write_evidence(
    output_dir: Path, raw: pd.DataFrame, resolved_config: dict[str, object], runtime_seconds: float, source_path: Path | None
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    with (output_dir / "resolved_config.yaml").open("w", encoding="utf-8") as stream:
        yaml.safe_dump(resolved_config, stream, sort_keys=True)

    repository_root = _repository_root(source_path)
    charter = repository_root / "docs/stage6c_charter.md"
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


# ---------------------------------------------------------------------------
# Stage A: k_CMI sensitivity (point estimate only, no permutation test)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageAConfig:
    k_cmi_values: tuple[int, ...]
    sample_sizes: tuple[int, ...]
    replicates: int
    master_seed: int
    source_path: Path | None = None


def _run_stage_a_cell(task: tuple[int, dict, int, int, StageAConfig]) -> list[dict[str, object]]:
    k_cmi, condition, condition_index, n, config = task
    label = condition["label"]
    s = int(condition["s"])
    sample: Callable = condition["sample"]  # type: ignore[assignment]
    x_col = int(condition["x"])
    y_col = int(condition["y"])
    z_cols = condition["z"]  # type: ignore[assignment]

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _seed(config.master_seed, _STAGE_TAG_A, k_cmi, condition_index, n, replicate)
        rng = np.random.default_rng(seed)
        row: dict[str, object] = {
            "stage": "A", "k_cmi": k_cmi, "label": label, "s": s, "n": n, "replicate": replicate,
            "seed": seed, "status": "ok", "error": "", "estimate": np.nan,
        }
        try:
            data = sample(n, rng)
            x = data[:, x_col]
            y = data[:, y_col]
            z = data[:, list(z_cols)] if z_cols else None
            row["estimate"] = estimate_cmiknn(x, y, z, k=k_cmi)
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


def run_stage_a(config: StageAConfig, output_dir: Path, max_workers: int | None = None) -> pd.DataFrame:
    import os
    from concurrent.futures import ProcessPoolExecutor

    started = time.perf_counter()
    tasks = [
        (k_cmi, condition, condition_index, n, config)
        for k_cmi in config.k_cmi_values
        for condition_index, condition in enumerate(NULL_CONDITIONS)
        for n in config.sample_sizes
    ]
    if max_workers is None:
        max_workers = min(len(tasks), max(1, (os.cpu_count() or 1) - 1))

    rows: list[dict[str, object]] = []
    if max_workers > 1 and len(tasks) > 1:
        from concurrent.futures import ProcessPoolExecutor as PPE

        with PPE(max_workers=max_workers) as executor:
            for cell_rows in executor.map(_run_stage_a_cell, tasks):
                rows.extend(cell_rows)
    else:
        for task in tasks:
            rows.extend(_run_stage_a_cell(task))

    raw = pd.DataFrame(rows)
    resolved = {
        "k_cmi_values": list(config.k_cmi_values),
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "master_seed": config.master_seed,
    }
    _write_evidence(output_dir, raw, resolved, time.perf_counter() - started, config.source_path)
    return raw


# ---------------------------------------------------------------------------
# Stage B: k_perm null calibration (the primary study)
# ---------------------------------------------------------------------------


_STAGE_B_COLUMNS = (
    "stage", "k_perm_label", "k_perm_resolved", "k_cmi", "label", "s", "n",
    "replicate", "seed", "status", "error", "estimate", "p_value",
)


@dataclass(frozen=True)
class StageBConfig:
    k_cmi: int
    k_perm_labels: tuple[str, ...]
    sample_sizes: tuple[int, ...]
    replicates: int
    permutations: int
    alphas: tuple[float, ...]
    master_seed: int
    source_path: Path | None = None


def _run_stage_b_cell(task: tuple[str, dict, int, int, StageBConfig]) -> list[dict[str, object]]:
    k_perm_label, condition, condition_index, n, config = task
    label = condition["label"]
    s = int(condition["s"])
    sample: Callable = condition["sample"]  # type: ignore[assignment]
    x_col = int(condition["x"])
    y_col = int(condition["y"])
    z_cols = condition["z"]  # type: ignore[assignment]
    k_perm = resolve_k_perm(k_perm_label, n)
    # K_PERM_LABELS.index(...), NOT Python's built-in hash() -- str
    # hashing is randomized per-process (PYTHONHASHSEED) unless fixed,
    # which would make seeds differ across worker processes/CI shards
    # for the exact same cell, breaking the sharding contract's own
    # "a shard's seeds are bit-identical to what an unsharded run would
    # draw" requirement (see scripts/aggregate_shards.py's docstring).
    k_perm_index = K_PERM_LABELS.index(k_perm_label)

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _seed(config.master_seed, _STAGE_TAG_B, k_perm_index, condition_index, n, replicate)
        rng = np.random.default_rng(seed)
        row: dict[str, object] = {
            "stage": "B", "k_perm_label": k_perm_label, "k_perm_resolved": k_perm, "k_cmi": config.k_cmi,
            "label": label, "s": s, "n": n, "replicate": replicate, "seed": seed,
            "status": "ok", "error": "", "estimate": np.nan, "p_value": np.nan,
        }
        try:
            data = sample(n, rng)
            x = data[:, x_col]
            y = data[:, y_col]
            z = data[:, list(z_cols)] if z_cols else None
            result = local_permutation_test(
                x, y, z, k=config.k_cmi, k_perm=k_perm, permutations=config.permutations, rng=rng
            )
            row["estimate"] = result.statistic
            row["p_value"] = result.p_value
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


def _all_stage_b_tasks(config: StageBConfig) -> list[tuple[str, dict, int, int, StageBConfig]]:
    """Every (k_perm_label, condition, n) cell derived from the FULL
    grid (config.k_perm_labels x NULL_CONDITIONS x config.sample_sizes),
    not any shard's own filtered subset -- required so seeds (which key
    off condition_index, n, and K_PERM_LABELS.index(...), all full-grid
    quantities) are bit-identical between a sharded and unsharded run."""
    tasks: list[tuple[str, dict, int, int, StageBConfig]] = []
    for condition_index, condition in enumerate(NULL_CONDITIONS):
        s = int(condition["s"])
        labels = ("kperm5",) if s == 0 else config.k_perm_labels  # |S|=0: global permutation, k_perm irrelevant
        for label in labels:
            for n in config.sample_sizes:
                tasks.append((label, condition, condition_index, n, config))
    return tasks


def run_stage_b(
    config: StageBConfig,
    output_dir: Path,
    max_workers: int | None = None,
    k_perm_labels: tuple[str, ...] | None = None,
    labels: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`k_perm_labels`/`labels`/`sample_sizes` restrict which cells
    actually run, for a single-cell CI shard -- task selection is
    always filtered down from `_all_stage_b_tasks`'s own full-grid
    list, never regenerated from the filtered subset, so a shard's
    seeds match what an unsharded run would draw for that same cell.
    A shard combination that has no matching cell at all (e.g. |S|=0
    crossed with any `k_perm_label` other than `kperm5`, since |S|=0
    doesn't use `k_perm`) legitimately produces zero rows rather than
    raising -- the generic sharding workflow dispatches the full cross
    product of every dimension, and not every combination is valid."""
    import os
    from concurrent.futures import ProcessPoolExecutor

    started = time.perf_counter()
    target_k_perm = set(k_perm_labels) if k_perm_labels is not None else None
    target_labels = set(labels) if labels is not None else None
    target_sizes = set(sample_sizes) if sample_sizes is not None else None

    tasks = [
        task
        for task in _all_stage_b_tasks(config)
        if (target_k_perm is None or task[0] in target_k_perm)
        and (target_labels is None or str(task[1]["label"]) in target_labels)
        and (target_sizes is None or task[3] in target_sizes)
    ]

    rows: list[dict[str, object]] = []
    if tasks:
        if max_workers is None:
            max_workers = min(len(tasks), max(1, (os.cpu_count() or 1) - 1))
        if max_workers > 1 and len(tasks) > 1:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                for cell_rows in executor.map(_run_stage_b_cell, tasks):
                    rows.extend(cell_rows)
        else:
            for task in tasks:
                rows.extend(_run_stage_b_cell(task))

    raw = pd.DataFrame(rows, columns=_STAGE_B_COLUMNS) if not rows else pd.DataFrame(rows)
    resolved = {
        "k_cmi": config.k_cmi,
        "k_perm_labels": list(config.k_perm_labels),
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "permutations": config.permutations,
        "alphas": list(config.alphas),
        "master_seed": config.master_seed,
    }
    _write_evidence(output_dir, raw, resolved, time.perf_counter() - started, config.source_path)
    if not write_report:
        return raw
    from mintnet.experiments.stage6c_reporting import write_stage_b_report

    write_stage_b_report(raw, config, output_dir)
    return raw


# ---------------------------------------------------------------------------
# Stage C: power at the calibrated setting (contingent on Stage B)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageCConfig:
    k_cmi: int
    k_perm_label: str
    sample_sizes: tuple[int, ...]
    replicates: int
    permutations: int
    alphas: tuple[float, ...]
    master_seed: int
    source_path: Path | None = None


def _run_stage_c_cell(task: tuple[dict, int, int, StageCConfig]) -> list[dict[str, object]]:
    condition, condition_index, n, config = task
    label = condition["label"]
    s = int(condition["s"])
    sample: Callable = condition["sample"]  # type: ignore[assignment]
    x_col = int(condition["x"])
    y_col = int(condition["y"])
    z_cols = condition["z"]  # type: ignore[assignment]
    k_perm = resolve_k_perm(config.k_perm_label, n)

    rows: list[dict[str, object]] = []
    for replicate in range(config.replicates):
        seed = _seed(config.master_seed, _STAGE_TAG_C, condition_index, n, replicate)
        rng = np.random.default_rng(seed)
        row: dict[str, object] = {
            "stage": "C", "k_perm_label": config.k_perm_label, "k_perm_resolved": k_perm, "k_cmi": config.k_cmi,
            "label": label, "s": s, "n": n, "replicate": replicate, "seed": seed,
            "status": "ok", "error": "", "estimate": np.nan, "p_value": np.nan,
        }
        try:
            data = sample(n, rng)
            x = data[:, x_col]
            y = data[:, y_col]
            z = data[:, list(z_cols)] if z_cols else None
            result = local_permutation_test(
                x, y, z, k=config.k_cmi, k_perm=k_perm, permutations=config.permutations, rng=rng
            )
            row["estimate"] = result.statistic
            row["p_value"] = result.p_value
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    return rows


_STAGE_C_COLUMNS = (
    "stage", "k_perm_label", "k_perm_resolved", "k_cmi", "label", "s", "n",
    "replicate", "seed", "status", "error", "estimate", "p_value",
)


def run_stage_c(
    config: StageCConfig,
    output_dir: Path,
    max_workers: int | None = None,
    labels: tuple[str, ...] | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    """`labels`/`sample_sizes` restrict which cells run, for a
    single-cell CI shard -- task selection is filtered down from the
    full (ALT_CONDITIONS x config.sample_sizes) grid, never regenerated
    from the filtered subset, so a shard's seeds match what an
    unsharded run would draw for that same cell (seeds already key off
    `condition_index`/`n`/`replicate`, all full-grid quantities)."""
    import os
    from concurrent.futures import ProcessPoolExecutor

    started = time.perf_counter()
    target_labels = set(labels) if labels is not None else None
    target_sizes = set(sample_sizes) if sample_sizes is not None else None

    tasks = [
        (condition, condition_index, n, config)
        for condition_index, condition in enumerate(ALT_CONDITIONS)
        for n in config.sample_sizes
        if (target_labels is None or str(condition["label"]) in target_labels)
        and (target_sizes is None or n in target_sizes)
    ]

    rows: list[dict[str, object]] = []
    if tasks:
        if max_workers is None:
            max_workers = min(len(tasks), max(1, (os.cpu_count() or 1) - 1))
        if max_workers > 1 and len(tasks) > 1:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                for cell_rows in executor.map(_run_stage_c_cell, tasks):
                    rows.extend(cell_rows)
        else:
            for task in tasks:
                rows.extend(_run_stage_c_cell(task))

    raw = pd.DataFrame(rows, columns=_STAGE_C_COLUMNS) if not rows else pd.DataFrame(rows)
    resolved = {
        "k_cmi": config.k_cmi,
        "k_perm_label": config.k_perm_label,
        "sample_sizes": list(config.sample_sizes),
        "replicates": config.replicates,
        "permutations": config.permutations,
        "alphas": list(config.alphas),
        "master_seed": config.master_seed,
    }
    _write_evidence(output_dir, raw, resolved, time.perf_counter() - started, config.source_path)
    if not write_report:
        return raw
    from mintnet.experiments.stage6c_reporting import write_stage_c_report

    write_stage_c_report(raw, config, output_dir)
    return raw


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError("Stage 6c configuration must be a mapping")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=["a", "b", "c"])
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    arguments = parser.parse_args()

    values = _load_yaml(arguments.config)

    if arguments.stage == "a":
        block = values["stage_a"]
        config_a = StageAConfig(
            k_cmi_values=tuple(int(v) for v in block["k_cmi_values"]),
            sample_sizes=tuple(int(v) for v in block["sample_sizes"]),
            replicates=int(block["replicates"]),
            master_seed=int(block["master_seed"]),
            source_path=arguments.config.resolve(),
        )
        raw = run_stage_a(config_a, arguments.output, max_workers=arguments.workers)
        from mintnet.experiments.stage6c_reporting import write_stage_a_report

        write_stage_a_report(raw, config_a, arguments.output)
    elif arguments.stage == "b":
        block = values["stage_b"]
        config_b = StageBConfig(
            k_cmi=int(block["k_cmi"]),
            k_perm_labels=tuple(str(v) for v in block["k_perm_labels"]),
            sample_sizes=tuple(int(v) for v in block["sample_sizes"]),
            replicates=int(block["replicates"]),
            permutations=int(block["permutations"]),
            alphas=tuple(float(v) for v in block["alphas"]),
            master_seed=int(block["master_seed"]),
            source_path=arguments.config.resolve(),
        )
        raw = run_stage_b(config_b, arguments.output, max_workers=arguments.workers)
        from mintnet.experiments.stage6c_reporting import write_stage_b_report

        write_stage_b_report(raw, config_b, arguments.output)
    else:
        block = values["stage_c"]
        config_c = StageCConfig(
            k_cmi=int(block["k_cmi"]),
            k_perm_label=str(block["k_perm_label"]),
            sample_sizes=tuple(int(v) for v in block["sample_sizes"]),
            replicates=int(block["replicates"]),
            permutations=int(block["permutations"]),
            alphas=tuple(float(v) for v in block["alphas"]),
            master_seed=int(block["master_seed"]),
            source_path=arguments.config.resolve(),
        )
        raw = run_stage_c(config_c, arguments.output, max_workers=arguments.workers)
        from mintnet.experiments.stage6c_reporting import write_stage_c_report

        write_stage_c_report(raw, config_c, arguments.output)


if __name__ == "__main__":
    main()
