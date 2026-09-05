"""Two-stage analysis for the Stage 7c estimator-retuning experiment.
Descriptive/diagnostic only -- no single PROCEED/REASSESS gate, but a
real filter (Stage A) that determines which k_CMI values' own power
numbers (Stage B) are even meaningful. See docs/stage7c_charter.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage6c_reporting import wilson_ci
from mintnet.experiments.stage7c_retune import Stage7cConfig

ALPHAS: tuple[float, ...] = tuple(round(a, 2) for a in np.arange(0.01, 0.51, 0.01))
_TYPE_I_BANDS: dict[float, tuple[float, float]] = {0.05: (0.03, 0.07), 0.01: (0.005, 0.015)}
INDIRECT_PRUNE_TPR_FLOOR = 0.80
DIRECT_EDGE_POWER_FLOOR = 0.90

# D-060's own recorded k_CMI=40 baseline detection limits, for direct
# comparison -- not re-derived from raw data here (that evidence lives
# in results/generated/stage7b_frontier/, outside this run's own scope).
BASELINE_K_CMI = 40
BASELINE_DETECTION_LIMITS: dict[int, float] = {750: 0.20, 1500: 0.15, 3000: 0.12}


def _rejection_curve(p_values: pd.Series) -> dict[float, float]:
    values = p_values.dropna().to_numpy()
    if values.size == 0:
        return {alpha: float("nan") for alpha in ALPHAS}
    return {alpha: float((values <= alpha).mean()) for alpha in ALPHAS}


def stage_a_calibration_filter(raw: pd.DataFrame, config: Stage7cConfig) -> pd.DataFrame:
    """Per (k_cmi, n, alpha in {.05,.01}), at target_rho=0: rejection
    rate, Wilson 95% CI, and whether it's defensible (in band or CI
    overlaps nominal) -- D-056's own criterion, applied here to k_CMI
    instead of k_perm."""
    rows: list[dict[str, object]] = []
    for k_cmi in config.k_cmis:
        for n in config.sample_sizes:
            cell = raw.loc[
                (raw["k_cmi"] == k_cmi) & (raw["target_rho"] == 0.0) & (raw["n"] == n) & (raw["status"] == "ok")
            ]
            total = len(cell)
            for alpha, band in _TYPE_I_BANDS.items():
                if total == 0:
                    rows.append(
                        {"k_cmi": k_cmi, "n": n, "alpha": alpha, "rejections": 0, "total": 0,
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
                        "k_cmi": k_cmi, "n": n, "alpha": alpha, "rejections": rejections, "total": total,
                        "rate": rate, "ci_low": ci_low, "ci_high": ci_high, "defensible": bool(in_band or overlaps),
                    }
                )
    return pd.DataFrame(rows)


def calibrated_k_cmis(stage_a: pd.DataFrame, config: Stage7cConfig) -> list[int]:
    """k_CMI values defensible across EVERY tested N and alpha -- the
    same all-cells-must-pass discipline D-056 used for k_perm."""
    survivors = []
    for k_cmi in config.k_cmis:
        cell = stage_a.loc[stage_a["k_cmi"] == k_cmi]
        if cell["defensible"].all() and len(cell) > 0:
            survivors.append(k_cmi)
    return survivors


def stage_b_frontier_comparison(raw: pd.DataFrame, config: Stage7cConfig, survivors: list[int]) -> pd.DataFrame:
    """For each calibrated k_CMI, per N: detection limit (smallest
    target_rho>0 with power>=.90 at some alpha where the target_rho=0
    cell's own prune rate is >=.80 at that same alpha), compared
    against D-060's own recorded k_CMI=40 baseline."""
    rows: list[dict[str, object]] = []
    for k_cmi in survivors:
        for n in config.sample_sizes:
            null_cell = raw.loc[
                (raw["k_cmi"] == k_cmi) & (raw["target_rho"] == 0.0) & (raw["n"] == n) & (raw["status"] == "ok")
            ]
            null_curve = _rejection_curve(null_cell["p_value_12"])

            detection_limit = None
            for target_rho in sorted(rho for rho in config.target_rhos if rho > 0.0):
                cell = raw.loc[
                    (raw["k_cmi"] == k_cmi) & (raw["target_rho"] == target_rho) & (raw["n"] == n)
                    & (raw["status"] == "ok")
                ]
                power_curve = _rejection_curve(cell["p_value_12"])
                feasible_alpha_exists = any(
                    (1.0 - null_curve[alpha]) >= INDIRECT_PRUNE_TPR_FLOOR and power_curve[alpha] >= DIRECT_EDGE_POWER_FLOOR
                    for alpha in ALPHAS
                    if np.isfinite(null_curve[alpha]) and np.isfinite(power_curve[alpha])
                )
                if feasible_alpha_exists:
                    detection_limit = target_rho
                    break

            baseline = BASELINE_DETECTION_LIMITS.get(n)
            improved = (
                detection_limit is not None and baseline is not None and detection_limit < baseline
            )
            rows.append(
                {
                    "k_cmi": k_cmi, "n": n, "detection_limit": detection_limit,
                    "baseline_k_cmi": BASELINE_K_CMI, "baseline_detection_limit": baseline,
                    "improved_on_baseline": improved,
                }
            )
    return pd.DataFrame(rows)


def write_report(raw: pd.DataFrame, config: Stage7cConfig, output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_a = stage_a_calibration_filter(raw, config)
    stage_a.to_csv(output_dir / "stage_a_calibration.csv", index=False)

    survivors = calibrated_k_cmis(stage_a, config)
    stage_b = stage_b_frontier_comparison(raw, config, survivors)
    stage_b.to_csv(output_dir / "stage_b_frontier_comparison.csv", index=False)

    n_errors = int((raw["status"] != "ok").sum())
    any_improved = bool(stage_b["improved_on_baseline"].any()) if not stage_b.empty else False

    lines = [
        "# Stage 7c Report -- Estimator Retuning Against the Mapped Frontier (mi-native)\n",
        "Descriptive/diagnostic -- no single PROCEED/REASSESS gate. Stage A filters which "
        "k_CMI values remain calibrated; Stage B compares detection limits among survivors "
        "against D-060's own k_CMI=40 baseline.\n",
        f"Errors: {n_errors}\n",
        f"**Calibrated k_CMI values (survived Stage A): {survivors}**\n",
        f"**Any surviving k_CMI improves on the k_CMI={BASELINE_K_CMI} baseline anywhere tested: {any_improved}**\n",
        "## Stage A: calibration filter (every N x alpha must pass)\n",
        "| k_CMI | defensible everywhere |",
        "|---|---|",
    ]
    for k_cmi in config.k_cmis:
        cell = stage_a.loc[stage_a["k_cmi"] == k_cmi]
        lines.append(f"| {k_cmi} | {bool(cell['defensible'].all()) if len(cell) else False} |")
    lines.append("")
    lines.append("## Stage B: detection limit vs. baseline, calibrated survivors only\n")
    lines.append("| k_CMI | N | detection limit | baseline (k_CMI=40) | improved |")
    lines.append("|---|---|---|---|---|")
    for _, row in stage_b.iterrows():
        limit = "not reached" if row["detection_limit"] is None else row["detection_limit"]
        lines.append(f"| {row.k_cmi} | {row.n} | {limit} | {row.baseline_detection_limit} | {row.improved_on_baseline} |")
    lines.append("")
    lines.append(
        "See `stage_a_calibration.csv` and `stage_b_frontier_comparison.csv` for complete evidence.\n"
    )
    (output_dir / "stage7c_report.md").write_text("\n".join(lines), encoding="utf-8")

    (output_dir / "summary.json").write_text(
        json.dumps(
            {"calibrated_k_cmis": survivors, "any_improved": any_improved, "stage_b": stage_b.to_dict(orient="records")},
            indent=2, default=str,
        ) + "\n",
        encoding="utf-8",
    )
    return stage_b
