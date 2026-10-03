"""Fail closed on malformed or unsafe manual CIN F follow-up dispatch inputs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_PROTOCOLS = {"cin-followup-f-v1", "cin-followup-f-v2"}


def read_protocol(config_path: Path) -> str | None:
    try:
        payload: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid YAML config: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("config YAML root must be a mapping")
    protocol = payload.get("protocol")
    if protocol is None:
        return None
    if not isinstance(protocol, str):
        raise ValueError("config protocol must be a string")
    if protocol.startswith("cin-followup-f-") and protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError(f"unsupported CIN F follow-up protocol: {protocol}")
    return protocol if protocol in SUPPORTED_PROTOCOLS else None


def validate_dispatch(
    *,
    protocol: str | None,
    dim1_flag: str,
    dim1_values: str,
    dim2_flag: str,
    dim2_values: str,
    aggregation_phase: str,
    dim3_flag: str = "",
    dim3_values: str = "",
) -> None:
    """Validate fixed follow-up dimensions before GitHub expands shard matrix."""
    if protocol is None:
        return
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError(f"unsupported CIN F follow-up protocol: {protocol}")
    if dim1_flag != "--cases" or dim1_values != "F":
        raise ValueError("CIN F follow-up dimension 1 must be exactly --cases F")
    if protocol == "cin-followup-f-v1":
        if dim3_flag == "--f-max-tries":
            raise ValueError("generator cap overrides are not allowed for a frozen protocol")
        return

    if dim2_flag != "--replicate-batches":
        raise ValueError("CIN F follow-up v2 dimension 2 must be --replicate-batches")
    if dim3_flag or dim3_values:
        raise ValueError("CIN F follow-up v2 does not allow a third dimension")
    expected_batches = {
        "development": "dev0",
        "validation": "val0,val1",
    }
    if aggregation_phase not in expected_batches:
        raise ValueError("CIN F follow-up v2 requires development or validation phase")
    if dim2_values != expected_batches[aggregation_phase]:
        raise ValueError(
            f"CIN F follow-up v2 {aggregation_phase} must use only "
            f"{expected_batches[aggregation_phase]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dim1-flag")
    parser.add_argument("--dim1-values")
    parser.add_argument("--dim2-flag")
    parser.add_argument("--dim2-values")
    parser.add_argument("--dim3-flag", default="")
    parser.add_argument("--dim3-values", default="")
    parser.add_argument("--aggregation-phase", default="full")
    args = parser.parse_args(argv)
    try:
        protocol = read_protocol(args.config)
        dimensions = (args.dim1_flag, args.dim1_values, args.dim2_flag, args.dim2_values)
        if any(value is not None for value in dimensions):
            if any(value is None for value in dimensions):
                parser.error("all four dimension flags/values are required together")
            validate_dispatch(
                protocol=protocol,
                dim1_flag=args.dim1_flag,
                dim1_values=args.dim1_values,
                dim2_flag=args.dim2_flag,
                dim2_values=args.dim2_values,
                dim3_flag=args.dim3_flag,
                dim3_values=args.dim3_values,
                aggregation_phase=args.aggregation_phase,
            )
    except ValueError as exc:
        parser.error(str(exc))
    print(protocol or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
