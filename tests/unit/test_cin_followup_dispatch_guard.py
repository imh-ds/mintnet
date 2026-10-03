from __future__ import annotations

from pathlib import Path

import pytest

import scripts.cin_followup_dispatch_guard as dispatch_guard


def test_yaml_equivalent_protocol_forms_are_classified_as_followup(tmp_path: Path) -> None:
    for protocol_line in (
        "protocol: cin-followup-f-v2",
        'protocol: "cin-followup-f-v2"',
        "protocol: 'cin-followup-f-v2' # frozen campaign",
    ):
        config = tmp_path / "config.yaml"
        config.write_text(f"{protocol_line}\ncases: [F]\n", encoding="utf-8")
        assert dispatch_guard.read_protocol(config) == "cin-followup-f-v2"


def test_followup_dispatch_is_rejected_before_matrix_creation_when_dimensions_change() -> None:
    valid = {
        "protocol": "cin-followup-f-v2",
        "dim1_flag": "--cases",
        "dim1_values": "F",
        "dim2_flag": "--replicate-batches",
        "dim2_values": "val0,val1",
        "dim3_flag": "",
        "dim3_values": "",
        "aggregation_phase": "validation",
    }
    dispatch_guard.validate_dispatch(**valid)

    for field, value in (
        ("dim1_flag", "--f-max-tries"),
        ("dim1_values", "F,F"),
        ("dim2_values", "val0,val1,val2"),
        ("dim3_flag", "--support-aware-inner-splits"),
    ):
        changed = {**valid, field: value}
        with pytest.raises(ValueError):
            dispatch_guard.validate_dispatch(**changed)


def test_generic_config_is_ignored_but_unknown_followup_protocol_fails_closed(
    tmp_path: Path,
) -> None:
    generic = tmp_path / "generic.yaml"
    generic.write_text("cases: [A]\n", encoding="utf-8")
    assert dispatch_guard.read_protocol(generic) is None

    unknown = tmp_path / "unknown.yaml"
    unknown.write_text('protocol: "cin-followup-f-v99"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported CIN F follow-up protocol"):
        dispatch_guard.read_protocol(unknown)


def test_malformed_yaml_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "malformed.yaml"
    config.write_text("protocol: [cin-followup-f-v2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid YAML"):
        dispatch_guard.read_protocol(config)


def test_cli_accepts_workflow_dash_prefixed_flags_with_equals_form(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "followup.yaml"
    config.write_text('protocol: "cin-followup-f-v2" # frozen\n', encoding="utf-8")

    result = dispatch_guard.main(
        [
            "--config",
            str(config),
            "--dim1-flag=--cases",
            "--dim1-values=F",
            "--dim2-flag=--replicate-batches",
            "--dim2-values=dev0",
            "--dim3-flag=",
            "--dim3-values=",
            "--aggregation-phase=development",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out.strip() == "cin-followup-f-v2"
