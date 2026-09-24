"""Audit-oriented report for aggregated CIN panel outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .cin_baseline import PanelConfig, expected_row_count


def _load_pairs(raw: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    promised = raw.get("pair_sidecar_file", pd.Series(dtype=object)).dropna()
    if promised.empty:
        return pd.DataFrame()
    combined = Path(output_dir) / "sidecars" / "pairs_all.csv.gz"
    if combined.exists():
        return pd.read_csv(combined, compression="gzip")
    tables: list[pd.DataFrame] = []
    for file_name in promised.astype(str):
        path = Path(output_dir) / "sidecars" / Path(file_name).name
        if not path.exists():
            raise FileNotFoundError(f"promised sidecar is missing: {file_name}")
        tables.append(pd.read_csv(path, compression="gzip"))
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def write_report(raw: pd.DataFrame, config: PanelConfig, output_dir: Path) -> None:
    target = Path(output_dir)
    pairs = _load_pairs(raw, target)
    summary = (
        raw.groupby(["case", "phase", "method"], dropna=False)
        .agg(rows=("status", "size"), complete=("status", lambda values: int((values == "complete").sum())), failures=("status", lambda values: int((values == "error").sum())))
        .reset_index()
    )
    summary.to_csv(target / "baseline_summary.csv", index=False, lineterminator="\n")
    payload = {
        "configured_rows": expected_row_count(config),
        "emitted_rows": len(raw),
        "pair_rows": len(pairs),
        "status_counts": raw["status"].value_counts(dropna=False).to_dict(),
    }
    (target / "baseline_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# CIN statistical panel", "",
        f"Rows emitted: {len(raw)}; pair sidecar rows audited: {len(pairs)}.",
        "Counts are preserved behind every aggregate; incomplete and failed methods remain visible.",
    ]
    (target / "baseline_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ["write_report"]
