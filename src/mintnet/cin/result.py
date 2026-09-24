"""Stable in-memory result contract for CIN network fits."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["NetworkFit", "PAIR_COLUMNS", "compute_fit_id", "load_fit"]


PAIR_COLUMNS = (
    "node_i",
    "node_j",
    "gain_i_to_j",
    "gain_j_to_i",
    "weight_nats_raw",
    "display_magnitude_nats",
    "gaussian_equivalent_magnitude",
    "orientation_gap",
    "n_scored",
    "folds_complete",
    "status",
    "diagnostic_flags",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): _json_safe(value) for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]


def _copy_frame(frame: pd.DataFrame, *, name: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"{name} must be a pandas DataFrame")
    return frame.copy(deep=True)


def compute_fit_id(
    config_hash: str,
    schema: Mapping[str, Any],
    data_digest: str,
    code_revision: str | None,
) -> str:
    """Return the stable identifier used to join fits and downstream artifacts."""

    schema_json = json.dumps(
        _json_safe(schema),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest_input = "\x1f".join(
        (str(config_hash), schema_json, str(data_digest), code_revision or "")
    ).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()[:16]


def _node_order(metadata: Mapping[str, Any], nodes: pd.DataFrame) -> list[str]:
    schema = metadata.get("schema")
    if isinstance(schema, Mapping):
        names = [str(name) for name in schema]
    elif "node" in nodes.columns:
        names = [str(name) for name in nodes["node"]]
    else:
        raise ValueError("fit metadata must contain schema variable order")
    if len(names) < 2 or len(set(names)) != len(names):
        raise ValueError("fit schema must contain at least two unique node names")
    if "node" in nodes.columns and [str(name) for name in nodes["node"]] != names:
        raise ValueError("nodes table order does not match metadata schema")
    return names


def _matrix_frame(
    pairs: pd.DataFrame,
    names: list[str],
    value_column: str,
) -> pd.DataFrame:
    positions = {name: index for index, name in enumerate(names)}
    values = np.full((len(names), len(names)), np.nan, dtype=np.float64)
    np.fill_diagonal(values, 0.0)
    for record in pairs.to_dict(orient="records"):
        left = str(record["node_i"])
        right = str(record["node_j"])
        status = record["status"]
        if status != "complete":
            continue
        value = record[value_column]
        if pd.isna(value):
            raise ValueError(f"complete pair {left!r}, {right!r} has no {value_column}")
        left_index = positions[left]
        right_index = positions[right]
        values[left_index, right_index] = float(value)
        values[right_index, left_index] = float(value)
    matrix = pd.DataFrame(values, index=names, columns=names)
    matrix.index.name = "node"
    return matrix


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, float_format="%.17g")


def _read_pairs(path: Path) -> pd.DataFrame:
    pairs = pd.read_csv(path, keep_default_na=False)
    numeric_columns = {
        "gain_i_to_j",
        "gain_j_to_i",
        "weight_nats_raw",
        "display_magnitude_nats",
        "gaussian_equivalent_magnitude",
        "orientation_gap",
        "n_scored",
        "folds_complete",
    }
    for column in numeric_columns & set(pairs.columns):
        pairs[column] = pd.to_numeric(pairs[column], errors="coerce")
    return pairs


@dataclass(frozen=True)
class NetworkFit:
    """Aggregate CIN fit results and provenance, without raw participant data."""

    pairs: pd.DataFrame
    nodes: pd.DataFrame
    folds: pd.DataFrame
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        pairs = _copy_frame(self.pairs, name="pairs")
        nodes = _copy_frame(self.nodes, name="nodes")
        folds = _copy_frame(self.folds, name="folds")
        missing = [column for column in PAIR_COLUMNS if column not in pairs.columns]
        if missing:
            raise ValueError(f"pairs is missing required columns: {missing!r}")
        extra = [column for column in pairs.columns if column not in PAIR_COLUMNS]
        pairs = pairs.loc[:, [*PAIR_COLUMNS, *extra]]
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        object.__setattr__(self, "pairs", pairs)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "folds", folds)
        object.__setattr__(self, "metadata", copy.deepcopy(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe payload suitable for the Task 6 writer."""

        return {
            "pairs": _records(self.pairs),
            "nodes": _records(self.nodes),
            "folds": _records(self.folds),
            "metadata": _json_safe(copy.deepcopy(self.metadata)),
        }

    def save(self, directory: str | Path) -> None:
        """Write the fit without raw observations or implicit lossy defaults."""

        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        names = _node_order(self.metadata, self.nodes)
        pair_nodes = {
            str(name)
            for name in self.pairs["node_i"].tolist() + self.pairs["node_j"].tolist()
        }
        if not pair_nodes <= set(names):
            raise ValueError("pairs table contains nodes absent from the fit schema")

        _write_csv(self.pairs, output / "pairs.csv")
        _write_csv(self.nodes, output / "nodes.csv")
        _write_csv(self.folds, output / "folds.csv")
        _matrix_frame(self.pairs, names, "weight_nats_raw").to_csv(
            output / "matrix_weight.csv", float_format="%.17g"
        )
        _matrix_frame(self.pairs, names, "display_magnitude_nats").to_csv(
            output / "matrix_display.csv", float_format="%.17g"
        )
        with (output / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(_json_safe(self.metadata), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NetworkFit":
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dictionary")
        required = {"pairs", "nodes", "folds", "metadata"}
        missing = required - set(payload)
        if missing:
            raise ValueError(f"payload is missing fields: {sorted(missing)!r}")
        pairs = pd.DataFrame(payload["pairs"])
        if pairs.empty:
            pairs = pd.DataFrame(columns=PAIR_COLUMNS)
        nodes = pd.DataFrame(payload["nodes"])
        folds = pd.DataFrame(payload["folds"])
        return cls(pairs=pairs, nodes=nodes, folds=folds, metadata=copy.deepcopy(payload["metadata"]))


def _read_matrix(path: Path, names: list[str]) -> pd.DataFrame:
    matrix = pd.read_csv(path, index_col=0)
    matrix.index = matrix.index.astype(str)
    matrix.columns = matrix.columns.astype(str)
    if list(matrix.index) != names or list(matrix.columns) != names:
        raise ValueError(f"{path.name} node labels do not match metadata schema")
    return matrix.apply(pd.to_numeric, errors="coerce")


def _validate_matrix(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    name: str,
) -> None:
    left = actual.to_numpy(dtype=np.float64)
    right = expected.to_numpy(dtype=np.float64)
    if not np.allclose(left, right, rtol=1e-15, atol=1e-15, equal_nan=True):
        raise ValueError(f"{name} does not match pairs table")


def load_fit(directory: str | Path) -> NetworkFit:
    """Load and validate a persisted :class:`NetworkFit`."""

    source = Path(directory)
    required = (
        "pairs.csv",
        "nodes.csv",
        "folds.csv",
        "matrix_weight.csv",
        "matrix_display.csv",
        "metadata.json",
    )
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        raise ValueError(f"fit directory is missing files: {missing!r}")

    with (source / "metadata.json").open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    if not isinstance(metadata, dict):
        raise ValueError("metadata.json must contain an object")
    pairs = _read_pairs(source / "pairs.csv")
    nodes = pd.read_csv(source / "nodes.csv")
    folds = pd.read_csv(source / "folds.csv")
    names = _node_order(metadata, nodes)
    expected_pair_count = len(names) * (len(names) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError("pairs table has the wrong pair count")

    expected_pairs = {
        (names[left], names[right])
        for left in range(len(names))
        for right in range(left + 1, len(names))
    }
    actual_pairs: list[tuple[str, str]] = []
    for record in pairs.to_dict(orient="records"):
        left = str(record["node_i"])
        right = str(record["node_j"])
        if left == right or left not in names or right not in names:
            raise ValueError("pairs table contains an invalid pair")
        ordered = (left, right) if names.index(left) < names.index(right) else (right, left)
        actual_pairs.append(ordered)
    if set(actual_pairs) != expected_pairs or len(set(actual_pairs)) != len(actual_pairs):
        raise ValueError("pairs table does not contain each unique node pair")

    digests = metadata.get("digests")
    if not isinstance(digests, Mapping):
        raise ValueError("metadata must contain digests")
    expected_fit_id = compute_fit_id(
        metadata.get("config_hash", ""),
        metadata.get("schema", {}),
        digests.get("data_digest", ""),
        metadata.get("git_revision"),
    )
    if metadata.get("fit_id") != expected_fit_id:
        raise ValueError("metadata fit_id does not match fit provenance")

    fit = NetworkFit(pairs=pairs, nodes=nodes, folds=folds, metadata=metadata)
    _validate_matrix(
        _read_matrix(source / "matrix_weight.csv", names),
        _matrix_frame(fit.pairs, names, "weight_nats_raw"),
        "matrix_weight.csv",
    )
    _validate_matrix(
        _read_matrix(source / "matrix_display.csv", names),
        _matrix_frame(fit.pairs, names, "display_magnitude_nats"),
        "matrix_display.csv",
    )
    return fit
