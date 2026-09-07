"""Evidence rendering and the predeclared descriptive reading for the
Stage 5b noise-column-count stress test. See docs/stage5b_charter.md.

The charter's own predeclared reading: the mechanism is *confirmed* if
the MINT-minus-EBICglasso F1 gap is non-decreasing in noise multiplier
(allowing ordinary sampling noise) at both tested N, for both shapes;
*complicated* otherwise. This module computes that gap directly and
states which reading the evidence supports -- fixed before any
evidence exists, per the charter's own decision structure.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage5b import DGPS, METHODS, Stage5bConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class CellSummary:
    dgp: str
    method: str
    n: int
    noise_multiplier: int
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
    noise_multiplier: int
    mint_f1: float | None
    ebicglasso_f1: float | None
    gap: float | None


@dataclass(frozen=True)
class Stage5bReport:
    by_cell: tuple[CellSummary, ...]
    gap_by_condition: tuple[GapPoint, ...]
    monotone_non_decreasing: bool
    reading: str


def summarize_cell(
    raw: pd.DataFrame, dgp: str, method: str, n: int, multiplier: int, config: Stage5bConfig
) -> CellSummary:
    cell_raw = raw.loc[
        (raw["dgp"] == dgp) & (raw["method"] == method) & (raw["n"] == n) & (raw["noise_multiplier"] == multiplier)
    ]
    validation = _partition(cell_raw, config.validation_replicates)
    n_errors = int((validation["status"] != "ok").sum())
    ok = validation.loc[validation["status"] == "ok"]

    if ok.empty:
        return CellSummary(dgp, method, n, multiplier, "no valid replicates", None, None, None, None, None, n_errors)

    return CellSummary(
        dgp,
        method,
        n,
        multiplier,
        "ok",
        float(ok["precision"].mean()),
        float(ok["recall"].mean()),
        float(ok["f1"].mean()),
        float(ok["shd"].mean()),
        float(ok["elapsed_seconds"].mean()),
        n_errors,
    )


def _gap_points(by_cell: tuple[CellSummary, ...], config: Stage5bConfig) -> tuple[GapPoint, ...]:
    points = []
    for dgp in DGPS:
        for n in config.sample_sizes:
            for multiplier in config.noise_multipliers:
                mint = next(c for c in by_cell if c.dgp == dgp and c.method == "mint" and c.n == n and c.noise_multiplier == multiplier)
                ebic = next(c for c in by_cell if c.dgp == dgp and c.method == "ebicglasso" and c.n == n and c.noise_multiplier == multiplier)
                gap = (mint.f1 - ebic.f1) if (mint.f1 is not None and ebic.f1 is not None) else None
                points.append(GapPoint(dgp, n, multiplier, mint.f1, ebic.f1, gap))
    return tuple(points)


def _is_monotone_non_decreasing(gap_by_condition: tuple[GapPoint, ...], config: Stage5bConfig) -> bool:
    """Per (dgp, N) series across ascending noise multiplier, the gap
    must never decrease by more than a small sampling-noise tolerance."""
    tolerance = 0.01  # one percentage point of F1, allowing ordinary sampling noise
    for dgp in DGPS:
        for n in config.sample_sizes:
            series = sorted(
                (p for p in gap_by_condition if p.dgp == dgp and p.n == n), key=lambda p: p.noise_multiplier
            )
            values = [p.gap for p in series if p.gap is not None]
            for previous, current in zip(values, values[1:]):
                if current < previous - tolerance:
                    return False
    return True


def evaluate_stage5b(raw: pd.DataFrame, config: Stage5bConfig) -> Stage5bReport:
    by_cell = tuple(
        summarize_cell(raw, dgp, method, n, multiplier, config)
        for dgp in DGPS
        for n in config.sample_sizes
        for multiplier in config.noise_multipliers
        for method in METHODS
    )
    gap_by_condition = _gap_points(by_cell, config)
    monotone = _is_monotone_non_decreasing(gap_by_condition, config)
    reading = (
        "CONFIRMS the mechanism: the MINT-minus-EBICglasso F1 gap is non-decreasing in noise "
        "multiplier (within sampling tolerance) at every tested (dgp, N)."
        if monotone
        else "COMPLICATES the mechanism: the F1 gap decreases with noise multiplier at at least one "
        "(dgp, N) condition beyond sampling tolerance -- D-047's noise-column-count explanation needs "
        "its own diagnosis before further R6 charters build on it."
    )
    return Stage5bReport(by_cell, gap_by_condition, monotone, reading)


def _plot_gap_by_multiplier(report: Stage5bReport, config: Stage5bConfig, path: Path) -> None:
    figure, axes = plt.subplots(1, len(DGPS), figsize=(6 * len(DGPS), 4.5), sharey=True)
    for axis, dgp in zip(axes, DGPS):
        for n in config.sample_sizes:
            series = sorted(
                (p for p in report.gap_by_condition if p.dgp == dgp and p.n == n), key=lambda p: p.noise_multiplier
            )
            axis.plot([p.noise_multiplier for p in series], [p.gap for p in series], marker="o", label=f"N={n}")
        axis.axhline(0.0, color="gray", linestyle=":", linewidth=0.8)
        axis.set_title(dgp)
        axis.set_xlabel("Noise multiplier (x native noise-column count)")
    axes[0].set_ylabel("MINT F1 - EBICglasso F1")
    axes[-1].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage5b_report(raw: pd.DataFrame, config: Stage5bConfig, output_dir: Path) -> Stage5bReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage5b(raw, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "monotone_non_decreasing": report.monotone_non_decreasing,
                "reading": report.reading,
                "by_cell": [asdict(c) for c in report.by_cell],
                "gap_by_condition": [asdict(g) for g in report.gap_by_condition],
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_gap_by_multiplier(report, config, output_dir / "gap_by_noise_multiplier.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = [
        "# Stage 5b Noise-Column-Count Stress Test Report (R6)\n",
        f"**Reading: {report.reading}**\n",
        "Extends D-047's own two composed, noisy p=15 networks by appending extra independent "
        "standard-normal noise columns (multiplier x each shape's own native noise-column count) "
        "while holding strength (`.5`), MINT's alpha(N), and EBICglasso's gamma unchanged from "
        "`docs/stage5a_charter.md`.\n",
        "## F1 gap by noise multiplier\n",
        "| DGP shape | N | noise multiplier | MINT F1 | EBICglasso F1 | gap (MINT - EBICglasso) |",
        "|---|---|---|---|---|---|",
    ]
    for point in report.gap_by_condition:
        sections.append(
            f"| {point.dgp} | {point.n} | {point.noise_multiplier} | {fmt(point.mint_f1)} | "
            f"{fmt(point.ebicglasso_f1)} | {fmt(point.gap)} |"
        )
    sections.append("")

    for dgp in DGPS:
        rows = [
            f"## {dgp}\n",
            "| N | noise multiplier | method | precision | recall | F1 | SHD | mean runtime (s) | errors |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for n in config.sample_sizes:
            for multiplier in config.noise_multipliers:
                for method in METHODS:
                    cell = next(
                        c for c in report.by_cell
                        if c.dgp == dgp and c.method == method and c.n == n and c.noise_multiplier == multiplier
                    )
                    rows.append(
                        f"| {n} | {multiplier} | {method} | {fmt(cell.precision)} | {fmt(cell.recall)} | "
                        f"{fmt(cell.f1)} | {fmt(cell.shd)} | {fmt(cell.mean_runtime_seconds)} | {cell.n_errors} |"
                    )
        sections.append("\n".join(rows) + "\n")

    sections.append(
        "Descriptive result, not a validation gate -- see `docs/stage5b_charter.md`'s own decision "
        "structure. See `raw_metrics.csv`, `report.json`, `resolved_config.yaml`, and "
        "`gap_by_noise_multiplier.png` for complete evidence.\n"
    )
    (output_dir / "stage5b_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


write_report = write_stage5b_report
