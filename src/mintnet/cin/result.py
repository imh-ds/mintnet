"""Stable in-memory result contract for CIN network fits."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["NetworkFit", "PAIR_COLUMNS"]


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
