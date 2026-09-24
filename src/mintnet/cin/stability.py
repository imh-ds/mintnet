"""Budgeted repeated-refit stability for CIN fits."""

from __future__ import annotations

import copy
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import CINConfig, prepare_data
from .fit import _fit_prepared
from .result import NetworkFit

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
    "estimate_stability",
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


def _fit_definition(fit: NetworkFit) -> tuple[dict[str, Any], dict[str, Any], CINConfig]:
    if not isinstance(fit, NetworkFit):
        raise ValueError("fit must be a NetworkFit")
    metadata = fit.metadata
    schema = metadata.get("schema")
    config_payload = metadata.get("config")
    if not isinstance(schema, Mapping) or not isinstance(config_payload, Mapping):
        raise ValueError("fit metadata must contain schema and config")
    if not isinstance(metadata.get("fit_id"), str) or not metadata["fit_id"]:
        raise ValueError("fit metadata must contain fit_id")
    digests = metadata.get("digests")
    if not isinstance(digests, Mapping) or not {
        "data_digest",
        "row_identity_digest",
    } <= set(digests):
        raise ValueError("fit metadata must contain data and row identity digests")
    config_values = dict(config_payload)
    if isinstance(config_values.get("lambda_grid"), list):
        config_values["lambda_grid"] = tuple(config_values["lambda_grid"])
    return copy.deepcopy(dict(schema)), copy.deepcopy(dict(metadata)), CINConfig(**config_values)


def _validate_request(repeats: int, fraction: float, max_seconds: float) -> None:
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
        raise ValueError("fraction must be a finite number in (0, 1]")
    if not np.isfinite(float(fraction)) or not 0 < float(fraction) <= 1:
        raise ValueError("fraction must be a finite number in (0, 1]")
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)):
        raise ValueError("max_seconds must be a positive finite number")
    if not np.isfinite(float(max_seconds)) or float(max_seconds) <= 0:
        raise ValueError("max_seconds must be a positive finite number")


