"""Analysis for Stage 7e's own up-front calibration-transfer check.
Decides whether D-062's `degree=1` finding (measured on
`weak_edge_triangle`) transfers onto Stage 7's own real isolation-tier
fixtures, or whether a different calibrated `degree` must be used
instead. See docs/stage7e_charter.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6c_reporting import wilson_ci
from mintnet.experiments.stage7e_calibration_transfer import Stage7eCalibrationTransferConfig
from mintnet.experiments.stage7e_conditions import CHAIN_FORK_STRENGTHS, TRIANGLE_FAMILIES, condition_label

_TYPE_I_BANDS: dict[float, tuple[float, float]] = {0.05: (0.03, 0.07), 0.01: (0.005, 0.015)}
_NULL_PAIR = "0-2"


def calibration_filter(raw: pd.DataFrame, config: Stage7eCalibrationTransferConfig) -> pd.DataFrame:
    """Per (degree, motif, strength, n, alpha in {.05,.01}), at the
    chain/fork's own genuine null pair `(0,2)|1`: rejection rate,
    Wilson 95% CI, and defensibility -- D-056's own criterion, applied
    here directly to Stage 7's own isolation-tier fixtures rather than
    `weak_edge_triangle`."""
    rows: list[dict[str, object]] = []
    for degree in config.degrees:
        for motif in ("chain", "fork"):
            for strength in CHAIN_FORK_STRENGTHS:
                condition = condition_label(motif, strength)
                for n in config.sample_sizes:
                    cell = raw.loc[
                        (raw["degree"] == degree) & (raw["condition"] == condition) & (raw["pair"] == _NULL_PAIR)
                        & (raw["n"] == n) & (raw["status"] == "ok")
                    ]
                    total = len(cell)
                    for alpha, band in _TYPE_I_BANDS.items():
                        if total == 0:
                            rows.append(
                                {"degree": degree, "motif": motif, "strength": strength, "n": n, "alpha": alpha,
                                 "rejections": 0, "total": 0, "rate": float("nan"),
                                 "ci_low": float("nan"), "ci_high": float("nan"), "defensible": False}
                            )
                            continue
                        rejections = int((cell["p_value"] <= alpha).sum())
                        rate = rejections / total
                        ci_low, ci_high = wilson_ci(rejections, total)
                        in_band = band[0] <= rate <= band[1]
                        overlaps = ci_low <= alpha <= ci_high
                        rows.append(
                            {
                                "degree": degree, "motif": motif, "strength": strength, "n": n, "alpha": alpha,
                                "rejections": rejections, "total": total, "rate": rate,
                                "ci_low": ci_low, "ci_high": ci_high, "defensible": bool(in_band or overlaps),
                            }
                        )
    return pd.DataFrame(rows)


def calibrated_degrees(calibration: pd.DataFrame, config: Stage7eCalibrationTransferConfig) -> list[int]:
    """`degree` values defensible across EVERY tested motif, strength,
    N, and alpha -- the same all-cells-must-pass discipline D-056/Stage
    7c/7d used."""
    survivors = []
    for degree in config.degrees:
        cell = calibration.loc[calibration["degree"] == degree]
        if len(cell) > 0 and cell["defensible"].all():
            survivors.append(degree)
    return survivors


def triangle_power(raw: pd.DataFrame, config: Stage7eCalibrationTransferConfig) -> pd.DataFrame:
    """Descriptive only (no null pair exists for triangle families):
    rejection rate at alpha=0.05 on each of the three pairs, per
    (degree, family, N) -- context for the `degree` decision, not a
    pass/fail criterion."""
    rows: list[dict[str, object]] = []
    for degree in config.degrees:
        for family in TRIANGLE_FAMILIES:
            condition = condition_label("triangle", family)
            for n in config.sample_sizes:
                for pair in ("0-1", "0-2", "1-2"):
                    cell = raw.loc[
                        (raw["degree"] == degree) & (raw["condition"] == condition) & (raw["pair"] == pair)
                        & (raw["n"] == n) & (raw["status"] == "ok")
                    ]
                    total = len(cell)
                    rate = float((cell["p_value"] <= 0.05).mean()) if total else float("nan")
                    rows.append({"degree": degree, "family": family, "n": n, "pair": pair, "power_at_alpha_05": rate})
    return pd.DataFrame(rows)


def write_report(raw: pd.DataFrame, config: Stage7eCalibrationTransferConfig, output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    calibration = calibration_filter(raw, config)
    calibration.to_csv(output_dir / "calibration_filter.csv", index=False)

    survivors = calibrated_degrees(calibration, config)
    power = triangle_power(raw, config)
    power.to_csv(output_dir / "triangle_power.csv", index=False)

    n_errors = int((raw["status"] != "ok").sum())

    lines = [
        "# Stage 7e Calibration-Transfer Check Report (mi-native)\n",
        "Decides whether D-062's `degree=1` finding transfers onto Stage 7's own "
        "isolation-tier fixtures (chain/fork/triangle), before Stage 7e's own main run "
        "commits to an operating `degree`.\n",
        f"Errors: {n_errors}\n",
        f"**Calibrated degree values (chain/fork null, every motif/strength/N/alpha): {survivors}**\n",
        "## Calibration filter (chain/fork's own genuine null pair)\n",
        "| degree | defensible everywhere |",
        "|---|---|",
    ]
    for degree in config.degrees:
        cell = calibration.loc[calibration["degree"] == degree]
        lines.append(f"| {degree} | {bool(cell['defensible'].all()) if len(cell) else False} |")
    lines.append("")
    lines.append("## Triangle power (descriptive, not a pass/fail criterion)\n")
    lines.append("| degree | family | N | pair | power at alpha=0.05 |")
    lines.append("|---|---|---|---|---|")
    for _, row in power.iterrows():
        lines.append(f"| {row.degree} | {row.family} | {row.n} | {row.pair} | {row.power_at_alpha_05:.3f} |")
    lines.append("")
    lines.append("See `calibration_filter.csv` and `triangle_power.csv` for complete evidence.\n")
    (output_dir / "stage7e_calibration_transfer_report.md").write_text("\n".join(lines), encoding="utf-8")

    (output_dir / "summary.json").write_text(
        json.dumps(
            {"calibrated_degrees": survivors, "triangle_power": power.to_dict(orient="records")},
            indent=2, default=str,
        ) + "\n",
        encoding="utf-8",
    )
    return calibration
