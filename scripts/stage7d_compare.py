"""Head-to-head comparison for Stage 7d: structured-density estimator
(calibrated degree survivors) vs. the CMIknn baseline, both evaluated
on the identical DGP grid (`mintnet.experiments.stage7d_conditions`).
Run only after both `mintnet.experiments.stage7d_structured_density`
and `mintnet.experiments.stage7d_cmiknn_baseline` have produced their
own aggregated artifacts (raw_metrics.csv). See docs/stage7d_charter.md.

This script does not run any new evidence -- it only reads the two
already-aggregated `raw_metrics.csv` files and reports:

1. Per-family detection limits, calibrated structured-density degrees
   vs. the CMIknn baseline, side by side.
2. The mandatory U-shape diagnostic: per-curvature power for both
   estimators, since a bare detection-limit comparison could hide the
   single result this charter cannot skip (see the charter's own
   "Required evidence" section) -- whether the structured estimator
   detects U-shaped dependence at a rate distinguishable from CMIknn's
   own (expected to be near the null rate, since CMIknn's own
   symmetric kNN construction has no special blindness to this
   fixture's zero *linear* correlation the way a Fisher-z test would,
   but the structured estimator's own comparative advantage here, if
   any, is exactly what this comparison exists to check).
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage7d_conditions import USHAPE_CURVATURES, condition_label
from mintnet.experiments.stage7d_frontier import family_detection_limit, rejection_curve
from mintnet.experiments.stage7d_structured_density_reporting import calibrated_degrees, stage_a_calibration_filter


def _load_config(path: Path):
    from mintnet.experiments.stage7d_structured_density import load_config

    return load_config(path)


def structured_density_best_detection_limits(
    raw: pd.DataFrame, config, survivors: list[int]
) -> pd.DataFrame:
    """Per N, per family: the *best* (smallest) detection limit among
    calibrated degree survivors -- the fairest single number to compare
    against the baseline's own single (uncalibrated-choice) number,
    since a future composition charter would simply pick whichever
    calibrated degree performs best at its own chosen N."""
    rows: list[dict[str, object]] = []
    for n in config.sample_sizes:
        best: dict[str, tuple[int, float] | None] = {"linear": None, "curvature": None, "ushape": None}
        for degree in survivors:
            limits = family_detection_limit(
                raw, condition_column="condition", p_value_column="p_value_12", n=n,
                group_filter=raw["degree"] == degree,
            )
            for family, limit in limits.items():
                if limit is None:
                    continue
                if best[family] is None or limit < best[family][1]:
                    best[family] = (degree, limit)
        for family, value in best.items():
            rows.append(
                {
                    "n": n, "family": family,
                    "best_degree": None if value is None else value[0],
                    "detection_limit": None if value is None else value[1],
                }
            )
    return pd.DataFrame(rows)


def ushape_power_comparison(
    structured_raw: pd.DataFrame, structured_survivors: list[int], baseline_raw: pd.DataFrame, sample_sizes: tuple[int, ...]
) -> pd.DataFrame:
    """Per N, per curvature: power at `alpha=0.05` for the best
    calibrated structured-density degree at that N vs. the CMIknn
    baseline -- the direct, disclosed answer to the charter's own
    mandatory diagnostic question."""
    rows: list[dict[str, object]] = []
    for n in sample_sizes:
        for curvature in USHAPE_CURVATURES:
            condition = condition_label("ushape", curvature)
            baseline_cell = baseline_raw.loc[
                (baseline_raw["condition"] == condition) & (baseline_raw["n"] == n) & (baseline_raw["status"] == "ok")
            ]
            baseline_power = rejection_curve(baseline_cell["p_value_12"]).get(0.05, float("nan"))

            best_structured_power = float("nan")
            best_degree = None
            for degree in structured_survivors:
                cell = structured_raw.loc[
                    (structured_raw["degree"] == degree) & (structured_raw["condition"] == condition)
                    & (structured_raw["n"] == n) & (structured_raw["status"] == "ok")
                ]
                power = rejection_curve(cell["p_value_12"]).get(0.05, float("nan"))
                if pd.isna(best_structured_power) or (not pd.isna(power) and power > best_structured_power):
                    best_structured_power = power
                    best_degree = degree

            rows.append(
                {
                    "n": n, "curvature": curvature,
                    "structured_density_best_degree": best_degree,
                    "structured_density_power_at_alpha_05": best_structured_power,
                    "cmiknn_baseline_power_at_alpha_05": baseline_power,
                }
            )
    return pd.DataFrame(rows)


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent.parent, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _read_source_metadata(source_dir: Path) -> dict[str, object] | None:
    metadata_path = source_dir / "metadata.json"
    if not metadata_path.is_file():
        return None
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _write_provenance(
    output_dir: Path, structured_density_dir: Path, cmiknn_baseline_dir: Path
) -> None:
    """Unlike the two evidence runs this script compares (each written
    via `aggregate_shards.py`'s own `_write_provenance`), this script
    produces no new evidence -- it only reads two already-aggregated
    `raw_metrics.csv` files. Its own `metadata.json` therefore records
    the commit/environment this *comparison* was run under, plus each
    source directory's own metadata (git commit, charter hash) verbatim
    -- so a reader can confirm both inputs came from the same charter
    lineage without re-deriving it."""
    metadata = {
        "git_commit": _git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "structured_density_source": str(structured_density_dir),
        "structured_density_source_metadata": _read_source_metadata(structured_density_dir),
        "cmiknn_baseline_source": str(cmiknn_baseline_dir),
        "cmiknn_baseline_source_metadata": _read_source_metadata(cmiknn_baseline_dir),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str) + "\n", encoding="utf-8")


def compare(
    structured_density_dir: Path, cmiknn_baseline_dir: Path,
    structured_density_config_path: Path, output_dir: Path,
) -> None:
    structured_raw = pd.read_csv(structured_density_dir / "raw_metrics.csv")
    baseline_raw = pd.read_csv(cmiknn_baseline_dir / "raw_metrics.csv")
    config = _load_config(structured_density_config_path)

    stage_a = stage_a_calibration_filter(structured_raw, config)
    survivors = calibrated_degrees(stage_a, config)

    detection_limits = structured_density_best_detection_limits(structured_raw, config, survivors)
    baseline_limits = family_detection_limit_table(baseline_raw, config.sample_sizes)
    ushape_power = ushape_power_comparison(structured_raw, survivors, baseline_raw, config.sample_sizes)

    output_dir.mkdir(parents=True, exist_ok=True)
    detection_limits.to_csv(output_dir / "structured_density_detection_limits.csv", index=False)
    baseline_limits.to_csv(output_dir / "cmiknn_baseline_detection_limits.csv", index=False)
    ushape_power.to_csv(output_dir / "ushape_power_comparison.csv", index=False)
    _write_provenance(output_dir, structured_density_dir, cmiknn_baseline_dir)

    lines = [
        "# Stage 7d Head-to-Head Comparison (mi-native)\n",
        f"Calibrated structured-density degrees (Stage A survivors): {survivors}\n",
        "## Detection limit per family and N: structured density (best calibrated degree) vs. CMIknn baseline\n",
        "| N | family | structured-density limit (degree) | CMIknn baseline limit |",
        "|---|---|---|---|",
    ]
    for n in config.sample_sizes:
        for family in ("linear", "curvature", "ushape"):
            sd_row = detection_limits.loc[(detection_limits["n"] == n) & (detection_limits["family"] == family)]
            bl_row = baseline_limits.loc[(baseline_limits["n"] == n) & (baseline_limits["family"] == family)]
            sd_limit = sd_row["detection_limit"].iloc[0] if len(sd_row) else None
            sd_degree = sd_row["best_degree"].iloc[0] if len(sd_row) else None
            bl_limit = bl_row["detection_limit"].iloc[0] if len(bl_row) else None
            sd_text = "not reached" if sd_limit is None else f"{sd_limit} (degree={sd_degree})"
            bl_text = "not reached" if bl_limit is None else bl_limit
            lines.append(f"| {n} | {family} | {sd_text} | {bl_text} |")
    lines.append("")
    lines.append(
        "## Mandatory diagnostic: U-shape power at alpha=0.05 "
        "(structured density's own core value proposition)\n"
    )
    lines.append("| N | curvature | structured density (best degree) | CMIknn baseline |")
    lines.append("|---|---|---|---|")
    for _, row in ushape_power.iterrows():
        lines.append(
            f"| {row.n} | {row.curvature} | {row.structured_density_power_at_alpha_05:.3f} "
            f"(degree={row.structured_density_best_degree}) | {row.cmiknn_baseline_power_at_alpha_05:.3f} |"
        )
    lines.append("")
    (output_dir / "stage7d_comparison_report.md").write_text("\n".join(lines), encoding="utf-8")

    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "calibrated_degrees": survivors,
                "detection_limits": detection_limits.to_dict(orient="records"),
                "baseline_detection_limits": baseline_limits.to_dict(orient="records"),
                "ushape_power_comparison": ushape_power.to_dict(orient="records"),
            },
            indent=2, default=str,
        ) + "\n",
        encoding="utf-8",
    )


def family_detection_limit_table(raw: pd.DataFrame, sample_sizes: tuple[int, ...]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for n in sample_sizes:
        limits = family_detection_limit(raw, condition_column="condition", p_value_column="p_value_12", n=n)
        for family, limit in limits.items():
            rows.append({"n": n, "family": family, "detection_limit": limit})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structured-density-dir", required=True, type=Path)
    parser.add_argument("--cmiknn-baseline-dir", required=True, type=Path)
    parser.add_argument("--structured-density-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    compare(
        arguments.structured_density_dir, arguments.cmiknn_baseline_dir,
        arguments.structured_density_config, arguments.output,
    )


if __name__ == "__main__":
    main()
