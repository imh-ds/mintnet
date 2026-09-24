"""Budgeted repeated-refit stability for CIN fits."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STABILITY_TAG = 0xC17
STABILITY_COLUMNS = (
    "fit_id",
    "repeat_id",
    "repeat_seed",
    "node_i",
    "node_j",
    "gain_i_to_j",
    "gain_j_to_i",
    "weight_nats_raw",
    "status",
)

__all__ = [
    "STABILITY_COLUMNS",
    "STABILITY_TAG",
    "StabilityResult",
    "load_stability",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _repeat_seeds(fit_seed: int, repeats: int) -> tuple[int, ...]:
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    return tuple(
        int(
            np.random.SeedSequence(
                entropy=int(fit_seed),
                spawn_key=(STABILITY_TAG, repeat_id),
            ).generate_state(1, dtype=np.uint64)[0]
        )
        for repeat_id in range(repeats)
    )


def _sample_indices(
    retained_count: int,
    sample_size: int,
    fit_seed: int,
    repeat_id: int,
) -> np.ndarray:
    if retained_count < 1 or sample_size < 1 or sample_size > retained_count:
        raise ValueError("sample_size must be between 1 and retained_count")
    child = np.random.SeedSequence(
        entropy=int(fit_seed),
        spawn_key=(STABILITY_TAG, int(repeat_id)),
    )
    indices = np.random.default_rng(child).choice(
        retained_count, size=sample_size, replace=False
    )
    return np.sort(np.asarray(indices, dtype=np.intp))


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    required = {
        "fit_id",
        "config_hash",
        "digests",
        "schema",
        "seed",
        "stability_tag",
        "repeats_requested",
        "fraction",
        "sample_size",
        "repeat_seeds",
        "completed_repeat_ids",
        "repeats_completed",
        "status",
        "preflight",
    }
    missing = required - set(metadata)
    if missing:
        raise ValueError(f"stability metadata is missing fields: {sorted(missing)!r}")
    if metadata["stability_tag"] != STABILITY_TAG:
        raise ValueError("stability metadata has an unknown seed tag")
    digests = metadata["digests"]
    if not isinstance(digests, Mapping) or not {
        "data_digest",
        "row_identity_digest",
    } <= set(digests):
        raise ValueError("stability metadata is missing data digests")
    repeats = metadata["repeats_requested"]
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("stability metadata has an invalid repeat count")
    fraction = metadata["fraction"]
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
        raise ValueError("stability metadata has an invalid fraction")
    if not 0 < float(fraction) <= 1 or not np.isfinite(float(fraction)):
        raise ValueError("stability metadata has an invalid fraction")
    repeat_seeds = tuple(int(seed) for seed in metadata["repeat_seeds"])
    if len(repeat_seeds) != repeats or len(set(repeat_seeds)) != repeats:
        raise ValueError("stability metadata has an invalid repeat seed list")
    completed = tuple(int(repeat_id) for repeat_id in metadata["completed_repeat_ids"])
    if len(set(completed)) != len(completed) or any(
        repeat_id < 0 or repeat_id >= repeats for repeat_id in completed
    ):
        raise ValueError("stability metadata has invalid completed repeat ids")
    if metadata["repeats_completed"] != len(completed):
        raise ValueError("stability metadata has an inconsistent completion count")


def _canonical_pairs(schema: Mapping[str, Any]) -> set[tuple[str, str]]:
    names = [str(name) for name in schema]
    return {
        (names[left], names[right])
        for left in range(len(names))
        for right in range(left + 1, len(names))
    }


def _validate_records(records: pd.DataFrame, metadata: Mapping[str, Any]) -> None:
    missing = [column for column in STABILITY_COLUMNS if column not in records.columns]
    if missing:
        raise ValueError(f"stability records are missing columns: {missing!r}")
    if list(records.columns) != list(STABILITY_COLUMNS):
        raise ValueError("stability records have an unexpected column order")
    if not records.empty:
        if records["fit_id"].astype(str).ne(str(metadata["fit_id"])).any():
            raise ValueError("stability records contain another fit id")
        expected_pairs = _canonical_pairs(metadata["schema"])
        key_frame = records.loc[:, ["repeat_id", "node_i", "node_j"]].copy()
        keys: list[tuple[int, str, str]] = []
        for record in key_frame.to_dict(orient="records"):
            repeat_id = int(record["repeat_id"])
            left = str(record["node_i"])
            right = str(record["node_j"])
            if repeat_id < 0 or repeat_id >= int(metadata["repeats_requested"]):
                raise ValueError("stability records contain an invalid repeat id")
            if (left, right) not in expected_pairs:
                raise ValueError("stability records contain a non-canonical pair")
            keys.append((repeat_id, left, right))
        if len(set(keys)) != len(keys):
            raise ValueError("stability records contain duplicate repeat/pair keys")


@dataclass(frozen=True)
class StabilityResult:
    """Stored repeated-fit records and provenance, without raw participant data."""

    records: pd.DataFrame
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.records, pd.DataFrame):
            raise ValueError("records must be a pandas DataFrame")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        metadata = copy.deepcopy(self.metadata)
        _validate_metadata(metadata)
        records = self.records.copy(deep=True)
        missing = [column for column in STABILITY_COLUMNS if column not in records.columns]
        if records.empty and missing:
            records = pd.DataFrame(columns=STABILITY_COLUMNS)
        _validate_records(records, metadata)
        object.__setattr__(self, "records", records.loc[:, list(STABILITY_COLUMNS)])
        object.__setattr__(self, "metadata", metadata)

    @property
    def fit_id(self) -> str:
        return str(self.metadata["fit_id"])

    @property
    def repeats_requested(self) -> int:
        return int(self.metadata["repeats_requested"])

    @property
    def repeats_completed(self) -> int:
        return int(self.metadata["repeats_completed"])

    @property
    def status(self) -> str:
        return str(self.metadata["status"])

    def save(self, directory: str | Path, *, compressed: bool = False) -> None:
        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        record_name = "stability_records.csv.gz" if compressed else "stability_records.csv"
        self.records.to_csv(
            output / record_name,
            index=False,
            float_format="%.17g",
            compression="gzip" if compressed else None,
        )
        with (output / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(_json_safe(self.metadata), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")


def _read_records(path: Path) -> pd.DataFrame:
    records = pd.read_csv(path, keep_default_na=False, compression="infer")
    numeric_columns = {
        "repeat_id",
        "repeat_seed",
        "gain_i_to_j",
        "gain_j_to_i",
        "weight_nats_raw",
    }
    for column in numeric_columns & set(records.columns):
        records[column] = pd.to_numeric(records[column], errors="coerce")
    return records


def load_stability(directory: str | Path) -> StabilityResult:
    """Load a saved stability result and validate its provenance and keys."""

    source = Path(directory)
    metadata_path = source / "metadata.json"
    if not metadata_path.is_file():
        raise ValueError("stability directory is missing metadata.json")
    record_path = source / "stability_records.csv"
    if not record_path.is_file():
        record_path = source / "stability_records.csv.gz"
    if not record_path.is_file():
        raise ValueError("stability directory is missing stability_records.csv")
    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    if not isinstance(metadata, dict):
        raise ValueError("stability metadata must contain an object")
    return StabilityResult(_read_records(record_path), metadata)
