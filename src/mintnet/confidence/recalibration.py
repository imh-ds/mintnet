"""Isotonic recalibration mapping for the Tier-0 margin score. See
docs/stage8b_charter.md and D-066 (docs/decision_log.md).

Fits, per (motif_family, N), a monotonic margin -> P(correct) curve
from Stage 8a's own already-collected evidence, on a development split
of the replicates; validated on a disjoint held-out split before use.
Additive alongside mintnet.confidence.margin.edge_margin -- raw margin
remains available everywhere; this is an opt-in correction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

# Two validated, disjoint-keyed fitted artifacts, merged into one
# default lookup:
# - D-067's own isotonic curves per (motif_family, N) for the isolated
#   3-node fixtures (chain/fork/triangle/weak_edge_triangle), fit on
#   Stage 8a's development replicates (0-2499), held-out-validated on
#   2500-4999 (docs/decision_log.md D-067).
# - D-070's own isotonic curves for the composed-tier false-edge case
#   (chain_fork_hub/overlap), fit on Stage 8c's development replicates
#   (0-999), held-out-validated on 1000-1999 (docs/decision_log.md
#   D-070, docs/stage8e_charter.md). These two DGP names refer to
#   specific whole-network synthetic constructions, not a general
#   composed-network label -- see growing_subset_dpi's own docstring
#   for the scope caveat this implies for any caller passing them.
# Only these six motif families, at their own respective validated N
# ranges, are covered -- see calibrated_margin.
_DEFAULT_CURVES_PATHS = (
    Path(__file__).parent / "fitted" / "chain_fork_margin_curves.json",
    Path(__file__).parent / "fitted" / "composed_false_edge_curves.json",
)


@dataclass(frozen=True)
class IsotonicCurve:
    """A fitted monotonic margin -> P(correct) step function, stored as
    plain data (not a live sklearn object) so it can be serialized and
    applied without re-fitting or pickling model internals."""

    x_thresholds: tuple[float, ...]
    y_values: tuple[float, ...]

    def predict(self, margin: float) -> float:
        return float(np.interp(margin, self.x_thresholds, self.y_values))


def fit_isotonic_curve(margins: np.ndarray, correct: np.ndarray) -> IsotonicCurve:
    model = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
    model.fit(margins, correct)
    return IsotonicCurve(
        x_thresholds=tuple(float(x) for x in model.X_thresholds_),
        y_values=tuple(float(y) for y in model.y_thresholds_),
    )


def _motif_family(condition: str) -> str:
    family, _, _ = condition.rpartition("_")
    return family


def _in_replicate_range(raw: pd.DataFrame, replicate_range: tuple[int, int]) -> pd.DataFrame:
    low, high = replicate_range
    return raw.loc[(raw["replicate"] >= low) & (raw["replicate"] <= high)]


def fit_calibration_curves(
    raw: pd.DataFrame, development_replicates: tuple[int, int]
) -> dict[tuple[str, int], IsotonicCurve]:
    """One isotonic curve per (motif_family, n), fit only on the
    development replicate range and only on valid (status=='ok',
    non-NaN margin) rows."""
    scored = raw.loc[(raw["status"] == "ok") & raw["margin"].notna()].copy()
    scored = _in_replicate_range(scored, development_replicates)
    scored["motif_family"] = scored["condition"].map(_motif_family)

    curves: dict[tuple[str, int], IsotonicCurve] = {}
    for (motif_family, n), group in scored.groupby(["motif_family", "n"]):
        curves[(motif_family, int(n))] = fit_isotonic_curve(
            group["margin"].to_numpy(dtype=float), group["correct"].to_numpy(dtype=float)
        )
    return curves


@lru_cache(maxsize=1)
def default_curves() -> dict[tuple[str, int], IsotonicCurve]:
    """D-067's and D-070's own validated fitted artifacts, merged (see
    the module docstring and docs/decision_log.md). Loaded once,
    cached for the process."""
    merged: dict[tuple[str, int], IsotonicCurve] = {}
    for path in _DEFAULT_CURVES_PATHS:
        merged.update(load_curves(path))
    return merged


def calibrated_margin(
    margin: float, n: int, motif_family: str, curves: dict[tuple[str, int], IsotonicCurve] | None = None
) -> float:
    """Recalibrated probability for a single edge decision. Snaps to
    the nearest tested N a curve exists for -- does not interpolate
    between tested N values (unvalidated at any untested N) -- and
    raises outside the tested N range or for an unknown motif family.
    Defaults to D-067's own validated fitted curves when `curves` is
    not given explicitly (tests and refitting pass their own)."""
    if curves is None:
        curves = default_curves()
    available_ns = sorted({tested_n for family, tested_n in curves if family == motif_family})
    if not available_ns:
        raise ValueError(f"no fitted calibration curve for motif family {motif_family!r}")
    if n < available_ns[0] or n > available_ns[-1]:
        raise ValueError(
            f"n={n} is outside the validated range [{available_ns[0]}, {available_ns[-1]}] "
            f"for motif family {motif_family!r}"
        )
    nearest_n = min(available_ns, key=lambda tested_n: abs(tested_n - n))
    return curves[(motif_family, nearest_n)].predict(margin)


def evaluate_recalibrated_ece(
    raw: pd.DataFrame,
    curves: dict[tuple[str, int], IsotonicCurve],
    validation_replicates: tuple[int, int],
    bin_count: int,
) -> pd.DataFrame:
    """Re-derive the same bin-table/ECE analysis Stage 8a's own
    reporting module uses, but on the recalibrated score, over the
    validation replicate range only -- never the replicates the curves
    were fit on."""
    from mintnet.experiments.stage8a_calibration_reporting import bin_table

    scored = raw.loc[(raw["status"] == "ok") & raw["margin"].notna()].copy()
    scored = _in_replicate_range(scored, validation_replicates)
    scored["motif_family"] = scored["condition"].map(_motif_family)

    scored["recalibrated"] = [
        calibrated_margin(margin, int(n), motif_family, curves)
        for margin, n, motif_family in zip(scored["margin"], scored["n"], scored["motif_family"])
    ]
    # bin_table groups by "motif"/"margin" column names -- reuse it by
    # presenting the recalibrated score under those names.
    relabeled = scored.rename(columns={"motif_family": "motif"})
    relabeled["margin"] = relabeled["recalibrated"]
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    relabeled["bin"] = pd.cut(relabeled["margin"], bins=edges, include_lowest=True, labels=False)
    return bin_table(relabeled, bin_count)


def save_curves(curves: dict[tuple[str, int], IsotonicCurve], path: Path) -> None:
    payload = [
        {"motif_family": motif_family, "n": n, "x_thresholds": list(curve.x_thresholds), "y_values": list(curve.y_values)}
        for (motif_family, n), curve in sorted(curves.items())
    ]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_curves(path: Path) -> dict[tuple[str, int], IsotonicCurve]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        (entry["motif_family"], int(entry["n"])): IsotonicCurve(
            x_thresholds=tuple(entry["x_thresholds"]), y_values=tuple(entry["y_values"])
        )
        for entry in payload
    }
