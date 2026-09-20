"""Operating-frontier analysis for the Stage 7b power-curve mapping.
Descriptive/diagnostic only -- no PROCEED/REASSESS gate, per
docs/stage7b_charter.md. Applies the charter's own frozen 50-value
alpha grid entirely at reporting time, re-thresholding each replicate's
own already-computed p-values (stored once in raw_metrics.csv).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage7b_frontier import Stage7bConfig

ALPHAS: tuple[float, ...] = tuple(round(a, 2) for a in np.arange(0.01, 0.51, 0.01))
INDIRECT_PRUNE_TPR_FLOOR = 0.80
DIRECT_EDGE_POWER_FLOOR = 0.90  # equivalent to the Stage 7 gate's own FPR <= .10


def _rejection_curve(p_values: pd.Series) -> dict[float, float]:
    """P(p <= alpha) for every alpha in the frozen grid -- the retention/
    rejection rate, whichever interpretation applies to the caller's own
    null-vs-alternative framing."""
    values = p_values.dropna().to_numpy()
    if values.size == 0:
        return {alpha: float("nan") for alpha in ALPHAS}
    return {alpha: float((values <= alpha).mean()) for alpha in ALPHAS}


def build_curves(raw: pd.DataFrame, config: Stage7bConfig) -> pd.DataFrame:
    """Per (target_rho, n, alpha): weak-edge power (or, at target_rho=0,
    the in-family null retention rate), plus both dominant edges' own
    retention rate as a sanity check."""
    rows: list[dict[str, object]] = []
    for target_rho in config.target_rhos:
        for n in config.sample_sizes:
            cell = raw.loc[(raw["target_rho"] == target_rho) & (raw["n"] == n) & (raw["status"] == "ok")]
            weak_curve = _rejection_curve(cell["p_value_12"])
            dom01_curve = _rejection_curve(cell["p_value_01"])
            dom02_curve = _rejection_curve(cell["p_value_02"])
            for alpha in ALPHAS:
                rows.append(
                    {
                        "target_rho": target_rho, "n": n, "alpha": alpha,
                        "n_ok": len(cell),
                        "weak_edge_rejection_rate": weak_curve[alpha],
                        "dominant_edge_01_retention": dom01_curve[alpha],
                        "dominant_edge_02_retention": dom02_curve[alpha],
                    }
                )
    return pd.DataFrame(rows)


def null_calibration_check(curves: pd.DataFrame) -> pd.DataFrame:
    """target_rho=0 cells: weak_edge_rejection_rate is the in-family
    Type-I error rate -- compare directly against the nominal alpha,
    not borrowed from a different DGP structure (D-059's own chain/fork
    numbers), per the charter's own explicit design choice."""
    null_rows = curves.loc[curves["target_rho"] == 0.0].copy()
    null_rows["indirect_prune_rate"] = 1.0 - null_rows["weak_edge_rejection_rate"]
    null_rows["nominal_alpha"] = null_rows["alpha"]
    return null_rows[["n", "alpha", "weak_edge_rejection_rate", "indirect_prune_rate", "nominal_alpha"]]


def operating_frontier(curves: pd.DataFrame) -> pd.DataFrame:
    """For every (target_rho > 0, n, alpha): does this cell satisfy
    BOTH the indirect-edge-pruning floor (using this run's own
    target_rho=0 cell at the same N as the proxy, per the charter's own
    design) and the direct-edge power floor, at that same alpha."""
    null_by_n_alpha = (
        curves.loc[curves["target_rho"] == 0.0]
        .set_index(["n", "alpha"])["weak_edge_rejection_rate"]
        .apply(lambda rate: 1.0 - rate)
    )
    rows: list[dict[str, object]] = []
    for _, row in curves.loc[curves["target_rho"] > 0.0].iterrows():
        indirect_prune_rate = null_by_n_alpha.get((row["n"], row["alpha"]), float("nan"))
        power = row["weak_edge_rejection_rate"]
        feasible = bool(
            np.isfinite(indirect_prune_rate)
            and np.isfinite(power)
            and indirect_prune_rate >= INDIRECT_PRUNE_TPR_FLOOR
            and power >= DIRECT_EDGE_POWER_FLOOR
        )
        rows.append(
            {
                "target_rho": row["target_rho"], "n": row["n"], "alpha": row["alpha"],
                "indirect_prune_rate": indirect_prune_rate, "direct_edge_power": power,
                "feasible": feasible,
            }
        )
    return pd.DataFrame(rows)


def detection_limit_summary(frontier: pd.DataFrame) -> pd.DataFrame:
    """Smallest target_rho with at least one feasible alpha, per N --
    directly answering D-059's own posed question. 'not reached' if no
    tested target_rho has any feasible alpha at that N."""
    rows: list[dict[str, object]] = []
    for n in sorted(frontier["n"].unique()):
        by_n = frontier.loc[frontier["n"] == n]
        feasible_rhos = sorted(by_n.loc[by_n["feasible"], "target_rho"].unique())
        rows.append(
            {
                "n": n,
                "detection_limit_target_rho": feasible_rhos[0] if feasible_rhos else None,
                "any_feasible_rho_tested": len(feasible_rhos) > 0,
            }
        )
    return pd.DataFrame(rows)


def write_report(raw: pd.DataFrame, config: Stage7bConfig, output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    curves = build_curves(raw, config)
    curves.to_csv(output_dir / "power_curves.csv", index=False)

    null_check = null_calibration_check(curves)
    null_check.to_csv(output_dir / "null_calibration_check.csv", index=False)

    frontier = operating_frontier(curves)
    frontier.to_csv(output_dir / "operating_frontier.csv", index=False)

    summary = detection_limit_summary(frontier)
    summary.to_csv(output_dir / "detection_limit_summary.csv", index=False)

    n_errors = int((raw["status"] != "ok").sum())
    lines = [
        "# Stage 7b Report -- Power-Curve / Operating-Frontier Mapping (mi-native)\n",
        "Descriptive/diagnostic -- no PROCEED/REASSESS gate. See "
        "docs/stage7b_charter.md's own consequences section for how to read this.\n",
        f"k_CMI={config.k_cmi}, k_perm={config.k_perm}, permutations={config.permutations} "
        "(D-056/D-057's own calibrated setting, held fixed throughout).\n",
        f"Errors: {n_errors}\n",
        "## Detection-limit summary (smallest target_rho with any feasible alpha, per N)\n",
        "| N | detection limit (|rho_partial|) | any feasible rho tested |",
        "|---|---|---|",
    ]
    for _, row in summary.iterrows():
        limit = "not reached in tested range" if row["detection_limit_target_rho"] is None else row["detection_limit_target_rho"]
        lines.append(f"| {int(row.n)} | {limit} | {row.any_feasible_rho_tested} |")
    lines.append("")
    lines.append(
        "See `power_curves.csv` (full per-alpha curves), `null_calibration_check.csv` "
        "(in-family Type-I error check against nominal alpha), `operating_frontier.csv` "
        "(per-cell feasibility), and `detection_limit_summary.csv` for complete evidence.\n"
    )
    (output_dir / "stage7b_report.md").write_text("\n".join(lines), encoding="utf-8")

    (output_dir / "summary.json").write_text(
        json.dumps({"detection_limits": summary.to_dict(orient="records")}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return summary
