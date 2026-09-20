"""Evidence rendering and the predeclared descriptive reading for the
Stage 6a conditioning-set architecture experiment. See
docs/stage6a_charter.md.

Implementation-time clarification, made before any evidence exists:
the charter's own accuracy-comparison requirement ("comparable to or
better... within .01... at a majority of tested N") is fixed here to
the same `0.01` tolerance and `>= majority of tested N` convention
used throughout every prior Stage 5 charter.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6a import COMPOSED_SHAPES, ISOLATION_SHAPES, Stage6aConfig

_GAP_TOLERANCE = 0.01
_RECALL_DROP_TOLERANCE = 0.01


@dataclass(frozen=True)
class CellSummary:
    tier: str
    shape: str
    method: str
    n: int
    n_errors: int
    precision: float | None
    recall: float | None
    f1: float | None
    shd: float | None


@dataclass(frozen=True)
class ShapeReading:
    tier: str
    shape: str
    max_conditioning_size_used: int
    any_cap_reached: bool
    n_accuracy_comparable: int
    n_tested: int
    accuracy_reading: str
    recall_reading: str


@dataclass(frozen=True)
class Stage6aReport:
    by_cell: tuple[CellSummary, ...]
    by_shape: tuple[ShapeReading, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def summarize_cell(raw: pd.DataFrame, tier: str, shape: str, method: str, n: int, config: Stage6aConfig) -> CellSummary:
    cell_raw = raw.loc[
        (raw["tier"] == tier) & (raw["shape"] == shape) & (raw["method"] == method) & (raw["n"] == n)
    ]
    validation = _partition(cell_raw, config.validation_replicates)
    n_errors = int((validation["status"] != "ok").sum())
    ok = validation.loc[validation["status"] == "ok"]
    if ok.empty:
        return CellSummary(tier, shape, method, n, n_errors, None, None, None, None)
    return CellSummary(
        tier, shape, method, n, n_errors,
        float(ok["precision"].mean()), float(ok["recall"].mean()), float(ok["f1"].mean()), float(ok["shd"].mean()),
    )


def _shape_reading(tier: str, shape: str, by_cell: tuple[CellSummary, ...], sizes: pd.DataFrame) -> ShapeReading:
    shape_sizes = sizes.loc[(sizes["tier"] == tier) & (sizes["shape"] == shape)]
    max_size = int(shape_sizes["conditioning_size"].max()) if not shape_sizes.empty else 0
    any_cap = bool(shape_sizes["cap_reached"].any()) if not shape_sizes.empty else False

    full = sorted((c for c in by_cell if c.method == "full_component"), key=lambda c: c.n)
    growing = sorted((c for c in by_cell if c.method == "growing_subset"), key=lambda c: c.n)
    n_tested = len(full)

    n_comparable = sum(
        1 for f, g in zip(full, growing)
        if f.f1 is not None and g.f1 is not None and g.f1 >= f.f1 - _GAP_TOLERANCE
    )
    majority = (n_tested // 2) + 1
    if n_comparable >= majority:
        accuracy_reading = f"growing-subset F1 comparable to or better than full-component at {n_comparable}/{n_tested} tested N"
    else:
        accuracy_reading = f"growing-subset F1 trails full-component at a majority of tested N ({n_comparable}/{n_tested} comparable)"

    recall_drops = [
        (f.n, f.recall, g.recall)
        for f, g in zip(full, growing)
        if f.recall is not None and g.recall is not None and g.recall < f.recall - _RECALL_DROP_TOLERANCE
    ]
    if not recall_drops:
        recall_reading = "no material recall cost: growing-subset recall stays within .01 of full-component's at every tested N"
    else:
        worst = min(recall_drops, key=lambda item: item[2] - item[1])
        recall_reading = (
            f"recall cost found at {len(recall_drops)}/{n_tested} tested N, worst at N={worst[0]}: "
            f"full-component {worst[1]:.4f} vs. growing-subset {worst[2]:.4f}"
        )

    return ShapeReading(tier, shape, max_size, any_cap, n_comparable, n_tested, accuracy_reading, recall_reading)


def evaluate_stage6a(raw: pd.DataFrame, sizes: pd.DataFrame, config: Stage6aConfig) -> Stage6aReport:
    by_cell: list[CellSummary] = []
    by_shape: list[ShapeReading] = []

    for tier, shapes, ns in (
        ("isolation", ISOLATION_SHAPES, config.isolation_sample_sizes),
        ("composed", COMPOSED_SHAPES, config.composed_sample_sizes),
    ):
        for shape in shapes:
            shape_cells = [
                summarize_cell(raw, tier, shape, method, n, config) for n in ns for method in ("full_component", "growing_subset")
            ]
            by_cell.extend(shape_cells)
            by_shape.append(_shape_reading(tier, shape, tuple(shape_cells), sizes))

    return Stage6aReport(tuple(by_cell), tuple(by_shape))


def write_stage6a_report(raw: pd.DataFrame, sizes: pd.DataFrame, config: Stage6aConfig, output_dir: Path) -> Stage6aReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage6a(raw, sizes, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {"by_cell": [asdict(c) for c in report.by_cell], "by_shape": [asdict(s) for s in report.by_shape]},
            indent=2, allow_nan=True,
        ) + "\n",
        encoding="utf-8",
    )

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = [
        "# Stage 6a Conditioning-Set Architecture Report (mi-native prep)\n",
        "Compares full-component DPI (unmodified `compose_screen_then_prune`) against growing-subset "
        "DPI (PC-style, size-1-then-escalate search over MINT's own screened candidate graph), same "
        "Fisher-z primitive, same drawn data. No new estimator, no production pipeline change.\n",
        "## Dimension finding and accuracy reading, per shape\n",
        "| tier | shape | max conditioning size used | cap ever reached | accuracy reading | recall reading |",
        "|---|---|---|---|---|---|",
    ]
    for shape in report.by_shape:
        sections.append(
            f"| {shape.tier} | {shape.shape} | {shape.max_conditioning_size_used} | {shape.any_cap_reached} | "
            f"{shape.accuracy_reading} | {shape.recall_reading} |"
        )
    sections.append("")

    for tier in ("isolation", "composed"):
        shapes = ISOLATION_SHAPES if tier == "isolation" else COMPOSED_SHAPES
        for shape in shapes:
            rows = [
                f"## {tier} / {shape}\n",
                "| N | method | precision | recall | F1 | SHD | errors |",
                "|---|---|---|---|---|---|---|",
            ]
            ns = config.isolation_sample_sizes if tier == "isolation" else config.composed_sample_sizes
            for n in ns:
                for method in ("full_component", "growing_subset"):
                    cell = next(c for c in report.by_cell if c.tier == tier and c.shape == shape and c.method == method and c.n == n)
                    rows.append(
                        f"| {n} | {method} | {fmt(cell.precision)} | {fmt(cell.recall)} | {fmt(cell.f1)} | "
                        f"{fmt(cell.shd)} | {cell.n_errors} |"
                    )
            sections.append("\n".join(rows) + "\n")

    sections.append(
        "Descriptive result, not a production pipeline change -- see `docs/stage6a_charter.md`'s own "
        "decision structure and non-goals. See `raw_metrics.csv`, `conditioning_sizes.csv`, `report.json`, "
        "and `resolved_config.yaml` for complete evidence.\n"
    )
    (output_dir / "stage6a_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


write_report = write_stage6a_report
