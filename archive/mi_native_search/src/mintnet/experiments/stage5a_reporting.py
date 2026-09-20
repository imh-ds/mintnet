"""Evidence rendering and the predeclared descriptive verdict for the
Stage 5a comparator benchmark. See docs/stage5a_charter.md.

Implementation-time clarification, made before any evidence exists: the
charter's own "Decision structure" section required stating, per shape,
which method reaches "acceptable recovery (F1, SHD within the shape's
own already-established acceptable range)" at materially lower N,
without pinning one exact number. This module fixes that number now,
before results are generated: **mean validation-replicate F1 >= 0.90**.
This mirrors the F1 threshold's own standing elsewhere in this project
as a strict-but-conventional structure-recovery bar, and is fixed here
rather than chosen after seeing which threshold makes either method
look better.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage5a import DGPS, METHODS, Stage5aConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

ACCEPTABLE_F1: float = 0.90


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class CellSummary:
    dgp: str
    method: str
    n: int
    status: str
    precision: float | None
    recall: float | None
    f1: float | None
    shd: float | None
    n_estimated_edges: float | None
    mean_runtime_seconds: float | None
    n_errors: int


@dataclass(frozen=True)
class ShapeVerdict:
    dgp: str
    mint_threshold_n: int | None
    ebicglasso_threshold_n: int | None
    verdict: str


@dataclass(frozen=True)
class Stage5aReport:
    by_cell: tuple[CellSummary, ...]
    by_shape: tuple[ShapeVerdict, ...]


def summarize_cell(raw: pd.DataFrame, dgp: str, method: str, n: int, config: Stage5aConfig) -> CellSummary:
    cell_raw = raw.loc[(raw["dgp"] == dgp) & (raw["method"] == method) & (raw["n"] == n)]
    validation = _partition(cell_raw, config.validation_replicates)
    n_errors = int((validation["status"] != "ok").sum())
    ok = validation.loc[validation["status"] == "ok"]

    if ok.empty:
        return CellSummary(dgp, method, n, "no valid replicates", None, None, None, None, None, None, n_errors)

    return CellSummary(
        dgp,
        method,
        n,
        "ok",
        float(ok["precision"].mean()),
        float(ok["recall"].mean()),
        float(ok["f1"].mean()),
        float(ok["shd"].mean()),
        float(ok["n_estimated_edges"].mean()),
        float(ok["elapsed_seconds"].mean()),
        n_errors,
    )


def _threshold_n(cells: tuple[CellSummary, ...]) -> int | None:
    """Smallest N (in ascending order) at which mean F1 first reaches
    and holds ACCEPTABLE_F1 at every larger tested N -- a monotone
    "floor," not just the first N that happens to clear it in isolation."""
    ordered = sorted((c for c in cells if c.f1 is not None), key=lambda c: c.n)
    for index, cell in enumerate(ordered):
        if all(later.f1 is not None and later.f1 >= ACCEPTABLE_F1 for later in ordered[index:]):
            return cell.n
    return None


def _shape_verdict(dgp: str, by_cell: tuple[CellSummary, ...]) -> ShapeVerdict:
    mint_cells = tuple(c for c in by_cell if c.dgp == dgp and c.method == "mint")
    ebic_cells = tuple(c for c in by_cell if c.dgp == dgp and c.method == "ebicglasso")
    mint_n = _threshold_n(mint_cells)
    ebic_n = _threshold_n(ebic_cells)

    if mint_n is None and ebic_n is None:
        verdict = "neither method reaches acceptable recovery on the tested grid"
    elif mint_n is None:
        verdict = "EBICglasso reaches acceptable recovery; MINT does not on the tested grid"
    elif ebic_n is None:
        verdict = "MINT reaches acceptable recovery; EBICglasso does not on the tested grid"
    elif mint_n < ebic_n:
        verdict = f"MINT more sample-efficient (floor N={mint_n} vs EBICglasso N={ebic_n})"
    elif ebic_n < mint_n:
        verdict = f"EBICglasso more sample-efficient (floor N={ebic_n} vs MINT N={mint_n})"
    else:
        verdict = f"no material difference (both floor at N={mint_n})"

    return ShapeVerdict(dgp, mint_n, ebic_n, verdict)


def evaluate_stage5a(raw: pd.DataFrame, config: Stage5aConfig) -> Stage5aReport:
    by_cell = tuple(
        summarize_cell(raw, dgp, method, n, config)
        for dgp in DGPS
        for method in METHODS
        for n in config.sample_sizes
    )
    by_shape = tuple(_shape_verdict(dgp, by_cell) for dgp in DGPS)
    return Stage5aReport(by_cell, by_shape)


def _plot_f1_by_shape(report: Stage5aReport, sample_sizes: tuple[int, ...], path: Path) -> None:
    figure, axes = plt.subplots(1, len(DGPS), figsize=(5.5 * len(DGPS), 4.5), sharey=True)
    for axis, dgp in zip(axes, DGPS):
        for method, marker in (("mint", "o"), ("ebicglasso", "s")):
            cells = sorted((c for c in report.by_cell if c.dgp == dgp and c.method == method), key=lambda c: c.n)
            axis.plot([c.n for c in cells], [c.f1 for c in cells], marker=marker, label=method)
        axis.axhline(ACCEPTABLE_F1, color="gray", linestyle=":", linewidth=0.8)
        axis.set_title(dgp)
        axis.set_xlabel("N")
        axis.set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Mean validation F1")
    axes[-1].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage5a_report(raw: pd.DataFrame, config: Stage5aConfig, output_dir: Path) -> Stage5aReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage5a(raw, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "acceptable_f1": ACCEPTABLE_F1,
                "by_cell": [asdict(c) for c in report.by_cell],
                "by_shape": [asdict(s) for s in report.by_shape],
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_f1_by_shape(report, config.sample_sizes, output_dir / "f1_by_n_by_shape.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = [
        "# Stage 5a Comparator Benchmark Report -- MINT vs. EBICglasso (R6)\n",
        f"Acceptable-recovery threshold fixed before results: mean validation F1 >= "
        f"`{ACCEPTABLE_F1:.2f}`, held at every larger tested N (a monotone floor, not an "
        f"isolated crossing). MINT uses D-012's general `alpha(N)` formula uniformly across "
        f"all five shapes (see `stage5a.py`'s own module docstring for why overlap's "
        f"specialized formula was not reproduced here). EBICglasso uses `gamma="
        f"{config.ebicglasso_gamma}` throughout, `qgraph`'s own package default.\n",
    ]

    sections.append("## Per-shape verdict\n")
    sections.append("| DGP shape | MINT floor N | EBICglasso floor N | Verdict |")
    sections.append("|---|---|---|---|")
    for shape in report.by_shape:
        sections.append(
            f"| {shape.dgp} | {shape.mint_threshold_n if shape.mint_threshold_n is not None else 'none'} | "
            f"{shape.ebicglasso_threshold_n if shape.ebicglasso_threshold_n is not None else 'none'} | "
            f"{shape.verdict} |"
        )
    sections.append("")

    for dgp in DGPS:
        rows = [
            f"## {dgp}\n",
            "| N | method | precision | recall | F1 | SHD | mean runtime (s) | errors |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for n in config.sample_sizes:
            for method in METHODS:
                cell = next(c for c in report.by_cell if c.dgp == dgp and c.method == method and c.n == n)
                rows.append(
                    f"| {n} | {method} | {fmt(cell.precision)} | {fmt(cell.recall)} | {fmt(cell.f1)} | "
                    f"{fmt(cell.shd)} | {fmt(cell.mean_runtime_seconds)} | {cell.n_errors} |"
                )
        sections.append("\n".join(rows) + "\n")

    sections.append(
        "No claim of superiority is made or implied by this table -- per "
        "`docs/stage5a_charter.md`'s own non-goals, a mixed picture is a complete answer. "
        "See `raw_metrics.csv`, `report.json`, `resolved_config.yaml`, and "
        "`f1_by_n_by_shape.png` for complete evidence.\n"
    )
    (output_dir / "stage5a_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


# Generic name expected by scripts/aggregate_shards.py's own shard-
# aggregation contract (see stage5a.py's own "Generic shard-aggregation
# contract" comment).
write_report = write_stage5a_report
