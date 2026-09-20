"""Evidence rendering and the predeclared gate for the Stage 6c
null-calibration study. See docs/stage6c_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from mintnet.experiments.stage6c import (
    ALT_CONDITIONS,
    NULL_CONDITIONS,
    StageAConfig,
    StageBConfig,
    StageCConfig,
)

_TYPE_I_BANDS: dict[float, tuple[float, float]] = {0.05: (0.03, 0.07), 0.01: (0.005, 0.015)}
_POWER_THRESHOLD = 0.80


def wilson_ci(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval -- reliable near p=0/p=1, unlike the normal
    approximation, which matters for this study's own alpha=.01 cells."""
    if total == 0:
        return (float("nan"), float("nan"))
    z = float(norm.ppf(1 - (1 - confidence) / 2))
    p_hat = successes / total
    denom = 1 + z**2 / total
    center = (p_hat + z**2 / (2 * total)) / denom
    margin = (z * np.sqrt(p_hat * (1 - p_hat) / total + z**2 / (4 * total**2))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _ci_contains(ci: tuple[float, float], value: float) -> bool:
    return ci[0] <= value <= ci[1]


# ---------------------------------------------------------------------------
# Stage A report: k_CMI bias/RMSE (true CMI = 0 for every null condition)
# ---------------------------------------------------------------------------


def write_stage_a_report(raw: pd.DataFrame, config: StageAConfig, output_dir: Path) -> pd.DataFrame:
    rows = []
    for k_cmi in config.k_cmi_values:
        for condition in NULL_CONDITIONS:
            label = condition["label"]
            s = int(condition["s"])
            for n in config.sample_sizes:
                cell = raw.loc[(raw["k_cmi"] == k_cmi) & (raw["label"] == label) & (raw["n"] == n)]
                ok = cell.loc[cell["status"] == "ok"]
                n_errors = int((cell["status"] != "ok").sum())
                if ok.empty:
                    rows.append({"k_cmi": k_cmi, "label": label, "s": s, "n": n, "bias": np.nan, "rmse": np.nan, "n_errors": n_errors})
                    continue
                estimates = ok["estimate"].to_numpy()
                bias = float(estimates.mean())  # true CMI = 0 for every null condition
                rmse = float(np.sqrt(np.mean(estimates**2)))
                rows.append({"k_cmi": k_cmi, "label": label, "s": s, "n": n, "bias": bias, "rmse": rmse, "n_errors": n_errors})
    summary = pd.DataFrame(rows)
    summary.to_csv(output_dir / "stage_a_summary.csv", index=False)

    by_k = summary.groupby("k_cmi")[["bias", "rmse"]].agg(lambda s: np.sqrt(np.mean(s**2)) if s.name == "rmse" else np.mean(np.abs(s)))
    recommended_k = int(by_k["rmse"].idxmin())

    lines = [
        "# Stage 6c Report -- Stage A: k_CMI sensitivity (mi-native)\n",
        "Point-estimate bias/RMSE only (no permutation test) under true-null conditions "
        "(true I(X;Y|Z) = 0 by construction for every condition here).\n",
        "## Aggregate RMSE by k_CMI (pooled across |S| and N)\n",
        "| k_CMI | mean |bias| | pooled RMSE |",
        "|---|---|---|",
    ]
    for k_cmi in config.k_cmi_values:
        row = by_k.loc[k_cmi]
        lines.append(f"| {k_cmi} | {row['bias']:.4f} | {row['rmse']:.4f} |")
    lines.append("")
    lines.append(f"**Recommended k_CMI (lowest pooled RMSE): {recommended_k}**\n")
    lines.append("## Per-cell bias/RMSE\n")
    lines.append("| k_CMI | label | |S| | N | bias | RMSE | errors |")
    lines.append("|---|---|---|---|---|---|---|")
    for _, r in summary.iterrows():
        lines.append(f"| {r.k_cmi} | {r.label} | {r.s} | {r.n} | {r.bias:.4f} | {r.rmse:.4f} | {r.n_errors} |")
    (output_dir / "stage_a_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


# ---------------------------------------------------------------------------
# Stage B report: k_perm null calibration, per-cell Wilson CI + gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageBCell:
    k_perm_label: str
    k_perm_resolved: int
    label: str
    s: int
    n: int
    alpha: float
    rejections: int
    total: int
    rate: float
    ci_low: float
    ci_high: float
    in_band: bool
    ci_overlaps_nominal: bool
    defensible: bool
    n_errors: int


def _stage_b_cells(raw: pd.DataFrame, config: StageBConfig) -> list[StageBCell]:
    cells: list[StageBCell] = []
    seen: set[tuple[str, str, int]] = set()
    for _, group_key in raw[["k_perm_label", "label", "n"]].drop_duplicates().iterrows():
        key = (str(group_key["k_perm_label"]), str(group_key["label"]), int(group_key["n"]))
        if key in seen:
            continue
        seen.add(key)
        k_perm_label, label, n = key
        cell_raw = raw.loc[(raw["k_perm_label"] == k_perm_label) & (raw["label"] == label) & (raw["n"] == n)]
        s = int(cell_raw["s"].iloc[0])
        k_perm_resolved = int(cell_raw["k_perm_resolved"].iloc[0])
        n_errors = int((cell_raw["status"] != "ok").sum())
        ok = cell_raw.loc[cell_raw["status"] == "ok"]
        total = len(ok)
        for alpha in config.alphas:
            if total == 0:
                cells.append(StageBCell(k_perm_label, k_perm_resolved, label, s, n, alpha, 0, 0, float("nan"), float("nan"), float("nan"), False, False, False, n_errors))
                continue
            rejections = int((ok["p_value"] <= alpha).sum())
            rate = rejections / total
            ci = wilson_ci(rejections, total)
            band = _TYPE_I_BANDS.get(alpha)
            in_band = band is not None and band[0] <= rate <= band[1]
            overlaps = band is not None and _ci_contains(ci, alpha)
            defensible = bool(in_band or overlaps)
            cells.append(
                StageBCell(k_perm_label, k_perm_resolved, label, s, n, alpha, rejections, total, rate, ci[0], ci[1], in_band, overlaps, defensible, n_errors)
            )
    return cells


def write_stage_b_report(raw: pd.DataFrame, config: StageBConfig, output_dir: Path) -> list[StageBCell]:
    cells = _stage_b_cells(raw, config)
    cells_df = pd.DataFrame([asdict(c) for c in cells])
    cells_df.to_csv(output_dir / "stage_b_cells.csv", index=False)

    per_kperm_defensible: dict[str, bool] = {}
    for label in cells_df["k_perm_label"].unique():
        subset = cells_df.loc[cells_df["k_perm_label"] == label]
        per_kperm_defensible[label] = bool(subset["defensible"].all())

    defensible_labels = [label for label, ok in per_kperm_defensible.items() if ok]
    verdict = "PROCEED" if defensible_labels else "REASSESS"

    # smallest defensible fixed k_perm value preferred; adaptive as fallback
    preference_order = ["kperm3", "kperm5", "kperm10", "kperm20", "adaptive"]
    recommended = next((l for l in preference_order if l in defensible_labels), None)

    lines = [
        "# Stage 6c Report -- Stage B: local-permutation null calibration (mi-native)\n",
        f"**Verdict: {verdict}**\n",
    ]
    if recommended:
        lines.append(f"**Recommended operational k_perm: `{recommended}`** (defensible across every tested N x |S| cell; smallest such value preferred, or adaptive if no fixed value qualifies).\n")
    else:
        lines.append("**No swept k_perm value is defensible across every tested N x |S| cell.** See pattern tables below.\n")

    lines.append("## Defensibility by k_perm (every tested N x |S| x alpha cell must pass)\n")
    lines.append("| k_perm | defensible everywhere |")
    lines.append("|---|---|")
    for label in preference_order:
        if label in per_kperm_defensible:
            lines.append(f"| {label} | {per_kperm_defensible[label]} |")
    lines.append("")

    lines.append("## Pattern: rejection rate by |S| (pooled across N and k_perm, alpha=.05)\n")
    lines.append("| |S| | mean rate | n cells |")
    lines.append("|---|---|---|")
    for s in sorted(cells_df["s"].unique()):
        subset = cells_df.loc[(cells_df["s"] == s) & (cells_df["alpha"] == 0.05)]
        lines.append(f"| {s} | {subset['rate'].mean():.4f} | {len(subset)} |")
    lines.append("")

    lines.append("## Pattern: rejection rate by N within each k_perm (alpha=.05, |S|>=1 pooled)\n")
    lines.append("| k_perm | N | mean rate |")
    lines.append("|---|---|---|")
    for label in preference_order:
        if label not in per_kperm_defensible:
            continue
        for n in sorted(cells_df["n"].unique()):
            subset = cells_df.loc[(cells_df["k_perm_label"] == label) & (cells_df["n"] == n) & (cells_df["alpha"] == 0.05) & (cells_df["s"] >= 1)]
            if subset.empty:
                continue
            lines.append(f"| {label} | {n} | {subset['rate'].mean():.4f} |")
    lines.append("")

    lines.append("## Full per-cell evidence (alpha, rejections/total, rate, Wilson 95% CI)\n")
    lines.append("| k_perm | label | |S| | N | alpha | rejections/total | rate | CI low | CI high | in band | CI overlaps nominal | defensible |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in cells:
        lines.append(
            f"| {c.k_perm_label} | {c.label} | {c.s} | {c.n} | {c.alpha} | {c.rejections}/{c.total} | "
            f"{c.rate:.4f} | {c.ci_low:.4f} | {c.ci_high:.4f} | {c.in_band} | {c.ci_overlaps_nominal} | {c.defensible} |"
        )
    (output_dir / "stage_b_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (output_dir / "stage_b_verdict.json").write_text(
        json.dumps({"verdict": verdict, "defensible_labels": defensible_labels, "recommended": recommended}, indent=2) + "\n",
        encoding="utf-8",
    )
    return cells


# ---------------------------------------------------------------------------
# Stage C report: power at the calibrated setting
# ---------------------------------------------------------------------------


def write_stage_c_report(raw: pd.DataFrame, config: StageCConfig, output_dir: Path) -> pd.DataFrame:
    rows = []
    for condition in ALT_CONDITIONS:
        label = condition["label"]
        s = int(condition["s"])
        for n in config.sample_sizes:
            cell = raw.loc[(raw["label"] == label) & (raw["n"] == n)]
            ok = cell.loc[cell["status"] == "ok"]
            n_errors = int((cell["status"] != "ok").sum())
            for alpha in config.alphas:
                if ok.empty:
                    rows.append({"label": label, "s": s, "n": n, "alpha": alpha, "power": np.nan, "n_errors": n_errors})
                    continue
                power = float((ok["p_value"] <= alpha).mean())
                rows.append({"label": label, "s": s, "n": n, "alpha": alpha, "power": power, "n_errors": n_errors})
    summary = pd.DataFrame(rows)
    summary.to_csv(output_dir / "stage_c_summary.csv", index=False)

    power_05 = summary.loc[summary["alpha"] == 0.05]
    power_holds = bool((power_05["power"] >= _POWER_THRESHOLD).all()) if not power_05.empty else False

    lines = [
        "# Stage 6c Report -- Stage C: power at the calibrated setting (mi-native)\n",
        f"k_CMI={config.k_cmi}, k_perm={config.k_perm_label}\n",
        f"**Power >= {_POWER_THRESHOLD} at alpha=.05 for every condition/N: {power_holds}**\n",
        "| label | |S| | N | alpha | power | errors |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in summary.iterrows():
        lines.append(f"| {r.label} | {r.s} | {r.n} | {r.alpha} | {r.power:.4f} | {r.n_errors} |")
    (output_dir / "stage_c_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