def _base_metadata(
    fit_metadata: Mapping[str, Any],
    *,
    config: CINConfig,
    repeats: int,
    fraction: float,
    sample_size: int,
    repeat_seeds: tuple[int, ...],
    status: str,
    completed_repeat_ids: list[int],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    return {
        "fit_id": fit_metadata["fit_id"],
        "config_hash": fit_metadata["config_hash"],
        "digests": copy.deepcopy(fit_metadata["digests"]),
        "schema": copy.deepcopy(fit_metadata["schema"]),
        "seed": int(config.seed),
        "stability_tag": STABILITY_TAG,
        "repeats_requested": int(repeats),
        "B": int(repeats),
        "fraction": float(fraction),
        "sample_size": int(sample_size),
        "repeat_seeds": list(repeat_seeds),
        "completed_repeat_ids": sorted(int(value) for value in completed_repeat_ids),
        "repeats_completed": len(completed_repeat_ids),
        "status": status,
        "preflight": _json_safe(preflight),
    }


def _empty_records() -> pd.DataFrame:
    return pd.DataFrame(columns=STABILITY_COLUMNS)


def _validate_resume(
    resume: StabilityResult,
    fit_metadata: Mapping[str, Any],
    *,
    config: CINConfig,
    repeats: int,
    fraction: float,
    repeat_seeds: tuple[int, ...],
) -> tuple[pd.DataFrame, set[int]]:
    metadata = resume.metadata
    if resume.fit_id != fit_metadata["fit_id"]:
        raise ValueError("resume fit_id does not match the point fit")
    if metadata.get("config_hash") != fit_metadata.get("config_hash"):
        raise ValueError("resume config_hash does not match the point fit")
    if metadata.get("digests") != fit_metadata.get("digests"):
        raise ValueError("resume data digests do not match the point fit")
    if metadata.get("schema") != fit_metadata.get("schema"):
        raise ValueError("resume schema does not match the point fit")
    if metadata.get("seed") != config.seed:
        raise ValueError("resume seed does not match the point fit")
    if metadata.get("repeats_requested") != repeats:
        raise ValueError("resume repeat count does not match the request")
    if not np.isclose(float(metadata.get("fraction")), fraction, rtol=0, atol=0):
        raise ValueError("resume fraction does not match the request")
    if tuple(int(seed) for seed in metadata.get("repeat_seeds", ())) != repeat_seeds:
        raise ValueError("resume repeat seeds do not match the request")
    completed = {int(value) for value in metadata.get("completed_repeat_ids", ())}
    records = resume.records.loc[resume.records["repeat_id"].isin(completed)].copy()
    return records, completed


def _records_from_fit(
    fit: NetworkFit,
    *,
    fit_id: str,
    repeat_id: int,
    repeat_seed: int,
    interrupted: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in fit.pairs.to_dict(orient="records"):
        status = "interrupted" if interrupted else str(record["status"])
        available = not interrupted and status == "complete"
        rows.append(
            {
                "fit_id": fit_id,
                "repeat_id": int(repeat_id),
                "repeat_seed": int(repeat_seed),
                "node_i": str(record["node_i"]),
                "node_j": str(record["node_j"]),
                "gain_i_to_j": float(record["gain_i_to_j"]) if available else np.nan,
                "gain_j_to_i": float(record["gain_j_to_i"]) if available else np.nan,
                "weight_nats_raw": float(record["weight_nats_raw"]) if available else np.nan,
                "status": status,
            }
        )
    return rows


def _run_repeat(
    frame: pd.DataFrame,
    schema: Mapping[str, Mapping[str, Any]],
    config: CINConfig,
    *,
    repeat_seed: int,
    deadline: float,
) -> NetworkFit:
    prepared = prepare_data(frame, schema, config)
    return _fit_prepared(
        prepared,
        schema,
        config,
        deadline=deadline,
        split_seed=repeat_seed,
    )


def estimate_stability(
    fit: NetworkFit | None = None,
    frame: Any = None,
    *,
    repeats: int = 10,
    fraction: float = 0.8,
    max_seconds: float = 600.0,
    resume: StabilityResult | str | Path | None = None,
    elapsed_estimate: float | None = None,
) -> StabilityResult:
    """Estimate reproducibility by explicitly repeating fit/subsample work."""

    if fit is None:
        raise NotImplementedError("estimate_stability requires a NetworkFit")
    if frame is None:
        raise ValueError("estimate_stability requires a frame")
    _validate_request(repeats, fraction, max_seconds)
    schema, fit_metadata, config = _fit_definition(fit)
    from .config import prepare_data

    prepared = prepare_data(frame, schema, config)
    expected_digests = fit_metadata["digests"]
    if prepared.data_digest != expected_digests["data_digest"]:
        raise ValueError("data_digest does not match the point fit")
    if prepared.row_identity_digest != expected_digests["row_identity_digest"]:
        raise ValueError("row_identity_digest does not match the point fit")

    sample_size = int(np.floor(float(fraction) * prepared.n_retained))
    repeat_seeds = _repeat_seeds(config.seed, repeats)
    prior_records = _empty_records()
    completed: set[int] = set()
    if resume is not None:
        if isinstance(resume, (str, Path)):
            resume = load_stability(resume)
        if not isinstance(resume, StabilityResult):
            raise ValueError("resume must be a StabilityResult or result directory")
        prior_records, completed = _validate_resume(
            resume,
            fit_metadata,
            config=config,
            repeats=repeats,
            fraction=float(fraction),
            repeat_seeds=repeat_seeds,
        )

    runtime_metadata = fit_metadata.get("runtime", {})
    recorded_elapsed = runtime_metadata.get("elapsed_seconds")
    if elapsed_estimate is None:
        elapsed_estimate = recorded_elapsed
    if (
        elapsed_estimate is None
        or isinstance(elapsed_estimate, bool)
        or not isinstance(elapsed_estimate, (int, float))
        or not np.isfinite(float(elapsed_estimate))
        or float(elapsed_estimate) <= 0
    ):
        raise ValueError("a positive elapsed_estimate is required for stability preflight")

    preflight = {
        "elapsed_estimate": float(elapsed_estimate),
        "estimated_seconds": 0.0,
        "max_seconds": float(max_seconds),
        "sample_size": sample_size,
    }
    if sample_size < 30:
        metadata = _base_metadata(
            fit_metadata,
            config=config,
            repeats=repeats,
            fraction=float(fraction),
            sample_size=sample_size,
            repeat_seeds=repeat_seeds,
            status="unsupported_repeat_request",
            completed_repeat_ids=sorted(completed),
            preflight=preflight,
        )
        return StabilityResult(prior_records, metadata)

    remaining = [repeat_id for repeat_id in range(repeats) if repeat_id not in completed]
    preflight["estimated_seconds"] = 1.5 * len(remaining) * float(elapsed_estimate)
    if not remaining or preflight["estimated_seconds"] > float(max_seconds):
        status = "complete" if not remaining else "budget_not_started"
        metadata = _base_metadata(
            fit_metadata,
            config=config,
            repeats=repeats,
            fraction=float(fraction),
            sample_size=sample_size,
            repeat_seeds=repeat_seeds,
            status=status,
            completed_repeat_ids=sorted(completed),
            preflight=preflight,
        )
        return StabilityResult(prior_records, metadata)

    retained_frame = frame.loc[prepared.index]
    deadline = time.monotonic() + float(max_seconds)
    new_rows: list[dict[str, Any]] = []
    overall_status = "complete"
    for repeat_id in remaining:
        if time.monotonic() >= deadline:
            overall_status = "interrupted"
            break
        indices = _sample_indices(prepared.n_retained, sample_size, config.seed, repeat_id)
        repeat_frame = retained_frame.iloc[indices].copy()
        repeat_fit = _run_repeat(
            repeat_frame,
            schema,
            config,
            repeat_seed=repeat_seeds[repeat_id],
            deadline=deadline,
        )
        repeat_complete = bool(repeat_fit.metadata.get("complete")) and (
            repeat_fit.metadata.get("runtime", {}).get("status") == "complete"
        )
        new_rows.extend(
            _records_from_fit(
                repeat_fit,
                fit_id=str(fit_metadata["fit_id"]),
                repeat_id=repeat_id,
                repeat_seed=repeat_seeds[repeat_id],
                interrupted=not repeat_complete,
            )
        )
        if not repeat_complete:
            overall_status = "interrupted"
            break
        completed.add(repeat_id)

    new_records = pd.DataFrame(new_rows, columns=STABILITY_COLUMNS)
    records = pd.concat([prior_records, new_records], ignore_index=True)
    if not records.empty:
        records = records.loc[:, list(STABILITY_COLUMNS)]
    metadata = _base_metadata(
        fit_metadata,
        config=config,
        repeats=repeats,
        fraction=float(fraction),
        sample_size=sample_size,
        repeat_seeds=repeat_seeds,
        status="complete" if len(completed) == repeats else overall_status,
        completed_repeat_ids=sorted(completed),
        preflight=preflight,
    )
    metadata["preflight"]["elapsed_seconds"] = float(time.monotonic() - (deadline - float(max_seconds)))
    return StabilityResult(records, metadata)


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
