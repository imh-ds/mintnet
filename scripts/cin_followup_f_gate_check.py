"""Validate provenance and apply the strict completion gate for F-only follow-up."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

import pandas as pd
import yaml

from mintnet.experiments.cin_baseline import (
    CASE_ORDER,
    PanelConfig,
    expected_identities,
    load_config,
)
from mintnet.experiments.cin_common import derive_seed_bundle, load_yaml, sha256_text_file


IDENTITY_COLUMNS = ("case", "phase", "replicate", "method")
EXPECTED_F_REPLICATES = 97
COMPLETION_THRESHOLD = 1.0
RUNNER_HOURS_ESTIMATE = 0.585
RUNNER_HOURS_CEILING = 1.25
WILSON_Z_95 = 1.959963984540054
PROJECT_ROOT = Path(__file__).resolve().parents[1]
D106_SEED_INVENTORY_FILES = (
    PROJECT_ROOT
    / "docs/cin_followup_audit/d106/reconstruction/historical/development/raw_metrics.csv",
    PROJECT_ROOT
    / "docs/cin_followup_audit/d106/reconstruction/historical/validation/raw_metrics.csv",
    PROJECT_ROOT / "docs/cin_followup_audit/d106/diagnostic_seed_inventory.csv",
)
F_FROZEN_SOURCE_FILES = (
    PROJECT_ROOT / "src/mintnet/cin/config.py",
    PROJECT_ROOT / "src/mintnet/cin/features.py",
    PROJECT_ROOT / "src/mintnet/cin/fit.py",
    PROJECT_ROOT / "src/mintnet/cin/ridge.py",
    PROJECT_ROOT / "src/mintnet/cin/result.py",
    PROJECT_ROOT / "src/mintnet/cin/scores.py",
    PROJECT_ROOT / "src/mintnet/cin/views.py",
    PROJECT_ROOT / "src/mintnet/experiments/cin_baseline.py",
    PROJECT_ROOT / "src/mintnet/experiments/cin_baseline_reporting.py",
    PROJECT_ROOT / "src/mintnet/experiments/cin_common.py",
    PROJECT_ROOT / "src/mintnet/simulation/cin_networks.py",
    PROJECT_ROOT / "scripts/cin_followup_f_gate_check.py",
    PROJECT_ROOT / "scripts/aggregate_shards.py",
    PROJECT_ROOT / "scripts/aggregate_cin_sidecars.py",
    PROJECT_ROOT / ".github/workflows/sharded_benchmark.yml",
    PROJECT_ROOT / "requirements-cin-followup-v1.txt",
)
SEED_COLUMNS = (
    "structure_seed",
    "sample_seed",
    "cin_fit_seed",
    "comparator_fit_seed",
    "stability_seed",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _seed_inventory_sha256(paths: tuple[Path, ...] = D106_SEED_INVENTORY_FILES) -> str:
    digest = hashlib.sha256()
    for path in paths:
        relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
        normalized_bytes = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(normalized_bytes).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _frozen_source_sha256(paths: tuple[Path, ...] = F_FROZEN_SOURCE_FILES) -> str:
    digest = hashlib.sha256()
    for path in paths:
        relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
        normalized = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(normalized).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _load_historical_seed_inventory() -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in D106_SEED_INVENTORY_FILES]
    return pd.concat(frames, ignore_index=True)


def _wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("validation denominator must be positive")
    z2 = WILSON_Z_95**2
    proportion = successes / total
    denominator = 1.0 + z2 / total
    center = (proportion + z2 / (2.0 * total)) / denominator
    half_width = (
        WILSON_Z_95
        * math.sqrt(proportion * (1.0 - proportion) / total + z2 / (4.0 * total**2))
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def _validate_protocol_config(config: PanelConfig) -> set[tuple[str, str, int, str]]:
    if config.cases != ("F",):
        raise ValueError("F follow-up config must contain only case F")
    if len(config.development_replicates) != 20:
        raise ValueError("F follow-up requires exactly 20 development identities")
    if len(config.validation_replicates) != EXPECTED_F_REPLICATES:
        raise ValueError("F follow-up requires exactly 97 validation identities")
    if config.n_overrides.get("F") != 150:
        raise ValueError("F follow-up sample size must be n=150")
    if config.f_max_tries not in {500, 1000, 2500}:
        raise ValueError("F follow-up generator cap must be one of 500, 1000, or 2500")
    if config.f_max_tries != 500:
        raise ValueError("F follow-up must use the development-selected 500-attempt cap")
    if not config.support_aware_inner_splits:
        raise ValueError("F follow-up must use the development-selected support-aware split")
    if config.stability_cases:
        raise ValueError("F follow-up excludes stability resampling")
    if (
        len(set(config.development_replicates)) != 20
        or len(set(config.validation_replicates)) != 97
    ):
        raise ValueError("F follow-up replicate identities must be unique")
    if set(config.development_replicates) & set(config.validation_replicates):
        raise ValueError("F follow-up development and validation identities overlap")
    if set(config.development_replicates) != set(range(2000, 2020)):
        raise ValueError("F follow-up development identities must be exactly 2000–2019")
    if set(config.validation_replicates) != set(range(3000, 3097)):
        raise ValueError("F follow-up validation identities must be exactly 3000–3096")
    if set(config.development_replicates) & set(range(0, 10)):
        raise ValueError("F follow-up development identities overlap D-106 development")
    if set(config.validation_replicates) & set(range(1000, 1020)):
        raise ValueError("F follow-up validation identities overlap D-106 validation/diagnostics")
    return expected_identities(config, phase="validation")


def validate_dispatch_preflight(
    config: PanelConfig,
    *,
    freeze_manifest: Mapping[str, Any],
    source_config_path: Path,
    code_revision: str,
    support_aware_inner_splits: bool | None = None,
) -> dict[str, Any]:
    """Verify the frozen F protocol and identity inventory before any shard runs."""
    _validate_protocol_config(config)
    if freeze_manifest.get("status") != "frozen":
        raise ValueError("dispatch freeze manifest status must be frozen")
    revision_pattern = r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}"
    if re.fullmatch(revision_pattern, code_revision) is None:
        raise ValueError("dispatch revision must be a full Git revision hash")
    frozen_revision = freeze_manifest.get("code_revision")
    if not isinstance(frozen_revision, str) or re.fullmatch(revision_pattern, frozen_revision) is None:
        raise ValueError("freeze manifest code_revision must be a full Git revision hash")

    source_hash = sha256_text_file(source_config_path)
    charter_hash = _sha256_file(config.charter_path)
    payload = load_yaml(source_config_path)
    if payload.get("protocol") != "cin-followup-f-v1":
        raise ValueError("dispatch config protocol must be cin-followup-f-v1")
    if support_aware_inner_splits is not None:
        payload["support_aware_inner_splits"] = support_aware_inner_splits
    resolved_bytes = yaml.safe_dump(
        payload,
        sort_keys=True,
        default_flow_style=False,
    ).encode("utf-8")
    resolved_hash = hashlib.sha256(resolved_bytes).hexdigest()
    frozen_values = {
        "source_config_sha256": source_hash,
        "config_sha256": resolved_hash,
        "charter_sha256": charter_hash,
        "seed_inventory_sha256": _seed_inventory_sha256(),
        "source_code_sha256": _frozen_source_sha256(),
        "f_max_tries": config.f_max_tries,
        "support_aware_inner_splits": (
            config.support_aware_inner_splits
            if support_aware_inner_splits is None
            else support_aware_inner_splits
        ),
        "runner_hours_estimate": RUNNER_HOURS_ESTIMATE,
        "runner_hours_ceiling": RUNNER_HOURS_CEILING,
    }
    for field, value in frozen_values.items():
        if freeze_manifest.get(field) != value:
            raise ValueError(f"dispatch freeze manifest {field} mismatch")
    return {
        "status": "dispatch_preflight_pass",
        "dispatch_revision": code_revision,
        "protocol_code_revision": frozen_revision,
        "f_max_tries": config.f_max_tries,
        "support_aware_inner_splits": frozen_values["support_aware_inner_splits"],
        "seed_inventory_sha256": frozen_values["seed_inventory_sha256"],
    }


def validate_f_seed_bundles(config: PanelConfig, historical: pd.DataFrame) -> dict[str, int]:
    """Reject exact five-seed bundle reuse against a historical raw inventory."""
    missing = set(SEED_COLUMNS) - set(historical.columns)
    if missing:
        raise ValueError(f"historical seed inventory is missing columns: {sorted(missing)}")
    if historical.loc[:, SEED_COLUMNS].isna().any().any():
        raise ValueError("historical seed inventory contains unavailable seed values")

    old_streams = {
        column: set(pd.to_numeric(historical[column], errors="raise").astype(int))
        for column in SEED_COLUMNS
    }
    proposed: dict[str, list[tuple[int, int, int, int, int]]] = {
        "development": [],
        "validation": [],
    }
    case_index = CASE_ORDER.index("F")
    for phase, phase_index, replicates in (
        ("development", 0, config.development_replicates),
        ("validation", 1, config.validation_replicates),
    ):
        for replicate in replicates:
            bundle = derive_seed_bundle(config.master_seed, case_index, phase_index, replicate)
            proposed[phase].append(
                (
                    bundle.structure,
                    bundle.sample,
                    bundle.cin_fit,
                    bundle.comparator_fit,
                    bundle.stability,
                )
            )
    combined = proposed["development"] + proposed["validation"]
    for index, column in enumerate(SEED_COLUMNS):
        proposed_stream = {bundle[index] for bundle in combined}
        if len(proposed_stream) != len(combined):
            raise ValueError(f"F follow-up {column} values collide across proposed identities")
        collisions = old_streams[column] & proposed_stream
        if collisions:
            raise ValueError(
                "F follow-up "
                f"{column} values collide with historical identities: {sorted(collisions)}"
            )
    return {phase: len(bundles) for phase, bundles in proposed.items()}


def _validate_provenance(
    config: PanelConfig,
    *,
    metadata: Mapping[str, Any],
    freeze_manifest: Mapping[str, Any],
    raw_metrics_path: Path,
    resolved_config_path: Path,
    source_config_path: Path,
) -> int:
    required = {
        "provenance_validated",
        "source_config_sha256",
        "config_sha256",
        "charter_sha256",
        "git_commit",
        "aggregated_raw_metrics_sha256",
    }
    missing = required - set(metadata)
    if missing:
        raise ValueError(f"aggregate provenance is missing fields: {sorted(missing)}")
    if metadata["provenance_validated"] is not True:
        raise ValueError("aggregate provenance was not validated")
    revision = metadata["git_commit"]
    revision_pattern = r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}"
    if not isinstance(revision, str) or re.fullmatch(revision_pattern, revision) is None:
        raise ValueError("aggregate git_commit must be a full Git revision hash")

    source_hash = sha256_text_file(source_config_path)
    resolved_hash = _sha256_file(resolved_config_path)
    resolved_payload = load_yaml(resolved_config_path)
    effective_cap_value = resolved_payload.get("f_max_tries", config.f_max_tries)
    if isinstance(effective_cap_value, bool) or not isinstance(effective_cap_value, int):
        raise ValueError("resolved config f_max_tries must be an integer")
    if effective_cap_value not in {500, 1000, 2500}:
        raise ValueError("resolved config has an unapproved F generator cap")
    raw_hash = _sha256_file(raw_metrics_path)
    charter_hash = config.charter_sha256
    if metadata["source_config_sha256"] != source_hash:
        raise ValueError("source config provenance hash mismatch")
    if metadata["config_sha256"] != resolved_hash:
        raise ValueError("resolved config provenance hash mismatch")
    if metadata["charter_sha256"] != charter_hash:
        raise ValueError("charter provenance hash mismatch")
    if metadata["aggregated_raw_metrics_sha256"] != raw_hash:
        raise ValueError("aggregated_raw_metrics_sha256 mismatch")

    frozen = {
        "source_config_sha256": source_hash,
        "config_sha256": resolved_hash,
        "charter_sha256": charter_hash,
        "seed_inventory_sha256": _seed_inventory_sha256(),
        "source_code_sha256": _frozen_source_sha256(),
        "f_max_tries": effective_cap_value,
        "support_aware_inner_splits": bool(
            resolved_payload.get("support_aware_inner_splits", False)
        ),
        "runner_hours_estimate": RUNNER_HOURS_ESTIMATE,
        "runner_hours_ceiling": RUNNER_HOURS_CEILING,
    }
    if freeze_manifest.get("status") != "frozen":
        raise ValueError("freeze manifest status must be frozen before validation can pass")
    revision_pattern = r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}"
    frozen_revision = freeze_manifest.get("code_revision")
    if not isinstance(frozen_revision, str) or re.fullmatch(revision_pattern, frozen_revision) is None:
        raise ValueError("freeze manifest code_revision must be a full Git revision hash")
    for field, value in frozen.items():
        if not freeze_manifest.get(field):
            raise ValueError(f"freeze manifest is missing {field}")
        if freeze_manifest[field] != value:
            raise ValueError(f"freeze manifest {field} does not match aggregate provenance")
    return effective_cap_value


def evaluate_f_validation(
    raw: pd.DataFrame,
    config: PanelConfig,
    *,
    metadata: Mapping[str, Any],
    freeze_manifest: Mapping[str, Any],
    raw_metrics_path: Path,
    resolved_config_path: Path,
    source_config_path: Path,
    require_candidate: bool = True,
) -> dict[str, Any]:
    """Validate a frozen F validation table and return its strict completion result."""
    expected = _validate_protocol_config(config)
    if load_yaml(source_config_path).get("protocol") != "cin-followup-f-v1":
        raise ValueError("validation source config protocol must be cin-followup-f-v1")
    validate_f_seed_bundles(config, _load_historical_seed_inventory())
    missing_columns = set(
        IDENTITY_COLUMNS
        + SEED_COLUMNS
        + (
            "status",
            "ap",
            "n_pairs_complete",
            "n_pairs_total",
            "n_failed_pairs",
            "generator_attempts",
            "error_type",
        )
    ) - set(raw)
    if missing_columns:
        raise ValueError(f"raw metrics are missing required columns: {sorted(missing_columns)}")

    keys = [
        (str(row[0]), str(row[1]), int(row[2]), str(row[3]))
        for row in raw.loc[:, IDENTITY_COLUMNS].itertuples(index=False, name=None)
    ]
    if len(set(keys)) != len(keys):
        raise ValueError("raw metrics contain duplicate validation identity keys")
    actual = set(keys)
    if actual != expected:
        missing = sorted(expected - actual)
        foreign = sorted(actual - expected)
        raise ValueError(
            f"raw validation identity grid mismatch; missing={missing}, foreign={foreign}"
        )
    if len(raw) != EXPECTED_F_REPLICATES:
        raise ValueError("raw validation identity count does not equal 97")

    resolved_payload = load_yaml(resolved_config_path)
    if require_candidate and resolved_payload.get("support_aware_inner_splits") is not True:
        raise ValueError("candidate validation must use the frozen support-aware split")

    expected_seeds = {
        replicate: derive_seed_bundle(config.master_seed, CASE_ORDER.index("F"), 1, replicate)
        for replicate in config.validation_replicates
    }
    for row in raw.loc[:, ("replicate", *SEED_COLUMNS)].itertuples(index=False, name=None):
        replicate = int(row[0])
        expected_bundle = expected_seeds[replicate]
        expected_values = (
            expected_bundle.structure,
            expected_bundle.sample,
            expected_bundle.cin_fit,
            expected_bundle.comparator_fit,
            expected_bundle.stability,
        )
        try:
            numeric_values = tuple(float(value) for value in row[1:])
            if any(not math.isfinite(value) or not value.is_integer() for value in numeric_values):
                raise ValueError("seed values must be finite integers")
            observed_values = tuple(int(value) for value in numeric_values)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"validation seed bundle is invalid for replicate {replicate}"
            ) from exc
        if observed_values != expected_values:
            raise ValueError(f"validation seed bundle mismatch for replicate {replicate}")

    effective_cap = _validate_provenance(
        config,
        metadata=metadata,
        freeze_manifest=freeze_manifest,
        raw_metrics_path=raw_metrics_path,
        resolved_config_path=resolved_config_path,
        source_config_path=source_config_path,
    )

    statuses = raw["status"].astype(str)
    allowed = {"complete", "incomplete", "error"}
    if not set(statuses) <= allowed:
        raise ValueError(f"raw metrics contain unknown statuses: {sorted(set(statuses) - allowed)}")
    ap = pd.to_numeric(raw["ap"], errors="coerce")
    pair_complete = pd.to_numeric(raw["n_pairs_complete"], errors="coerce")
    pair_total = pd.to_numeric(raw["n_pairs_total"], errors="coerce")
    complete_rows = statuses.eq("complete")
    incomplete_rows = statuses.eq("incomplete")
    error_rows = statuses.eq("error")
    generator_attempts = pd.to_numeric(raw["generator_attempts"], errors="coerce")

    if (complete_rows & ((pair_total != 28) | (pair_complete != 28) | ~np_isfinite(ap))).any():
        raise ValueError("complete F rows must have 28/28 pairs and finite AP")
    generated_rows = complete_rows | incomplete_rows
    if (
        generated_rows
        & (
            ~np_isfinite(generator_attempts)
            | (generator_attempts < 1)
            | (generator_attempts.mod(1) != 0)
        )
    ).any():
        raise ValueError("generated F rows must retain a positive integer generator attempt count")
    fit_error_rows = error_rows & pair_total.eq(28)
    if (
        fit_error_rows
        & (
            ~np_isfinite(generator_attempts)
            | (generator_attempts < 1)
            | (generator_attempts.mod(1) != 0)
        )
    ).any():
        raise ValueError("F fit-error rows must retain a positive integer generator attempt count")
    acceptance_errors = error_rows & raw["error_type"].astype(str).eq("GeneratorAcceptanceError")
    if (
        acceptance_errors
        & (generator_attempts != effective_cap)
    ).any():
        raise ValueError(
            "generator acceptance errors must retain the configured exhausted attempt cap"
        )
    invalid_incomplete = (
        (pair_total != 28)
        | (pair_complete < 0)
        | (pair_complete >= 28)
        | ~np_isfinite(pair_complete)
        | np_isfinite(ap)
    )
    if (incomplete_rows & invalid_incomplete).any():
        raise ValueError("incomplete F rows must retain failed pairs and unavailable AP")
    if (error_rows & np_isfinite(ap)).any():
        raise ValueError("error rows must have unavailable AP")
    failed = pd.to_numeric(raw["n_failed_pairs"], errors="coerce")
    if (complete_rows & (failed != 0)).any() or (
        incomplete_rows & (failed != 28 - pair_complete)
    ).any():
        raise ValueError("pair failure counts are inconsistent with pair completion")

    n_complete = int(complete_rows.sum())
    low, high = _wilson_interval(n_complete, EXPECTED_F_REPLICATES)
    status_counts = {
        name: int(statuses.eq(name).sum())
        for name in ("complete", "incomplete", "error")
    }
    return {
        "protocol": "cin-followup-f-v1",
        "case": "F",
        "phase": "validation",
        "method": "cin",
        "status": "pass" if n_complete / EXPECTED_F_REPLICATES >= COMPLETION_THRESHOLD else "fail",
        "completion_threshold": COMPLETION_THRESHOLD,
        "f_max_tries": effective_cap,
        "n_expected": EXPECTED_F_REPLICATES,
        "n_complete": n_complete,
        "completion_rate": n_complete / EXPECTED_F_REPLICATES,
        "status_counts": status_counts,
        "wilson_95": {"lower": low, "upper": high, "half_width": (high - low) / 2.0},
        "git_commit": metadata["git_commit"],
        "source_config_sha256": metadata["source_config_sha256"],
        "charter_sha256": metadata["charter_sha256"],
    }


def paired_completion_comparison(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    config: PanelConfig,
) -> dict[str, Any]:
    """Compare baseline/candidate completion on the same frozen validation keys."""
    expected = _validate_protocol_config(config)
    required = set(IDENTITY_COLUMNS + SEED_COLUMNS + ("status",))
    for label, raw in (("baseline", baseline), ("candidate", candidate)):
        missing = required - set(raw)
        if missing:
            raise ValueError(f"{label} raw metrics are missing columns: {sorted(missing)}")
        keys = [
            (str(row[0]), str(row[1]), int(row[2]), str(row[3]))
            for row in raw.loc[:, IDENTITY_COLUMNS].itertuples(index=False, name=None)
        ]
        actual = set(keys)
        if len(keys) != len(actual) or actual != expected:
            raise ValueError(f"{label} validation identity grid mismatch")

    baseline_indexed = baseline.set_index(list(IDENTITY_COLUMNS)).sort_index()
    candidate_indexed = candidate.set_index(list(IDENTITY_COLUMNS)).sort_index()
    if not baseline_indexed.loc[:, SEED_COLUMNS].equals(candidate_indexed.loc[:, SEED_COLUMNS]):
        raise ValueError("baseline and candidate deterministic seed bundles differ")
    allowed = {"complete", "incomplete", "error"}
    baseline_status = baseline_indexed["status"].astype(str)
    candidate_status = candidate_indexed["status"].astype(str)
    if not set(baseline_status) <= allowed or not set(candidate_status) <= allowed:
        raise ValueError("baseline or candidate contains an unknown completion status")

    paired_status_counts = {
        f"{left}->{right}": int(((baseline_status == left) & (candidate_status == right)).sum())
        for left in ("complete", "incomplete", "error")
        for right in ("complete", "incomplete", "error")
    }
    baseline_complete = baseline_status.eq("complete")
    candidate_complete = candidate_status.eq("complete")
    return {
        "n_expected": len(expected),
        "baseline_complete": int(baseline_complete.sum()),
        "candidate_complete": int(candidate_complete.sum()),
        "baseline_completion_rate": float(baseline_complete.mean()),
        "candidate_completion_rate": float(candidate_complete.mean()),
        "candidate_improvements": int((~baseline_complete & candidate_complete).sum()),
        "candidate_regressions": int((baseline_complete & ~candidate_complete).sum()),
        "paired_status_counts": paired_status_counts,
    }


def np_isfinite(values: pd.Series) -> pd.Series:
    return values.map(lambda value: pd.notna(value) and math.isfinite(float(value)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--freeze-manifest", type=Path)
    parser.add_argument("--code-revision")
    parser.add_argument("--support-aware-inner-splits", choices=("true", "false"))
    parser.add_argument("--baseline-raw", type=Path)
    parser.add_argument("--baseline-metadata", type=Path)
    parser.add_argument("--baseline-freeze-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    seed_counts = validate_f_seed_bundles(config, _load_historical_seed_inventory())
    seed_inventory_hash = _seed_inventory_sha256()
    if args.preflight_only:
        if args.freeze_manifest is None:
            parser.error("--freeze-manifest is required with --preflight-only")
        revision = args.code_revision
        if revision is None:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        support_override = (
            None
            if args.support_aware_inner_splits is None
            else args.support_aware_inner_splits == "true"
        )
        result = validate_dispatch_preflight(
            config,
            freeze_manifest=json.loads(args.freeze_manifest.read_text(encoding="utf-8")),
            source_config_path=args.config,
            code_revision=revision,
            support_aware_inner_splits=support_override,
        )
        print(
            json.dumps(
                {
                    **result,
                    "seed_bundle_counts": seed_counts,
                    "seed_inventory_sha256": seed_inventory_hash,
                },
                sort_keys=True,
            )
        )
        return 0
    required_paths = (args.raw, args.metadata, args.freeze_manifest, args.output)
    if any(path is None for path in required_paths):
        parser.error("--raw, --metadata, --freeze-manifest, and --output are required")
    result = evaluate_f_validation(
        pd.read_csv(args.raw),
        config,
        metadata=json.loads(args.metadata.read_text(encoding="utf-8")),
        freeze_manifest=json.loads(args.freeze_manifest.read_text(encoding="utf-8")),
        raw_metrics_path=args.raw,
        resolved_config_path=args.raw.parent / "resolved_config.yaml",
        source_config_path=args.config,
    )
    baseline_args = (
        args.baseline_raw,
        args.baseline_metadata,
        args.baseline_freeze_manifest,
    )
    if any(value is not None for value in baseline_args):
        if any(value is None for value in baseline_args):
            parser.error(
                "--baseline-raw, --baseline-metadata, and "
                "--baseline-freeze-manifest must be supplied together"
            )
        baseline_raw = pd.read_csv(args.baseline_raw)
        baseline_result = evaluate_f_validation(
            baseline_raw,
            config,
            metadata=json.loads(args.baseline_metadata.read_text(encoding="utf-8")),
            freeze_manifest=json.loads(
                args.baseline_freeze_manifest.read_text(encoding="utf-8")
            ),
            raw_metrics_path=args.baseline_raw,
            resolved_config_path=args.baseline_raw.parent / "resolved_config.yaml",
            source_config_path=args.config,
            require_candidate=False,
        )
        result["baseline_gate"] = baseline_result
        result["paired_completion"] = paired_completion_comparison(
            baseline_raw,
            pd.read_csv(args.raw),
            config,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
