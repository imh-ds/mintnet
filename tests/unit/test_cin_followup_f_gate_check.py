from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
import pytest
import yaml

from mintnet.experiments.cin_baseline import CASE_ORDER, expected_identities, load_config
from mintnet.experiments.cin_common import derive_seed_bundle, sha256_text_file
import scripts.cin_followup_f_gate_check as gate_check
from scripts.cin_followup_f_gate_check import (
    RUNNER_HOURS_CEILING,
    RUNNER_HOURS_ESTIMATE,
    _frozen_source_sha256,
    _seed_inventory_sha256,
    evaluate_f_validation,
    paired_completion_comparison,
    validate_dispatch_preflight,
    validate_f_seed_bundles,
)


ROOT = Path(__file__).resolve().parents[2]
FOLLOWUP_CONFIG = ROOT / "configs" / "cin_followup_v1.yaml"


def _f_rows(*, incomplete: int | None = None, error: int | None = None) -> pd.DataFrame:
    config = load_config(FOLLOWUP_CONFIG)
    rows: list[dict[str, object]] = []
    for case, phase, replicate, method in sorted(expected_identities(config, phase="validation")):
        seeds = derive_seed_bundle(config.master_seed, CASE_ORDER.index("F"), 1, replicate)
        status = "complete"
        n_complete = n_total = 28
        ap: float | None = 0.5
        if replicate == incomplete:
            status, n_complete, ap = "incomplete", 21, None
        elif replicate == error:
            status, n_complete, n_total, ap = "error", 0, 0, None
        rows.append({
            "case": case,
            "phase": phase,
            "replicate": replicate,
            "method": method,
            "structure_seed": seeds.structure,
            "sample_seed": seeds.sample,
            "cin_fit_seed": seeds.cin_fit,
            "comparator_fit_seed": seeds.comparator_fit,
            "stability_seed": seeds.stability,
            "status": status,
            "ap": ap,
            "n_pairs_complete": n_complete,
            "n_pairs_total": n_total,
            "n_failed_pairs": n_total - n_complete,
            "generator_attempts": 500 if status == "error" else 47,
            "error_type": "GeneratorAcceptanceError" if status == "error" else None,
            "error": "simulated generator rejection" if status == "error" else None,
            "pair_sidecar_file": (
                None if status == "error" else f"F_validation_{replicate}_cin_pairs.csv.gz"
            ),
        })
    return pd.DataFrame(rows)


