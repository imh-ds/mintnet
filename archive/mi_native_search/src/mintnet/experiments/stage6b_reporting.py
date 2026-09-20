"""Evidence rendering and the predeclared descriptive gate for the
Stage 6b conditional-MI estimator validation. See docs/stage6b_charter.md.

Implementation-time scope note: this first pass reports Type-I error
control and power (the charter's own primary gate -- an uncalibrated
test is untrustworthy regardless of point-estimate accuracy) for every
condition/N/alpha cell. Full bias/RMSE against the analytic Gaussian
reference for every condition is reserved for a follow-up once this
pass's Type-I-error result is known, per stage6b.py's own disclosed
scope reduction.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6b import CONDITIONS, Stage6bConfig

# Type-I error tolerance bands, mirroring docs/stage6b_charter.md's own
# criterion 4 (fixed there, restated here for the report's own use).
_TYPE_I_BANDS: dict[float, tuple[float, float]] = {0.05: (0.03, 0.07), 0.01: (0.005, 0.015)}
_POWER_THRESHOLD = 0.80


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class CellSummary:
    label: str
    s: int
    kind: str
    n: int
    n_errors: int
    mean_estimate: float | None
    rejection_rate_by_alpha: dict[float, float]


@dataclass(frozen=True)
class Stage6bReport:
    by_cell: tuple[CellSummary, ...]
    type_i_error_holds: bool
    power_holds: bool
    reading: str


def _condition_kind(label: str) -> str:
    return "null" if label.endswith("_null") else "alt"


def summarize_cell(raw: pd.DataFrame, label: str, s: int, n: int, config: Stage6bConfig) -> CellSummary:
    cell_raw = raw.loc[(raw["label"] == label) & (raw["n"] == n)]
    validation = _partition(cell_raw, config.validation_replicates)
    n_errors = int((validation["status"] != "ok").sum())
    ok = validation.loc[validation["status"] == "ok"]

    if ok.empty:
        return CellSummary(label, s, _condition_kind(label), n, n_errors, None, {a: float("nan") for a in config.alphas})

    rejection_rates = {alpha: float((ok["p_value"] <= alpha).mean()) for alpha in config.alphas}
    return CellSummary(label, s, _condition_kind(label), n, n_errors, float(ok["estimate"].mean()), rejection_rates)


def evaluate_stage6b(raw: pd.DataFrame, config: Stage6bConfig) -> Stage6bReport:
    by_cell = tuple(
        summarize_cell(raw, condition["label"], int(condition["s"]), n, config)  # type: ignore[index]
        for condition in CONDITIONS
        for n in config.sample_sizes
    )

    type_i_holds = True
    for cell in by_cell:
        if cell.kind != "null":
            continue
        for alpha, rate in cell.rejection_rate_by_alpha.items():
            band = _TYPE_I_BANDS.get(alpha)
            if band is None or rate != rate:  # NaN check
                continue
            if not (band[0] <= rate <= band[1]):
                type_i_holds = False

    power_holds = True
    for cell in by_cell:
        if cell.kind != "alt":
            continue
        rate = cell.rejection_rate_by_alpha.get(0.05)
        if rate is None or rate != rate:
            continue
        if rate < _POWER_THRESHOLD:
            power_holds = False

    if type_i_holds and power_holds:
        reading = "PROCEED (first-pass grid): Type-I error controlled and power adequate at every tested condition/N/alpha."
    elif not type_i_holds:
        reading = (
            "REASSESS -- Type-I error control fails at one or more condition/N/alpha cells. This blocks the "
            "whole mi-native track per the charter's own consequences section, regardless of power."
        )
    else:
        reading = "REASSESS -- Type-I error holds but power is inadequate at one or more alt conditions/N."

    return Stage6bReport(by_cell, type_i_holds, power_holds, reading)


def write_stage6b_report(raw: pd.DataFrame, config: Stage6bConfig, output_dir: Path) -> Stage6bReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage6b(raw, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "type_i_error_holds": report.type_i_error_holds,
                "power_holds": report.power_holds,
                "reading": report.reading,
                "by_cell": [asdict(c) for c in report.by_cell],
            },
            indent=2, allow_nan=True,
        ) + "\n",
        encoding="utf-8",
    )

    def fmt(value: float | None) -> str:
        return "None" if value is None or value != value else f"{value:.4f}"

    sections = [
        "# Stage 6b Conditional-MI Estimator Validation Report (mi-native)\n",
        f"**Reading: {report.reading}**\n",
        "Reduced first-pass grid (see stage6b.py's own module docstring for the measured timing that "
        "motivated this) -- N up to 750, not the charter's own full grid up to 1500. Extending the grid "
        "is a natural follow-up once this pass's Type-I-error result is known, not a substitute for it.\n",
        "## Type-I error and power, per condition\n",
        "| label | |S| | kind | N | mean estimate | reject@.05 | reject@.01 | errors |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cell in report.by_cell:
        r05 = cell.rejection_rate_by_alpha.get(0.05)
        r01 = cell.rejection_rate_by_alpha.get(0.01)
        sections.append(
            f"| {cell.label} | {cell.s} | {cell.kind} | {cell.n} | {fmt(cell.mean_estimate)} | "
            f"{fmt(r05)} | {fmt(r01)} | {cell.n_errors} |"
        )
    sections.append("")

    sections.append(
        "Type-I error band (null conditions): `[.03, .07]` at alpha=.05, `[.005, .015]` at alpha=.01. "
        "Power threshold (alt conditions): `>= .80` at alpha=.05. See `docs/stage6b_charter.md`'s own "
        "selection-and-gate section for the frozen criteria.\n"
    )
    sections.append(
        "Descriptive validation of the estimator and test alone -- no DPI, screening, or pipeline "
        "change. See `raw_metrics.csv`, `report.json`, and `resolved_config.yaml` for complete evidence.\n"
    )
    (output_dir / "stage6b_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


write_report = write_stage6b_report
