"""Configuration contracts for the CIN statistical-panel runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cin_common import load_yaml


CASE_ORDER = tuple("ABCDEFGHI") + ("regression",)


@dataclass(frozen=True)
class PanelConfig:
    cases: tuple[str, ...]
    master_seed: int
    development_replicates: tuple[int, ...]
    validation_replicates: tuple[int, ...]
    n_overrides: dict[str, int]
    stability_cases: tuple[str, ...]
    stability_repeats: int
    stability_fraction: float
    source_path: Path


def _replicate_range(values: object, name: str) -> tuple[int, ...]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} must be a non-empty list")
    result = tuple(int(value) for value in values)
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def load_config(path: Path) -> PanelConfig:
    source = Path(path)
    payload = load_yaml(source)
    cases_value = payload.get("cases")
    if not isinstance(cases_value, list) or not cases_value:
        raise ValueError("panel configuration requires non-empty cases")
    cases = tuple(str(value) for value in cases_value)
    unknown = sorted(set(cases) - set(CASE_ORDER))
    if unknown:
        raise ValueError(f"unknown case: {unknown[0]}")
    if len(set(cases)) != len(cases):
        raise ValueError("panel cases must not contain duplicates")
    development = _replicate_range(payload.get("development_replicates"), "development_replicates")
    validation = _replicate_range(payload.get("validation_replicates"), "validation_replicates")
    if set(development) & set(validation):
        raise ValueError("development and validation replicate ranges must be disjoint")
    overrides_value = payload.get("n_overrides", {})
    if not isinstance(overrides_value, dict):
        raise ValueError("n_overrides must be a mapping")
    overrides = {str(key): int(value) for key, value in overrides_value.items()}
    if set(overrides) - set(cases):
        raise ValueError("n_overrides may only name configured cases")
    if any(value < 1 for value in overrides.values()):
        raise ValueError("n_overrides values must be positive")
    master_seed = int(payload.get("master_seed", -1))
    if master_seed < 0:
        raise ValueError("master_seed must be nonnegative")
    stability_cases = tuple(str(value) for value in payload.get("stability_cases", ()))
    if set(stability_cases) - set(cases):
        raise ValueError("stability_cases must be configured cases")
    stability_repeats = int(payload.get("stability_repeats", 0))
    stability_fraction = float(payload.get("stability_fraction", 0.0))
    if stability_repeats < 0 or not 0.0 < stability_fraction <= 1.0:
        raise ValueError("invalid stability settings")
    return PanelConfig(
        cases=cases,
        master_seed=master_seed,
        development_replicates=development,
        validation_replicates=validation,
        n_overrides=overrides,
        stability_cases=stability_cases,
        stability_repeats=stability_repeats,
        stability_fraction=stability_fraction,
        source_path=source.resolve(),
    )


COMBINATION_COLUMNS = ("case", "phase", "method")


__all__ = ["CASE_ORDER", "COMBINATION_COLUMNS", "PanelConfig", "load_config"]
