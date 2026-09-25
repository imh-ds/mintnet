"""Deterministic, shardable CIN cost-pilot runner."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import pandas as pd  # noqa: E402

from mintnet.cin import CINConfig, fit_network  # noqa: E402
from mintnet.simulation import generate_cost_input  # noqa: E402

from .cin_common import (  # noqa: E402
    IncrementalCsvWriter,
    derive_seed_bundle,
    load_yaml,
    peak_rss_mb,
    sha256_file,
    thread_limits,
    write_gzip_frame,
    write_provenance,
    write_resolved_config,
)


@dataclass(frozen=True)
class CostCell:
    cell_id: str
    kind: str
    p: int
    n: int


@dataclass(frozen=True)
class CostConfig:
    cells: tuple[CostCell, ...]
    repeats: tuple[int, ...]
    master_seed: int
    source_path: Path
    charter_path: Path


COMBINATION_COLUMNS = ("cell", "repeat")
COST_RAW_COLUMNS = (
    "cell", "repeat", "kind", "p", "n", "status", "error_type", "error",
    "structure_seed", "sample_seed", "cin_fit_seed", "elapsed_seconds",
    "prepare_seconds", "features_seconds", "gram_factor_seconds", "h_seconds",
    "omission_seconds", "score_seconds", "aggregate_seconds", "outputs_seconds",
    "n_large_factorizations", "q", "t", "n_fallbacks", "fallback_fraction",
    "n_requested_omissions", "n_pairs_complete", "n_pairs_total", "peak_rss_mb",
    "pair_sidecar_file", "requested_directional_outer_fits", "status_histogram_json",
    "variance_floor_hit_rate", "probability_clipped_fraction", "probability_min",
    "zero_sum_fallbacks", "tuned_penalty_min_fraction", "tuned_penalty_max_fraction",
    "tuned_penalty_histogram_json", "first_scaled_normal_residual", "environment_json",
    "charter_sha256",
)
MANIFEST_COLUMNS = ("file", "cell", "repeat", "method", "kind", "n_rows", "sha256")


def load_config(path: Path) -> CostConfig:
    source = Path(path)
    payload = load_yaml(source)
    raw_cells = payload.get("cells")
    if not isinstance(raw_cells, list) or not raw_cells:
        raise ValueError("cost configuration requires non-empty cells")
    cells: list[CostCell] = []
    seen: set[str] = set()
    for raw in raw_cells:
        if not isinstance(raw, dict):
            raise ValueError("each cost cell must be a mapping")
        cell_id = str(raw.get("id", ""))
        kind = str(raw.get("kind", ""))
        if not cell_id or cell_id in seen:
            raise ValueError(f"duplicate or empty cost cell id: {cell_id!r}")
        if kind not in {"dense_continuous", "categorical5", "categorical10", "mixed"}:
            raise ValueError(f"unsupported cost input kind: {kind}")
        p = int(raw.get("p", 0))
        n = int(raw.get("n", 0))
        if p < 1 or n < 1:
            raise ValueError(f"cost cell dimensions must be positive: {cell_id}")
        cells.append(CostCell(cell_id, kind, p, n))
        seen.add(cell_id)
    repeats = tuple(int(value) for value in payload.get("repeats", ()))
    if not repeats or any(value < 1 for value in repeats):
        raise ValueError("cost configuration requires positive repeats")
    master_seed = int(payload.get("master_seed", -1))
    if master_seed < 0:
        raise ValueError("master_seed must be nonnegative")
    charter_value = str(payload.get("charter", "docs/cin_cost_charter.md"))
    charter_path = (source.parent.parent / charter_value).resolve()
    return CostConfig(tuple(cells), repeats, master_seed, source.resolve(), charter_path)


def expected_row_count(config: CostConfig) -> int:
    return len(config.cells) * len(config.repeats)


def expected_combinations(config: CostConfig) -> set[tuple[str, int]]:
    return {(cell.cell_id, repeat) for cell in config.cells for repeat in config.repeats}


def _write_manifest_row(output_dir: Path, row: dict[str, Any]) -> None:
    path = output_dir / "sidecar_manifest.csv"
    prior = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=MANIFEST_COLUMNS)
    updated = pd.concat([prior, pd.DataFrame([row])], ignore_index=True)
    updated.to_csv(path, index=False, lineterminator="\n")


def _empty_row(cell: CostCell, repeat: int, seeds: Any) -> dict[str, Any]:
    row = {column: None for column in COST_RAW_COLUMNS}
    row.update({
        "cell": cell.cell_id, "repeat": repeat, "kind": cell.kind, "p": cell.p, "n": cell.n,
        "structure_seed": seeds.structure, "sample_seed": seeds.sample, "cin_fit_seed": seeds.cin_fit,
        "n_pairs_total": cell.p * (cell.p - 1) // 2,
    })
    return row


def _phase_seconds(cost: dict[str, Any], *names: str) -> float | None:
    values = cost.get("phase_seconds", {})
    if not isinstance(values, dict):
        return None
    selected = [float(values[name]) for name in names if name in values]
    return sum(selected) if selected else None


def _run_cell(config: CostConfig, output_dir: Path, cell: CostCell, repeat: int, cell_index: int) -> dict[str, Any]:
    seeds = derive_seed_bundle(config.master_seed, cell_index, 0, repeat)
    row = _empty_row(cell, repeat, seeds)
    started = time.perf_counter()
    try:
        frame, schema = generate_cost_input(cell.kind, cell.p, cell.n, seed=seeds.sample)
        fit_config = CINConfig(seed=seeds.cin_fit)
        with thread_limits():
            fit = fit_network(frame, schema, fit_config)
        cost = fit.metadata.get("cost", {})
        pairs = fit.pairs.copy()
        sidecar_name = f"{cell.cell_id}_{repeat}_cin_pairs.csv.gz"
        sidecar_path = output_dir / "sidecars" / sidecar_name
        outputs_started = time.perf_counter()
        n_rows = write_gzip_frame(pairs, sidecar_path)
        _write_manifest_row(output_dir, {
            "file": sidecar_name, "cell": cell.cell_id, "repeat": repeat,
            "method": "cin", "kind": "pairs", "n_rows": n_rows,
            "sha256": sha256_file(sidecar_path),
        })
        cost.setdefault("phase_seconds", {})["outputs"] = time.perf_counter() - outputs_started
        elapsed = time.perf_counter() - started
        complete = int((pairs["status"] == "complete").sum()) if "status" in pairs else 0
        total = len(pairs)
        factor_count = int(cost.get("n_large_factorizations", 0) or 0)
        fallback_count = int(cost.get("n_fallbacks", 0) or 0)
        requested_omissions = int(cost.get("n_requested_omissions", 0) or 0)
        status_counts = pairs["status"].value_counts().sort_index().to_dict()
        penalty_histogram = cost.get("tuned_penalty_histogram", {})
        probability_floor = cost.get("probability_floor", {})
        environment = {
            "dependencies": fit.metadata.get("dependencies", {}),
            "thread_environment": {
                name: os.environ.get(name)
                for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
            },
        }
        row.update({
            "status": "complete" if bool(fit.metadata.get("complete", False)) else "incomplete",
            "elapsed_seconds": elapsed,
            "prepare_seconds": _phase_seconds(cost, "prepare"),
            "features_seconds": _phase_seconds(cost, "features", "tuning"),
            "gram_factor_seconds": _phase_seconds(cost, "gram_factor", "factorization"),
            "h_seconds": _phase_seconds(cost, "h", "H"),
            "omission_seconds": _phase_seconds(cost, "omission"),
            "score_seconds": _phase_seconds(cost, "score", "scoring"),
            "aggregate_seconds": _phase_seconds(cost, "aggregate"),
            "outputs_seconds": _phase_seconds(cost, "outputs"),
            "n_large_factorizations": factor_count, "q": cost.get("q"), "t": cost.get("t"),
            "n_fallbacks": fallback_count,
            "fallback_fraction": fallback_count / requested_omissions if requested_omissions else 0.0,
            "n_requested_omissions": requested_omissions,
            "n_pairs_complete": complete, "n_pairs_total": total,
            "peak_rss_mb": peak_rss_mb(), "pair_sidecar_file": sidecar_name,
            "requested_directional_outer_fits": cost.get("requested_directional_outer_fits"),
            "status_histogram_json": json.dumps(status_counts, sort_keys=True, separators=(",", ":")),
            "variance_floor_hit_rate": cost.get("variance_floor_hit_rate"),
            "probability_clipped_fraction": probability_floor.get("clipped_fraction"),
            "probability_min": probability_floor.get("min_probability"),
            "zero_sum_fallbacks": probability_floor.get("zero_sum_fallbacks"),
            "tuned_penalty_min_fraction": penalty_histogram.get("min_fraction"),
            "tuned_penalty_max_fraction": penalty_histogram.get("max_fraction"),
            "tuned_penalty_histogram_json": json.dumps(penalty_histogram, sort_keys=True, separators=(",", ":")),
            "first_scaled_normal_residual": cost.get("first_scaled_normal_residual"),
            "environment_json": json.dumps(environment, sort_keys=True, separators=(",", ":")),
            "charter_sha256": sha256_file(config.charter_path),
        })
    except Exception as exc:  # noqa: BLE001 - failure rows are part of the contract.
        row.update({
            "status": "error", "error_type": type(exc).__name__, "error": str(exc),
            "elapsed_seconds": time.perf_counter() - started, "n_pairs_complete": 0,
            "pair_sidecar_file": None, "peak_rss_mb": peak_rss_mb(),
        })
    return row


def run_cost(
    config: CostConfig,
    output_dir: Path,
    *,
    cells: tuple[str, ...] | None = None,
    repeats: tuple[int, ...] | None = None,
    workers: int = 1,
    write_report: bool = True,
) -> pd.DataFrame:
    """Run selected full-grid cells while preserving shard-local identity."""

    if workers != 1:
        raise ValueError("CIN runners currently require --workers 1")
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "sidecars").mkdir(parents=True, exist_ok=True)
    if not config.charter_path.is_file():
        raise ValueError(f"cost charter does not exist: {config.charter_path}")
    full_payload = load_yaml(config.source_path)
    write_resolved_config(target, full_payload)
    selected_cells = set(cells) if cells is not None else {cell.cell_id for cell in config.cells}
    selected_repeats = set(repeats) if repeats is not None else set(config.repeats)
    unknown_cells = selected_cells - {cell.cell_id for cell in config.cells}
    unknown_repeats = selected_repeats - set(config.repeats)
    if unknown_cells:
        raise ValueError(f"unknown cost cells: {sorted(unknown_cells)}")
    if unknown_repeats:
        raise ValueError(f"unknown cost repeats: {sorted(unknown_repeats)}")
    rows: list[dict[str, Any]] = []
    writer = IncrementalCsvWriter(target / "raw_metrics.csv", COST_RAW_COLUMNS)
    started = time.perf_counter()
    try:
        for cell_index, cell in enumerate(config.cells):
            if cell.cell_id not in selected_cells:
                continue
            for repeat in config.repeats:
                if repeat not in selected_repeats:
                    continue
                row = _run_cell(config, target, cell, repeat, cell_index)
                writer.append(row)
                rows.append(row)
    finally:
        writer.close()
    write_provenance(
        target, config_payload=full_payload, source_path=config.source_path,
        charter_path=config.charter_path,
        runtime_seconds=time.perf_counter() - started, peak_rss_mb=peak_rss_mb(),
    )
    raw = pd.DataFrame(rows, columns=COST_RAW_COLUMNS)
    if write_report:
        from . import cin_cost_reporting

        cin_cost_reporting.write_report(raw, config, target)
    return raw


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cells", type=_parse_csv)
    parser.add_argument("--repeat", type=int, action="append")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    run_cost(
        load_config(args.config), args.output, cells=args.cells,
        repeats=tuple(args.repeat) if args.repeat else None,
        workers=args.workers, write_report=not args.no_report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMBINATION_COLUMNS", "COST_RAW_COLUMNS", "CostCell", "CostConfig",
    "expected_combinations", "expected_row_count", "load_config", "run_cost",
]
