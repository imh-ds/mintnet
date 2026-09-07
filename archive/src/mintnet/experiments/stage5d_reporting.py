"""Evidence rendering for the Stage 5d signal-strength sweep. See
docs/stage5d_charter.md.

No confirm/refute branch (this charter has no sharp a priori
prediction, unlike Stage 5b/5c) -- instead this module classifies each
(dgp, N) series' own F1-gap trend across ascending strength
(increasing / decreasing / flat / non-monotonic) and separately checks,
explicitly and independently of that trend, whether recall stayed at
`1.0` for both methods everywhere -- the charter's own predeclared
reporting requirement that this get its own sentence regardless of the
trend finding.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage5d import DGPS, METHODS, Stage5dConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_GAP_TOLERANCE = 0.01  # F1 points, same sampling-noise tolerance as Stage 5b/5c
_RECALL_FLOOR = 0.999  # below this counts as "recall dropped," not float noise


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class CellSummary:
    dgp: str
    method: str
    n: int
    strength: float
    status: str
    precision: float | None
    recall: float | None
    f1: float | None
    shd: float | None
    mean_runtime_seconds: float | None
    n_errors: int


@dataclass(frozen=True)
class GapPoint:
    dgp: str
    n: int
    strength: float
    mint_f1: float | None
    ebicglasso_f1: float | None
    gap: float | None
    mint_recall: float | None
    ebicglasso_recall: float | None


@dataclass(frozen=True)
class SeriesTrend:
    dgp: str
    n: int
    trend: str


@dataclass(frozen=True)
class Stage5dReport:
    by_cell: tuple[CellSummary, ...]
    gap_by_condition: tuple[GapPoint, ...]
    trends: tuple[SeriesTrend, ...]
    recall_holds: bool
    recall_note: str


def summarize_cell(
    raw: pd.DataFrame, dgp: str, method: str, n: int, strength: float, config: Stage5dConfig
) -> CellSummary:
    cell_raw = raw.loc[
        (raw["dgp"] == dgp) & (raw["method"] == method) & (raw["n"] == n) & (raw["strength"] == strength)
    ]
    validation = _partition(cell_raw, config.validation_replicates)
    n_errors = int((validation["status"] != "ok").sum())
    ok = validation.loc[validation["status"] == "ok"]

    if ok.empty:
        return CellSummary(dgp, method, n, strength, "no valid replicates", None, None, None, None, None, n_errors)

    return CellSummary(
        dgp,
        method,
        n,
        strength,
        "ok",
        float(ok["precision"].mean()),
        float(ok["recall"].mean()),
        float(ok["f1"].mean()),
        float(ok["shd"].mean()),
        float(ok["elapsed_seconds"].mean()),
        n_errors,
    )


def _gap_points(by_cell: tuple[CellSummary, ...], config: Stage5dConfig) -> tuple[GapPoint, ...]:
    points = []
    for dgp in DGPS:
        for n in config.sample_sizes:
            for strength in config.strengths:
                mint = next(c for c in by_cell if c.dgp == dgp and c.method == "mint" and c.n == n and c.strength == strength)
                ebic = next(c for c in by_cell if c.dgp == dgp and c.method == "ebicglasso" and c.n == n and c.strength == strength)
                gap = (mint.f1 - ebic.f1) if (mint.f1 is not None and ebic.f1 is not None) else None
                points.append(GapPoint(dgp, n, strength, mint.f1, ebic.f1, gap, mint.recall, ebic.recall))
    return tuple(points)


def _classify_trend(values: list[float]) -> str:
    diffs = [b - a for a, b in zip(values, values[1:])]
    if all(abs(d) <= _GAP_TOLERANCE for d in diffs):
        return "flat"
    if all(d >= -_GAP_TOLERANCE for d in diffs) and any(d > _GAP_TOLERANCE for d in diffs):
        return "increasing"
    if all(d <= _GAP_TOLERANCE for d in diffs) and any(d < -_GAP_TOLERANCE for d in diffs):
        return "decreasing"
    return "non-monotonic"


def _trends(gap_by_condition: tuple[GapPoint, ...], config: Stage5dConfig) -> tuple[SeriesTrend, ...]:
    trends = []
    for dgp in DGPS:
        for n in config.sample_sizes:
            series = sorted(
                (p for p in gap_by_condition if p.dgp == dgp and p.n == n), key=lambda p: p.strength
            )
            values = [p.gap for p in series if p.gap is not None]
            trends.append(SeriesTrend(dgp, n, _classify_trend(values) if len(values) >= 2 else "insufficient data"))
    return tuple(trends)


def _recall_check(by_cell: tuple[CellSummary, ...]) -> tuple[bool, str]:
    drops = [c for c in by_cell if c.recall is not None and c.recall < _RECALL_FLOOR]
    if not drops:
        return True, "Recall stayed at 1.0 for both methods in every cell -- the entire measured gap remains a precision (false-edge) question, as in every prior R6 charter."
    detail = "; ".join(f"{c.dgp}/{c.method}/N={c.n}/strength={c.strength}: recall={c.recall:.4f}" for c in drops)
    return False, f"Recall dropped below 1.0 in {len(drops)} cell(s), new to this R6 arc: {detail}"


def evaluate_stage5d(raw: pd.DataFrame, config: Stage5dConfig) -> Stage5dReport:
    by_cell = tuple(
        summarize_cell(raw, dgp, method, n, strength, config)
        for dgp in DGPS
        for n in config.sample_sizes
        for strength in config.strengths
        for method in METHODS
    )
    gap_by_condition = _gap_points(by_cell, config)
    trends = _trends(gap_by_condition, config)
    recall_holds, recall_note = _recall_check(by_cell)
    return Stage5dReport(by_cell, gap_by_condition, trends, recall_holds, recall_note)


def _plot_gap_by_strength(report: Stage5dReport, config: Stage5dConfig, path: Path) -> None:
    figure, axes = plt.subplots(1, len(DGPS), figsize=(6 * len(DGPS), 4.5), sharey=True)
    for axis, dgp in zip(axes, DGPS):
        for n in config.sample_sizes:
            series = sorted(
                (p for p in report.gap_by_condition if p.dgp == dgp and p.n == n), key=lambda p: p.strength
            )
            axis.plot([p.strength for p in series], [p.gap for p in series], marker="o", label=f"N={n}")
        axis.axhline(0.0, color="gray", linestyle=":", linewidth=0.8)
        axis.set_title(dgp)
        axis.set_xlabel("Signal strength")
    axes[0].set_ylabel("MINT F1 - EBICglasso F1")
    axes[-1].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage5d_report(raw: pd.DataFrame, config: Stage5dConfig, output_dir: Path) -> Stage5dReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage5d(raw, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "recall_holds": report.recall_holds,
                "recall_note": report.recall_note,
                "trends": [asdict(t) for t in report.trends],
                "by_cell": [asdict(c) for c in report.by_cell],
                "gap_by_condition": [asdict(g) for g in report.gap_by_condition],
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_gap_by_strength(report, config, output_dir / "gap_by_strength.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = [
        "# Stage 5d Signal-Strength Sweep Report (R6)\n",
        f"**Recall check: {report.recall_note}**\n",
        "No confirm/refute branch (exploratory axis, per `docs/stage5d_charter.md`'s own \"no strong "
        "directional prediction\" section) -- instead, the F1-gap trend is classified per (dgp, N) "
        "series across ascending strength.\n",
        "## F1-gap trend by (dgp, N)\n",
        "| DGP shape | N | trend |",
        "|---|---|---|",
    ]
    for trend in report.trends:
        sections.append(f"| {trend.dgp} | {trend.n} | {trend.trend} |")
    sections.append("")

    sections.append("## F1 gap by strength\n")
    sections.append("| DGP shape | N | strength | MINT F1 | MINT recall | EBICglasso F1 | EBICglasso recall | gap |")
    sections.append("|---|---|---|---|---|---|---|---|")
    for point in report.gap_by_condition:
        sections.append(
            f"| {point.dgp} | {point.n} | {point.strength} | {fmt(point.mint_f1)} | {fmt(point.mint_recall)} | "
            f"{fmt(point.ebicglasso_f1)} | {fmt(point.ebicglasso_recall)} | {fmt(point.gap)} |"
        )
    sections.append("")

    for dgp in DGPS:
        rows = [
            f"## {dgp}\n",
            "| N | strength | method | precision | recall | F1 | SHD | mean runtime (s) | errors |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for n in config.sample_sizes:
            for strength in config.strengths:
                for method in METHODS:
                    cell = next(
                        c for c in report.by_cell
                        if c.dgp == dgp and c.method == method and c.n == n and c.strength == strength
                    )
                    rows.append(
                        f"| {n} | {strength} | {method} | {fmt(cell.precision)} | {fmt(cell.recall)} | "
                        f"{fmt(cell.f1)} | {fmt(cell.shd)} | {fmt(cell.mean_runtime_seconds)} | {cell.n_errors} |"
                    )
        sections.append("\n".join(rows) + "\n")

    sections.append(
        "Descriptive result, not a validation gate -- see `docs/stage5d_charter.md`'s own decision "
        "structure. See `raw_metrics.csv`, `report.json`, `resolved_config.yaml`, and "
        "`gap_by_strength.png` for complete evidence.\n"
    )
    (output_dir / "stage5d_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


write_report = write_stage5d_report
