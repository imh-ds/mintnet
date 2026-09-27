"""Generic aggregator for any sharded experiment run. See
.github/workflows/sharded_benchmark.yml -- that workflow and this
script work on any runner module that opts into the shard-aggregation
contract. Its first user, the retired Stage 5a runner, is preserved under
`archive/mi_native_search/` as a historical example.

Contract a shardable module must expose:
    - `load_config(path) -> Config`
    - `expected_row_count(config) -> int`
    - `expected_combinations(config) -> set[tuple]`
    - `COMBINATION_COLUMNS: tuple[str, ...]`
plus a `<module>_reporting` companion module exposing
`write_report(raw, config, output_dir)`.

Each shard is one runner invocation restricted to a subset of cells
(`--no-report`, since a partial run's report would be misleading) that
wrote its own `raw_metrics.csv`. This script concatenates every shard's
raw metrics, verifies full coverage (every expected combination present
exactly once, no shard missing or duplicated), and only then calls the
module's own report writer -- producing the same report an unsharded
run would, since a well-behaved shardable runner derives its seeds from
the *full* grid's index, not the shard's own subset. The archived Stage 5a
runner and its integration test demonstrate that historical contract;
active CIN runners must prove the same property independently.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pandas as pd


def _load_module(module_path: str) -> tuple[ModuleType, ModuleType]:
    runner = importlib.import_module(module_path)
    reporting = importlib.import_module(f"{module_path}_reporting")
    return runner, reporting


def aggregate(
    module_path: str,
    config_path: Path,
    shards_dir: Path,
    output_dir: Path,
    *,
    phase: str | None = None,
) -> pd.DataFrame:
    runner, reporting = _load_module(module_path)
    config = runner.load_config(config_path)

    shard_paths = sorted(shards_dir.glob("*/raw_metrics.csv"))
    if not shard_paths:
        raise SystemExit(f"no raw_metrics.csv files found under {shards_dir}")

    raw = pd.concat((pd.read_csv(path) for path in shard_paths), ignore_index=True)

    expected_identities = getattr(runner, "expected_identities", None)
    if phase is not None:
        if phase not in {"development", "validation"}:
            raise SystemExit(f"unknown aggregation phase: {phase}")
        if not callable(expected_identities):
            raise SystemExit(f"runner {module_path} does not support phase aggregation")
        if "phase" not in raw.columns:
            raise SystemExit("phase aggregation requires a phase column")
        observed_phases = set(raw["phase"].dropna().astype(str))
        if observed_phases != {phase}:
            raise SystemExit(
                f"phase aggregation requested {phase}, but shards contain phases {sorted(observed_phases)}"
            )

    phase_row_count = getattr(runner, "expected_row_count_for_phase", None)
    expected_rows = (
        phase_row_count(config, phase)
        if phase is not None and callable(phase_row_count)
        else runner.expected_row_count(config)
    )
    if len(raw) != expected_rows:
        raise SystemExit(
            f"aggregated {len(raw)} rows from {len(shard_paths)} shard(s), expected {expected_rows} "
            "-- a shard is missing or duplicated"
        )

    if callable(expected_identities):
        expected = expected_identities(config, phase=phase)
        identity_columns = ["case", "phase", "replicate", "method"]
        missing_columns = set(identity_columns) - set(raw.columns)
        if missing_columns:
            raise SystemExit(f"raw metrics are missing identity columns: {sorted(missing_columns)}")
        try:
            replicate_values = pd.to_numeric(raw["replicate"], errors="raise")
            if not replicate_values.mod(1).eq(0).all():
                raise ValueError("non-integral replicate")
            actual = {
                (str(row.case), str(row.phase), int(row.replicate), str(row.method))
                for row in raw.assign(replicate=replicate_values).itertuples(index=False)
            }
        except (TypeError, ValueError, OverflowError) as exc:
            raise SystemExit(f"raw metrics contain invalid identities: {exc}") from exc
        duplicate_keys = raw.duplicated(subset=identity_columns)
        if duplicate_keys.any():
            raise SystemExit(f"{int(duplicate_keys.sum())} duplicate rows across shards (key: {identity_columns})")
        if len(raw) != len(actual) or actual != expected:
            missing = expected - actual
            foreign = actual - expected
            raise SystemExit(
                f"aggregated identities do not match the requested grid; missing: {sorted(missing)}, "
                f"foreign: {sorted(foreign)}"
            )
    else:
        combination_columns = list(runner.COMBINATION_COLUMNS)
        combos = set(raw[combination_columns].itertuples(index=False, name=None))
        expected_combos = runner.expected_combinations(config)
        if combos != expected_combos:
            missing = expected_combos - combos
            raise SystemExit(f"aggregated shards do not cover every combination -- missing: {missing}")
        dedup_columns = combination_columns + (["replicate"] if "replicate" in raw.columns else [])
        duplicate_keys = raw.duplicated(subset=dedup_columns)
        if duplicate_keys.any():
            raise SystemExit(f"{int(duplicate_keys.sum())} duplicate rows across shards (key: {dedup_columns})")

    target = Path(output_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{target.name}.aggregate-", dir=target.parent) as temporary:
        staging = Path(temporary) / "artifact"
        staging.mkdir()
        if {"pair_sidecar_file", "stability_sidecar_file"} & set(raw.columns):
            from scripts.aggregate_cin_sidecars import aggregate_sidecars

            aggregate_sidecars(shards_dir, staging, phase=phase)
        raw.to_csv(staging / "raw_metrics.csv", index=False)
        expected_charter_sha256 = getattr(config, "charter_sha256", None)
        if expected_charter_sha256 is None and getattr(config, "charter_path", None):
            charter_bytes = Path(config.charter_path).read_bytes().replace(b"\r\n", b"\n")
            expected_charter_sha256 = hashlib.sha256(charter_bytes).hexdigest()
        _write_provenance(
            shard_paths,
            staging,
            expected_source_config_sha256=_sha256_file(config_path),
            expected_charter_sha256=expected_charter_sha256,
        )
        reporting.write_report(raw, config, staging)
        backup = Path(temporary) / "previous-output"
        if target.exists():
            os.replace(target, backup)
        try:
            os.replace(staging, target)
        except OSError:
            if backup.exists():
                os.replace(backup, target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    return raw


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_provenance(
    shard_paths: list[Path],
    output_dir: Path,
    *,
    expected_source_config_sha256: str | None = None,
    expected_charter_sha256: str | None = None,
) -> None:
    """Validate shard identity, then preserve each shard's environment evidence."""
    shard_dirs = sorted({path.parent for path in shard_paths})
    if not shard_dirs:
        raise ValueError("cannot aggregate provenance without shard directories")

    invariant_fields = (
        "config_sha256", "source_config_sha256", "charter_sha256", "git_commit"
    )
    required_fields = (
        "config", *invariant_fields, "python", "platform", "package_versions",
        "thread_settings", "cpu", "runtime_seconds", "peak_rss_mb",
    )
    reference: dict[str, object] | None = None
    reference_resolved: bytes | None = None
    shard_records: list[dict[str, object]] = []

    for shard_dir in shard_dirs:
        metadata_path = shard_dir / "metadata.json"
        resolved_path = shard_dir / "resolved_config.yaml"
        if not metadata_path.is_file():
            raise FileNotFoundError(f"missing metadata.json in shard {shard_dir}")
        if not resolved_path.is_file():
            raise FileNotFoundError(f"missing resolved_config.yaml in shard {shard_dir}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError(f"metadata.json in {shard_dir} must contain an object")
        missing = set(required_fields) - set(metadata)
        if missing:
            raise ValueError(f"metadata.json in {shard_dir} is missing fields: {sorted(missing)}")
        for field in invariant_fields:
            if metadata[field] is None or str(metadata[field]).strip() == "":
                raise ValueError(f"metadata field {field} is unavailable in {shard_dir}")
        if not isinstance(metadata["package_versions"], dict):
            raise ValueError(f"package_versions must be an object in {shard_dir}")
        thread_settings = metadata["thread_settings"]
        if not isinstance(thread_settings, dict) or not {"environment", "threadpool_info"} <= set(thread_settings):
            raise ValueError(f"thread_settings is incomplete in {shard_dir}")
        try:
            runtime = float(metadata["runtime_seconds"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"runtime_seconds is invalid in {shard_dir}") from exc
        if not math.isfinite(runtime) or runtime < 0:
            raise ValueError(f"runtime_seconds is invalid in {shard_dir}")

        resolved_bytes = resolved_path.read_bytes()
        resolved_hash = hashlib.sha256(resolved_bytes).hexdigest()
        if metadata["config_sha256"] != resolved_hash:
            raise ValueError(f"config_sha256 does not match resolved_config.yaml in {shard_dir}")
        if expected_source_config_sha256 and metadata["source_config_sha256"] != expected_source_config_sha256:
            raise ValueError(f"source_config_sha256 does not match requested config in {shard_dir}")
        if expected_charter_sha256 and metadata["charter_sha256"] != expected_charter_sha256:
            raise ValueError(f"charter_sha256 does not match requested charter in {shard_dir}")
        if reference is None:
            reference = metadata
            reference_resolved = resolved_bytes
        else:
            for field in invariant_fields:
                if metadata[field] != reference[field]:
                    raise ValueError(f"mixed shard provenance: {field} differs in {shard_dir}")
            if resolved_bytes != reference_resolved:
                raise ValueError(f"mixed shard provenance: resolved_config.yaml differs in {shard_dir}")

        raw_path = shard_dir / "raw_metrics.csv"
        shard_raw = pd.read_csv(raw_path)
        if "charter_sha256" in shard_raw.columns:
            if shard_raw["charter_sha256"].isna().any() or set(
                shard_raw["charter_sha256"].astype(str)
            ) != {str(metadata["charter_sha256"])}:
                raise ValueError(f"raw charter provenance does not match metadata in {shard_dir}")
        shard_records.append({
            "shard": shard_dir.name,
            **{field: metadata[field] for field in required_fields},
        })

    assert reference is not None and reference_resolved is not None
    (output_dir / "resolved_config.yaml").write_bytes(reference_resolved)
    runtimes = [float(record["runtime_seconds"]) for record in shard_records]
    rss_values = [
        float(record["peak_rss_mb"])
        for record in shard_records
        if record["peak_rss_mb"] is not None and pd.notna(record["peak_rss_mb"])
    ]
    environment_fields = ("python", "platform", "package_versions", "thread_settings", "cpu")
    environment_summary: dict[str, object] = {}
    for field in environment_fields:
        values = {json.dumps(record[field], sort_keys=True) for record in shard_records}
        environment_summary[field] = json.loads(next(iter(values))) if len(values) == 1 else "varies by shard"
    environment_summary["peak_rss_mb_max"] = max(rss_values) if rss_values else None
    environment_summary["peak_rss_mb_contributing_shards"] = len(rss_values)
    raw_metrics_path = output_dir / "raw_metrics.csv"
    if not raw_metrics_path.is_file():
        raise FileNotFoundError("aggregated raw_metrics.csv must be staged before provenance")
    aggregated_metadata = {
        "config_sha256": reference["config_sha256"],
        "source_config_sha256": reference["source_config_sha256"],
        "charter_sha256": reference["charter_sha256"],
        "git_commit": reference["git_commit"],
        "provenance_validated": True,
        "aggregated_raw_metrics_sha256": _sha256_file(raw_metrics_path),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "total_runtime_seconds": sum(runtimes),
        "max_shard_runtime_seconds": max(runtimes),
        "shard_count": len(shard_records),
        "shards": shard_records,
        "environment_summary": environment_summary,
        "note": (
            "Per-shard provenance and environments are retained in shards. "
            "total_runtime_seconds sums shard runtimes and is not wall-clock duration."
        ),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(aggregated_metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module", required=True,
        help="import path of the shardable runner module, e.g. mintnet.experiments.cin_baseline",
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--shards-dir", required=True, type=Path,
        help="directory containing one subdirectory per shard, each with its own raw_metrics.csv",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--phase", choices=("development", "validation"),
        help="aggregate exactly one CIN panel phase (unsupported for other runner modules)",
    )
    arguments = parser.parse_args()
    aggregate(
        arguments.module, arguments.config, arguments.shards_dir, arguments.output,
        phase=arguments.phase,
    )


if __name__ == "__main__":
    main()
