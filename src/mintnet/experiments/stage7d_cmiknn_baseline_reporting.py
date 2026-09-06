"""Descriptive report for Stage 7d's CMIknn baseline re-run. Purely
descriptive -- this run exists to supply the comparison side-by-side
with the structured-density sweep's own report; the actual head-to-head
comparison is produced by `scripts/stage7d_compare.py` once both
artifacts exist. See docs/stage7d_charter.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7d_cmiknn_baseline import Stage7dCmiknnBaselineConfig
from mintnet.experiments.stage7d_frontier import family_detection_limit


def detection_limits(raw: pd.DataFrame, config: Stage7dCmiknnBaselineConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for n in config.sample_sizes:
        limits = family_detection_limit(raw, condition_column="condition", p_value_column="p_value_12", n=n)
        for family, limit in limits.items():
            rows.append({"n": n, "family": family, "detection_limit": limit})
    return pd.DataFrame(rows)


def write_report(raw: pd.DataFrame, config: Stage7dCmiknnBaselineConfig, output_dir: Path) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    limits = detection_limits(raw, config)
    limits.to_csv(output_dir / "detection_limits.csv", index=False)

    n_errors = int((raw["status"] != "ok").sum())

    lines = [
        "# Stage 7d CMIknn Baseline Report (mi-native)\n",
        f"Purely descriptive -- `k_CMI={config.k_cmi}`, `k_perm={config.k_perm}`, "
        f"`R={config.replicates}` (reduced from the structured-density side's own R=400; see "
        "this module's own docstring for the cost rationale). Supplies the comparison side of "
        "`scripts/stage7d_compare.py`'s own head-to-head report.\n",
        f"Errors: {n_errors}\n",
        "## Detection limit per DGP family\n",
        "| N | family | detection limit |",
        "|---|---|---|",
    ]
    for _, row in limits.iterrows():
        limit = "not reached" if row["detection_limit"] is None else row["detection_limit"]
        lines.append(f"| {row.n} | {row.family} | {limit} |")
    lines.append("")
    lines.append("See `detection_limits.csv` for complete evidence.\n")
    (output_dir / "stage7d_cmiknn_baseline_report.md").write_text("\n".join(lines), encoding="utf-8")

    (output_dir / "summary.json").write_text(
        json.dumps({"detection_limits": limits.to_dict(orient="records")}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return limits
