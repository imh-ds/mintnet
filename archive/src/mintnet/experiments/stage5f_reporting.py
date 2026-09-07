"""Evidence rendering and the predeclared descriptive reading for the
Stage 5f diagnostic. See docs/stage5f_charter.md.

Implementation-time clarification, made before any evidence exists:
the charter's own decision structure fixes the MATERIAL/PARTIAL/MINIMAL
thresholds (passthrough share of false edges >= .5 / in (.1, .5) / <=
.1) at a majority of tested N -- this module fixes "majority" to a
concrete number, `>= 4` of the `7` tested N, mirroring Stage 5e's own
precedent for the same phrase.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage5f import BUCKETS, DGPS, Stage5fConfig

_MAJORITY_THRESHOLD = 4  # of 7 tested N


@dataclass(frozen=True)
class CellSummary:
    dgp: str
    n: int
    n_errors: int
    dpi_conditioned_true_edge: int
    dpi_conditioned_false_edge: int
    passthrough_true_edge: int
    passthrough_false_edge: int
    passthrough_share_of_false_edges: float | None


@dataclass(frozen=True)
class ShapeReading:
    dgp: str
    n_material: int
    n_partial: int
    n_minimal: int
    n_tested: int
    reading: str


@dataclass(frozen=True)
class Stage5fReport:
    by_cell: tuple[CellSummary, ...]
    by_shape: tuple[ShapeReading, ...]


def summarize_cell(raw: pd.DataFrame, dgp: str, n: int) -> CellSummary:
    cell = raw.loc[(raw["dgp"] == dgp) & (raw["n"] == n)]
    n_errors = int((cell["status"] != "ok").sum())
    ok = cell.loc[cell["status"] == "ok"]
    totals = {bucket: int(ok[bucket].sum()) for bucket in BUCKETS}
    false_total = totals["dpi_conditioned_false_edge"] + totals["passthrough_false_edge"]
    share = (totals["passthrough_false_edge"] / false_total) if false_total else None
    return CellSummary(
        dgp,
        n,
        n_errors,
        totals["dpi_conditioned_true_edge"],
        totals["dpi_conditioned_false_edge"],
        totals["passthrough_true_edge"],
        totals["passthrough_false_edge"],
        share,
    )


def _cell_classification(share: float | None) -> str | None:
    if share is None:
        return None
    if share >= 0.5:
        return "material"
    if share > 0.1:
        return "partial"
    return "minimal"


def _shape_reading(dgp: str, by_cell: tuple[CellSummary, ...]) -> ShapeReading:
    cells = [c for c in by_cell if c.dgp == dgp]
    classifications = [_cell_classification(c.passthrough_share_of_false_edges) for c in cells]
    n_material = sum(1 for c in classifications if c == "material")
    n_partial = sum(1 for c in classifications if c == "partial")
    n_minimal = sum(1 for c in classifications if c == "minimal")
    n_tested = len(cells)

    if n_material >= _MAJORITY_THRESHOLD:
        reading = f"MATERIAL: passthrough-unconditioned edges are a majority of MINT's own false positives at {n_material}/{n_tested} tested N"
    elif (n_material + n_partial) >= _MAJORITY_THRESHOLD:
        reading = f"PARTIAL: passthrough-unconditioned edges are a non-trivial but non-majority contributor at a majority of tested N ({n_material} material + {n_partial} partial of {n_tested})"
    else:
        reading = f"MINIMAL: passthrough-unconditioned edges are not a material contributor at a majority of tested N ({n_minimal}/{n_tested} minimal)"

    return ShapeReading(dgp, n_material, n_partial, n_minimal, n_tested, reading)


def evaluate_stage5f(raw: pd.DataFrame, config: Stage5fConfig) -> Stage5fReport:
    by_cell = tuple(summarize_cell(raw, dgp, n) for dgp in DGPS for n in config.sample_sizes)
    by_shape = tuple(_shape_reading(dgp, by_cell) for dgp in DGPS)
    return Stage5fReport(by_cell, by_shape)


def write_stage5f_report(raw: pd.DataFrame, config: Stage5fConfig, output_dir: Path) -> Stage5fReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage5f(raw, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {"by_cell": [asdict(c) for c in report.by_cell], "by_shape": [asdict(s) for s in report.by_shape]},
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )

    def fmt(value: float | None) -> str:
        return "None (no false edges)" if value is None else f"{value:.4f}"

    sections = [
        "# Stage 5f Diagnostic Report -- Passthrough-Unconditioned False Edges (R6)\n",
        "Tests whether MINT's DPI step's clique-shape scope (only conditions within "
        "validated 3/4/5-node candidate components) is a material source of MINT's own "
        "residual false positives on the two composed noisy networks. No algorithm change; "
        "pure post-hoc attribution of `compose_screen_then_prune`'s own unmodified output.\n",
        "## Per-shape reading\n",
        "| DGP shape | material | partial | minimal | Reading |",
        "|---|---|---|---|---|",
    ]
    for shape in report.by_shape:
        sections.append(
            f"| {shape.dgp} | {shape.n_material}/{shape.n_tested} | {shape.n_partial}/{shape.n_tested} | "
            f"{shape.n_minimal}/{shape.n_tested} | {shape.reading} |"
        )
    sections.append("")

    for dgp in DGPS:
        rows = [
            f"## {dgp}\n",
            "| N | DPI-conditioned true | DPI-conditioned false | passthrough true | passthrough false | "
            "passthrough share of false | errors |",
            "|---|---|---|---|---|---|---|",
        ]
        for n in config.sample_sizes:
            cell = next(c for c in report.by_cell if c.dgp == dgp and c.n == n)
            rows.append(
                f"| {n} | {cell.dpi_conditioned_true_edge} | {cell.dpi_conditioned_false_edge} | "
                f"{cell.passthrough_true_edge} | {cell.passthrough_false_edge} | "
                f"{fmt(cell.passthrough_share_of_false_edges)} | {cell.n_errors} |"
            )
        sections.append("\n".join(rows) + "\n")

    sections.append(
        "Descriptive attribution, not a validation gate or a fix -- see `docs/stage5f_charter.md`'s own "
        "decision structure and non-goals. See `raw_metrics.csv`, `report.json`, and `resolved_config.yaml` "
        "for complete evidence.\n"
    )
    (output_dir / "stage5f_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


write_report = write_stage5f_report
