"""Shared detection-limit/frontier analysis for Stage 7d's two evidence
runners (structured-density sweep and CMIknn baseline) -- factored out
so both sides' reports (and the final head-to-head comparison) use the
exact same feasibility definition. Mirrors
`mintnet.experiments.stage7b_frontier_reporting`'s own
`operating_frontier`/`detection_limit_summary` logic, generalized
across the three DGP families in `mintnet.experiments.stage7d_conditions`.
See docs/stage7d_charter.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mintnet.experiments.stage7d_conditions import CURVATURE_RHOS, USHAPE_CURVATURES, condition_label

ALPHAS: tuple[float, ...] = tuple(round(a, 2) for a in np.arange(0.01, 0.51, 0.01))
INDIRECT_PRUNE_TPR_FLOOR = 0.80
DIRECT_EDGE_POWER_FLOOR = 0.90

# (family, null_condition, positive params) -- `curvature` has no null
# condition of its own; independence at `target_rho=0` is the same
# population claim as `linear`'s own null (a monotonic transform of one
# variable preserves independence), so `linear_0.0` is reused as its
# null reference, disclosed here rather than silently assumed.
FAMILY_SPECS: tuple[tuple[str, str, tuple[float, ...]], ...] = (
    ("linear", condition_label("linear", 0.0), (0.08, 0.12, 0.15, 0.20)),
    ("curvature", condition_label("linear", 0.0), CURVATURE_RHOS),
    ("ushape", condition_label("ushape", 0.0), tuple(c for c in USHAPE_CURVATURES if c > 0.0)),
)


def rejection_curve(p_values: pd.Series) -> dict[float, float]:
    values = p_values.dropna().to_numpy()
    if values.size == 0:
        return {alpha: float("nan") for alpha in ALPHAS}
    return {alpha: float((values <= alpha).mean()) for alpha in ALPHAS}


def _feasible(null_curve: dict[float, float], power_curve: dict[float, float]) -> bool:
    return any(
        (1.0 - null_curve[alpha]) >= INDIRECT_PRUNE_TPR_FLOOR and power_curve[alpha] >= DIRECT_EDGE_POWER_FLOOR
        for alpha in ALPHAS
        if np.isfinite(null_curve[alpha]) and np.isfinite(power_curve[alpha])
    )


def family_detection_limit(
    raw: pd.DataFrame, condition_column: str, p_value_column: str, n: int, group_filter: pd.Series | None = None
) -> dict[str, float | None]:
    """Per DGP family, the smallest positive parameter (`target_rho` or
    `curvature`) at which some `alpha` simultaneously clears the
    null-side pruning floor and the direct-edge power floor at this
    `N` -- `None` if no tested parameter clears it. `group_filter`
    additionally restricts rows (e.g. to one `degree` or one `k_cmi`)."""
    base = raw.loc[raw["n"] == n]
    if group_filter is not None:
        base = base.loc[group_filter]

    limits: dict[str, float | None] = {}
    for family, null_condition, params in FAMILY_SPECS:
        null_cell = base.loc[(base[condition_column] == null_condition) & (base["status"] == "ok")]
        null_curve = rejection_curve(null_cell[p_value_column])

        detection_limit: float | None = None
        for param in sorted(params):
            condition = condition_label(family, param)
            cell = base.loc[(base[condition_column] == condition) & (base["status"] == "ok")]
            power_curve = rejection_curve(cell[p_value_column])
            if _feasible(null_curve, power_curve):
                detection_limit = param
                break
        limits[family] = detection_limit
    return limits
