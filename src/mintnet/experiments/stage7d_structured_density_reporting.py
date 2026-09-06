"""Two-stage analysis for Stage 7d's structured-density degree sweep.
Descriptive/diagnostic only -- no single PROCEED/REASSESS gate, but a
real filter (Stage A) that determines which `degree` values' own power
numbers (Stage B) are even meaningful, mirroring Stage 7c's own
treatment of `k_CMI`. See docs/stage7d_charter.md.

The head-to-head comparison against the CMIknn baseline is NOT done
here -- that requires this run's own artifact plus
`mintnet.experiments.stage7d_cmiknn_baseline`'s own separate artifact,
and lives in `scripts/stage7d_compare.py` instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6c_reporting import wilson_ci
from mintnet.experiments.stage7d_conditions import condition_label
from mintnet.experiments.stage7d_frontier import family_detection_limit
from mintnet.experiments.stage7d_structured_density import Stage7dStructuredDensityConfig

_TYPE_I_BANDS: dict[float, tuple[float, float]] = {0.05: (0.03, 0.07), 0.01: (0.005, 0.015)}
_NULL_CONDITION = condition_label("linear", 0.0)


def stage_a_calibration_filter(raw: pd.DataFrame, config: Stage7dStructuredDensityConfig) -> pd.DataFrame:
    """Per (degree, n, alpha in {.05,.01}), at the shared `linear_0.0`
    null: rejection rate, Wilson 95% CI, and whether it's defensible
    (in band or CI overlaps nominal) -- D-056's own criterion, applied
    here to `degree`."""
    rows: list[dict[str, object]] = []
    for degree in config.degrees:
        for n in config.sample_sizes:
            cell = raw.loc[
                (raw["degree"] == degree) & (raw["condition"] == _NULL_CONDITION)
                & (raw["n"] == n) & (raw["status"] == "ok")
            ]
            total = len(cell)
            for alpha, band in _TYPE_I_BANDS.items():
                if total == 0:
                    rows.append(
                        {"degree": degree, "n": n, "alpha": alpha, "rejections": 0, "total": 0,
                         "rate": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"), "defensible": False}
                    )
                    continue
                rejections = int((cell["p_value_12"] <= alpha).sum())
                rate = rejections / total
                ci_low, ci_high = wilson_ci(rejections, total)
                in_band = band[0] <= rate <= band[1]
                overlaps = ci_low <= alpha <= ci_high
                rows.append(
                    {
                        "degree": degree, "n": n, "alpha": alpha, "rejections": rejections, "total": total,
                        "rate": rate, "ci_low": ci_low, "ci_high": ci_high, "defensible": bool(in_band or overlaps),
                    }
                )
    return pd.DataFrame(rows)


def calibrated_degrees(stage_a: pd.DataFrame, config: Stage7dStructuredDensityConfig) -> list[int]:
    """`degree` values defensible across EVERY tested N and alpha -- the
    same all-cells-must-pass discipline D-056/Stage 7c used."""
    survivors = []
    for degree in config.degrees:
        cell = stage_a.loc[stage_a["degree"] == degree]
        if len(cell) > 0 and cell["defensible"].all():
            survivors.append(degree)
    return survivors


def stage_b_detection_limits(raw: pd.DataFrame, config: Stage7dStructuredDensityConfig, survivors: list[int]) -> pd.DataFrame:
    """Per calibrated degree, per N, per DGP family: detection limit --
    see `mintnet.experiments.stage7d_frontier.family_detection_limit`."""
    rows: list[dict[str, object]] = []
    for degree in survivors:
        for n in config.sample_sizes:
            limits = family_detection_limit(
                raw, condition_column="condition", p_value_column="p_value_12", n=n,
                group_filter=raw["degree"] == degree,
            )
            for family, limit in limits.items():
                rows.append({"degree": degree, "n": n, "family": family, "detection_limit": limit})
    return pd.DataFrame(rows)


def write_report(raw: pd.DataFrame, config: Stage7dStructuredDensityConfig, output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_a = stage_a_calibration_filter(raw, config)
    stage_a.to_csv(output_dir / "stage_a_calibration.csv", index=False)

    survivors = calibrated_degrees(stage_a, config)
    stage_b = stage_b_detection_limits(raw, config, survivors)
    stage_b.to_csv(output_dir / "stage_b_detection_limits.csv", index=False)

    n_errors = int((raw["status"] != "ok").sum())

    lines = [
        "# Stage 7d Structured-Density Report (mi-native)\n",
        "Descriptive/diagnostic -- no single PROCEED/REASSESS gate. Stage A filters which "
        "`degree` values remain calibrated; Stage B reports detection limits per DGP family "
        "for calibrated survivors. The head-to-head comparison against the CMIknn baseline "
        "is produced separately by `scripts/stage7d_compare.py`, once both artifacts exist.\n",
        f"Errors: {n_errors}\n",
        f"**Calibrated degree values (survived Stage A): {survivors}**\n",
        "## Stage A: calibration filter (every N x alpha must pass)\n",
        "| degree | defensible everywhere |",
        "|---|---|",
    ]
    for degree in config.degrees:
        cell = stage_a.loc[stage_a["degree"] == degree]
        lines.append(f"| {degree} | {bool(cell['defensible'].all()) if len(cell) else False} |")
    lines.append("")
    lines.append("## Stage B: detection limit per DGP family, calibrated survivors only\n")
    lines.append("| degree | N | family | detection limit |")
    lines.append("|---|---|---|---|")
    for _, row in stage_b.iterrows():
        limit = "not reached" if row["detection_limit"] is None else row["detection_limit"]
        lines.append(f"| {row.degree} | {row.n} | {row.family} | {limit} |")
    lines.append("")
    lines.append(
        "See `stage_a_calibration.csv` and `stage_b_detection_limits.csv` for complete evidence.\n"
    )
    (output_dir / "stage7d_structured_density_report.md").write_text("\n".join(lines), encoding="utf-8")

    (output_dir / "summary.json").write_text(
        json.dumps(
            {"calibrated_degrees": survivors, "stage_b": stage_b.to_dict(orient="records")},
            indent=2, default=str,
        ) + "\n",
        encoding="utf-8",
    )
    return stage_b
