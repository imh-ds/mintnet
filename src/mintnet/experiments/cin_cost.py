"""Configuration contracts for the CIN cost-pilot runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cin_common import load_yaml


@dataclass(frozen=True)
class CostCell:
    cell_id: str
    kind: str
    p: int
    n: int


@dataclass(frozen=True)
class CostConfig:
    cells: tuple[CostCell, ...]
    repeats: tuple[int, ...]
    master_seed: int
    source_path: Path


def load_config(path: Path) -> CostConfig:
    source = Path(path)
    payload = load_yaml(source)
    raw_cells = payload.get("cells")
    if not isinstance(raw_cells, list) or not raw_cells:
        raise ValueError("cost configuration requires non-empty cells")
    cells: list[CostCell] = []
    seen: set[str] = set()
    for raw in raw_cells:
        if not isinstance(raw, dict):
            raise ValueError("each cost cell must be a mapping")
        cell_id = str(raw.get("id", ""))
        kind = str(raw.get("kind", ""))
        if not cell_id or cell_id in seen:
            raise ValueError(f"duplicate or empty cost cell id: {cell_id!r}")
        if kind not in {"dense_continuous", "categorical5", "categorical10", "mixed"}:
            raise ValueError(f"unsupported cost input kind: {kind}")
        p = int(raw.get("p", 0))
        n = int(raw.get("n", 0))
        if p < 1 or n < 1:
            raise ValueError(f"cost cell dimensions must be positive: {cell_id}")
        cells.append(CostCell(cell_id, kind, p, n))
        seen.add(cell_id)
    repeats = tuple(int(value) for value in payload.get("repeats", ()))
    if not repeats or any(value < 1 for value in repeats):
        raise ValueError("cost configuration requires positive repeats")
    master_seed = int(payload.get("master_seed", -1))
    if master_seed < 0:
        raise ValueError("master_seed must be nonnegative")
    return CostConfig(tuple(cells), repeats, master_seed, source.resolve())


def expected_row_count(config: CostConfig) -> int:
    return len(config.cells) * len(config.repeats)


def expected_combinations(config: CostConfig) -> set[tuple[str, int]]:
    return {(cell.cell_id, repeat) for cell in config.cells for repeat in config.repeats}


COMBINATION_COLUMNS = ("cell", "repeat")


__all__ = [
    "COMBINATION_COLUMNS",
    "CostCell",
    "CostConfig",
    "expected_combinations",
    "expected_row_count",
    "load_config",
]