def _provenance(
    tmp_path: Path,
    raw: pd.DataFrame,
    *,
    effective_max_tries: int | None = None,
    support_aware_inner_splits: bool | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    config = load_config(FOLLOWUP_CONFIG)
    raw_path = tmp_path / "raw_metrics.csv"
    raw.to_csv(raw_path, index=False)
    resolved_config = tmp_path / "resolved_config.yaml"
    resolved_payload = yaml.safe_load(FOLLOWUP_CONFIG.read_text(encoding="utf-8"))
    if effective_max_tries is not None:
        resolved_payload["f_max_tries"] = effective_max_tries
    if support_aware_inner_splits is not None:
        resolved_payload["support_aware_inner_splits"] = support_aware_inner_splits
    resolved_config.write_text(yaml.safe_dump(resolved_payload), encoding="utf-8")
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    code_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    metadata = {
        "provenance_validated": True,
        "source_config_sha256": sha256_text_file(FOLLOWUP_CONFIG),
        "config_sha256": sha(resolved_config),
        "charter_sha256": config.charter_sha256,
        "git_commit": code_revision,
        "aggregated_raw_metrics_sha256": sha(raw_path),
    }
    freeze = {
        "status": "frozen",
        "code_revision": code_revision,
        "source_config_sha256": sha256_text_file(FOLLOWUP_CONFIG),
        "config_sha256": sha(resolved_config),
        "charter_sha256": config.charter_sha256,
        "seed_inventory_sha256": _seed_inventory_sha256(),
        "f_max_tries": resolved_payload.get("f_max_tries", config.f_max_tries),
        "support_aware_inner_splits": resolved_payload.get(
            "support_aware_inner_splits", False
        ),
        "source_code_sha256": _frozen_source_sha256(),
        "runner_hours_estimate": RUNNER_HOURS_ESTIMATE,
        "runner_hours_ceiling": RUNNER_HOURS_CEILING,
    }
    return metadata, freeze


def test_all_expected_f_validation_identities_pass_strict_completion_gate(tmp_path: Path) -> None:
    raw = _f_rows()
    metadata, freeze = _provenance(tmp_path, raw)

    result = evaluate_f_validation(
        raw,
        load_config(FOLLOWUP_CONFIG),
        metadata=metadata,
        freeze_manifest=freeze,
        raw_metrics_path=tmp_path / "raw_metrics.csv",
        resolved_config_path=tmp_path / "resolved_config.yaml",
        source_config_path=FOLLOWUP_CONFIG,
    )

    assert result["status"] == "pass"
    assert result["n_expected"] == 97
    assert result["n_complete"] == 97
    assert result["completion_rate"] == 1.0
    assert result["wilson_95"]["lower"] < 1.0


def test_baseline_validation_accepts_frozen_false_split_manifest(tmp_path: Path) -> None:
    raw = _f_rows()
    metadata, freeze = _provenance(
        tmp_path,
        raw,
        support_aware_inner_splits=False,
    )

    result = evaluate_f_validation(
        raw,
        load_config(FOLLOWUP_CONFIG),
        metadata=metadata,
        freeze_manifest=freeze,
        raw_metrics_path=tmp_path / "raw_metrics.csv",
        resolved_config_path=tmp_path / "resolved_config.yaml",
        source_config_path=FOLLOWUP_CONFIG,
        require_candidate=False,
    )

    assert result["status"] == "pass"
    assert result["n_complete"] == 97


def test_validation_accepts_docs_only_dispatch_revision_with_frozen_code_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _f_rows()
    metadata, freeze = _provenance(tmp_path, raw)
    freeze["code_revision"] = "a" * 40
    freeze["source_code_sha256"] = "b" * 64
    metadata["git_commit"] = "c" * 40
    monkeypatch.setattr(gate_check, "_frozen_source_sha256", lambda: "d" * 64)
    monkeypatch.setattr(
        gate_check,
        "_frozen_source_sha256_at_revision",
        lambda revision: "b" * 64,
        raising=False,
    )

    result = evaluate_f_validation(
        raw,
        load_config(FOLLOWUP_CONFIG),
        metadata=metadata,
        freeze_manifest=freeze,
        raw_metrics_path=tmp_path / "raw_metrics.csv",
        resolved_config_path=tmp_path / "resolved_config.yaml",
        source_config_path=FOLLOWUP_CONFIG,
    )

    assert result["status"] == "pass"
    assert result["git_commit"] == "c" * 40


@pytest.mark.parametrize("failure_kind", ["incomplete", "error"])
def test_any_noncomplete_identity_fails_without_leaving_denominator(
    tmp_path: Path, failure_kind: str
) -> None:
    failure_id = 3000
    raw = _f_rows(
        incomplete=failure_id if failure_kind == "incomplete" else None,
        error=failure_id if failure_kind == "error" else None,
    )
    metadata, freeze = _provenance(tmp_path, raw)

    result = evaluate_f_validation(
        raw,
        load_config(FOLLOWUP_CONFIG),
        metadata=metadata,
        freeze_manifest=freeze,
        raw_metrics_path=tmp_path / "raw_metrics.csv",
        resolved_config_path=tmp_path / "resolved_config.yaml",
        source_config_path=FOLLOWUP_CONFIG,
    )

    assert result["status"] == "fail"
    assert result["n_expected"] == 97
    assert result["n_complete"] == 96
    assert result["completion_rate"] == 96 / 97
    assert result["status_counts"][failure_kind] == 1


def test_gate_uses_effective_attempt_cap_from_resolved_config(tmp_path: Path) -> None:
    raw = _f_rows(error=3000)
    raw.loc[raw["replicate"] == 3000, "generator_attempts"] = 1000
    metadata, freeze = _provenance(tmp_path, raw, effective_max_tries=1000)

    result = evaluate_f_validation(
        raw,
        load_config(FOLLOWUP_CONFIG),
        metadata=metadata,
        freeze_manifest=freeze,
        raw_metrics_path=tmp_path / "raw_metrics.csv",
        resolved_config_path=tmp_path / "resolved_config.yaml",
        source_config_path=FOLLOWUP_CONFIG,
    )

    assert result["f_max_tries"] == 1000
    assert result["status"] == "fail"


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "foreign", "mixed_phase"])
def test_gate_rejects_identity_grid_corruption(tmp_path: Path, mutation: str) -> None:
    raw = _f_rows()
    if mutation == "missing":
        raw = raw.iloc[1:].copy()
    elif mutation == "duplicate":
        raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    elif mutation == "foreign":
        raw.loc[0, "replicate"] = 9999
    else:
        raw.loc[0, "phase"] = "development"
    metadata, freeze = _provenance(tmp_path, raw)

    with pytest.raises(ValueError, match="identity"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


def test_gate_rejects_identity_with_a_different_deterministic_seed_bundle(tmp_path: Path) -> None:
    raw = _f_rows()
    raw.loc[raw["replicate"] == 3000, "sample_seed"] += 1
    metadata, freeze = _provenance(tmp_path, raw)

    with pytest.raises(ValueError, match="seed bundle mismatch"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


def test_gate_rejects_missing_generator_attempt_count(tmp_path: Path) -> None:
    raw = _f_rows()
    raw.loc[raw["replicate"] == 3000, "generator_attempts"] = None
    metadata, freeze = _provenance(tmp_path, raw)

    with pytest.raises(ValueError, match="attempt count"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


def test_gate_requires_attempt_count_on_fit_error_rows(tmp_path: Path) -> None:
    raw = _f_rows(error=3000)
    mask = raw["replicate"] == 3000
    raw.loc[mask, "n_pairs_total"] = 28
    raw.loc[mask, "n_failed_pairs"] = 28
    raw.loc[mask, "generator_attempts"] = None
    metadata, freeze = _provenance(tmp_path, raw)

    with pytest.raises(ValueError, match="fit-error rows"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


def test_paired_completion_comparison_keeps_identity_pairing_and_failed_rows() -> None:
    baseline = _f_rows(incomplete=3000)
    candidate = _f_rows()

    result = paired_completion_comparison(
        baseline,
        candidate,
        load_config(FOLLOWUP_CONFIG),
    )

    assert result["n_expected"] == 97
    assert result["baseline_complete"] == 96
    assert result["candidate_complete"] == 97
    assert result["candidate_improvements"] == 1
    assert result["candidate_regressions"] == 0
    assert result["paired_status_counts"]["incomplete->complete"] == 1


def test_paired_completion_comparison_rejects_changed_identity_or_seed() -> None:
    baseline = _f_rows()
    candidate = _f_rows()
    candidate.loc[candidate["replicate"] == 3000, "cin_fit_seed"] += 1

    with pytest.raises(ValueError, match="seed bundles differ"):
        paired_completion_comparison(baseline, candidate, load_config(FOLLOWUP_CONFIG))


def test_protocol_rejects_nonapproved_identity_ranges() -> None:
    config = load_config(FOLLOWUP_CONFIG)
    wrong_ids = replace(config, validation_replicates=(3097, *config.validation_replicates[1:]))

    with pytest.raises(ValueError, match="identities must be exactly"):
        evaluate_f_validation(
            _f_rows(),
            wrong_ids,
            metadata={},
            freeze_manifest={},
            raw_metrics_path=Path("unused"),
            resolved_config_path=Path("unused"),
            source_config_path=FOLLOWUP_CONFIG,
        )


def test_seed_bundles_are_fresh_against_d106_inventory() -> None:
    config = load_config(FOLLOWUP_CONFIG)
    historical = pd.concat(
        [
            pd.read_csv(
                ROOT
                / "docs/cin_followup_audit/d106/reconstruction/historical/development/raw_metrics.csv"
            ),
            pd.read_csv(
                ROOT
                / "docs/cin_followup_audit/d106/reconstruction/historical/validation/raw_metrics.csv"
            ),
        ],
        ignore_index=True,
    )

    assert validate_f_seed_bundles(config, historical) == {"development": 20, "validation": 97}


def test_seed_bundles_reject_historical_collision() -> None:
    config = load_config(FOLLOWUP_CONFIG)
    historical = pd.DataFrame(
        [{
            "structure_seed": 1,
            "sample_seed": 2,
            "cin_fit_seed": 3,
            "comparator_fit_seed": 4,
            "stability_seed": 5,
        }]
    )
    seed = derive_seed_bundle(config.master_seed, CASE_ORDER.index("F"), 0, 2000)
    historical.loc[0] = [
        seed.structure,
        seed.sample,
        seed.cin_fit,
        seed.comparator_fit,
        seed.stability,
    ]
    with pytest.raises(ValueError, match="collide with historical"):
        validate_f_seed_bundles(config, historical)


def test_seed_stream_rejects_component_collision_even_if_bundle_differs() -> None:
    config = load_config(FOLLOWUP_CONFIG)
    seed = derive_seed_bundle(config.master_seed, CASE_ORDER.index("F"), 0, 2000)
    historical = pd.DataFrame(
        [{
            "structure_seed": seed.structure,
            "sample_seed": 2,
            "cin_fit_seed": 3,
            "comparator_fit_seed": 4,
            "stability_seed": 5,
        }]
    )

    with pytest.raises(ValueError, match="structure_seed values collide"):
        validate_f_seed_bundles(config, historical)


@pytest.mark.parametrize(
    "field",
    [
        "source_config_sha256",
        "config_sha256",
        "charter_sha256",
        "seed_inventory_sha256",
        "source_code_sha256",
        "code_revision",
        "f_max_tries",
        "support_aware_inner_splits",
        "runner_hours_estimate",
        "runner_hours_ceiling",
    ],
)
def test_gate_rejects_changed_frozen_protocol_provenance(
    tmp_path: Path, field: str
) -> None:
    raw = _f_rows()
    metadata, freeze = _provenance(tmp_path, raw)
    freeze[field] = "changed"

    with pytest.raises(ValueError, match="freeze|provenance|revision"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


def test_gate_rejects_a_draft_freeze_manifest(tmp_path: Path) -> None:
    raw = _f_rows()
    metadata, freeze = _provenance(tmp_path, raw)
    freeze["status"] = "draft"

    with pytest.raises(ValueError, match="status must be frozen"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("support_aware_inner_splits", False, "support-aware split"),
        ("f_max_tries", 1000, "500-attempt cap"),
    ],
)
def test_gate_rejects_a_nonselected_development_candidate(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    config = replace(load_config(FOLLOWUP_CONFIG), **{field: value})

    with pytest.raises(ValueError, match=message):
        evaluate_f_validation(
            _f_rows(),
            config,
            metadata={},
            freeze_manifest={},
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


@pytest.mark.parametrize("support_aware", [True, False])
def test_dispatch_preflight_checks_frozen_candidate_and_baseline_hashes(
    support_aware: bool,
) -> None:
    config = load_config(FOLLOWUP_CONFIG)
    source_payload = yaml.safe_load(FOLLOWUP_CONFIG.read_text(encoding="utf-8"))
    source_sha = sha256_text_file(FOLLOWUP_CONFIG)
    resolved_payload = dict(source_payload)
    resolved_payload["support_aware_inner_splits"] = support_aware
    resolved_bytes = yaml.safe_dump(
        resolved_payload, sort_keys=True, default_flow_style=False
    ).encode("utf-8")
    revision = "b" * 40
    freeze = {
        "status": "frozen",
        "source_config_sha256": source_sha,
        "config_sha256": hashlib.sha256(resolved_bytes).hexdigest(),
        "charter_sha256": config.charter_sha256,
        "seed_inventory_sha256": _seed_inventory_sha256(),
        "code_revision": revision,
        "f_max_tries": 500,
        "support_aware_inner_splits": support_aware,
        "source_code_sha256": _frozen_source_sha256(),
        "runner_hours_estimate": RUNNER_HOURS_ESTIMATE,
        "runner_hours_ceiling": RUNNER_HOURS_CEILING,
    }

    result = validate_dispatch_preflight(
        config,
        freeze_manifest=freeze,
        source_config_path=FOLLOWUP_CONFIG,
        code_revision=revision,
        support_aware_inner_splits=support_aware,
    )

    assert result["status"] == "dispatch_preflight_pass"
    assert result["support_aware_inner_splits"] is support_aware


def test_dispatch_preflight_rejects_changed_revision_or_draft_manifest() -> None:
    config = load_config(FOLLOWUP_CONFIG)
    source_payload = yaml.safe_load(FOLLOWUP_CONFIG.read_text(encoding="utf-8"))
    resolved_bytes = yaml.safe_dump(
        source_payload, sort_keys=True, default_flow_style=False
    ).encode("utf-8")
    revision = "c" * 40
    freeze = {
        "status": "frozen",
        "source_config_sha256": sha256_text_file(FOLLOWUP_CONFIG),
        "config_sha256": hashlib.sha256(resolved_bytes).hexdigest(),
        "charter_sha256": config.charter_sha256,
        "seed_inventory_sha256": _seed_inventory_sha256(),
        "code_revision": revision,
        "f_max_tries": 500,
        "support_aware_inner_splits": True,
        "source_code_sha256": _frozen_source_sha256(),
        "runner_hours_estimate": RUNNER_HOURS_ESTIMATE,
        "runner_hours_ceiling": RUNNER_HOURS_CEILING,
    }

    with pytest.raises(ValueError, match="dispatch revision must"):
        validate_dispatch_preflight(
            config,
            freeze_manifest=freeze,
            source_config_path=FOLLOWUP_CONFIG,
            code_revision="not-a-revision",
        )
    freeze["status"] = "draft"
    with pytest.raises(ValueError, match="status must be frozen"):
        validate_dispatch_preflight(
            config,
            freeze_manifest=freeze,
            source_config_path=FOLLOWUP_CONFIG,
            code_revision=revision,
        )


def test_gate_rejects_modified_raw_config_or_unavailable_metrics(tmp_path: Path) -> None:
    raw = _f_rows()
    metadata, freeze = _provenance(tmp_path, raw)
    (tmp_path / "raw_metrics.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="raw_metrics_sha256"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )
    raw = _f_rows(incomplete=3000)
    assert pd.isna(raw.loc[raw["replicate"] == 3000, "ap"]).all()
    raw.loc[raw["replicate"] == 3000, "ap"] = 0.0
    metadata, freeze = _provenance(tmp_path, raw)
    with pytest.raises(ValueError, match="unavailable AP"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )


def test_gate_rejects_inconsistent_pair_failure_count(tmp_path: Path) -> None:
    raw = _f_rows(incomplete=3000)
    raw.loc[raw["replicate"] == 3000, "n_failed_pairs"] = 0
    metadata, freeze = _provenance(tmp_path, raw)

    with pytest.raises(ValueError, match="failure counts"):
        evaluate_f_validation(
            raw,
            load_config(FOLLOWUP_CONFIG),
            metadata=metadata,
            freeze_manifest=freeze,
            raw_metrics_path=tmp_path / "raw_metrics.csv",
            resolved_config_path=tmp_path / "resolved_config.yaml",
            source_config_path=FOLLOWUP_CONFIG,
        )
