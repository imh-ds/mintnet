"""`pi_min` calibration (Step 3) and recall/removal validation (Step 4)
for Stage 9c's own raw evidence. See docs/stage9c_charter.md.

Development/validation split by replicate PARITY (even/odd) -- D-079's
own precedent for "a clean, non-data-driven held-out check" -- serves
BOTH steps at once: `pi_min` is selected on development and confirmed
on validation (Step 3), and validation's own recall/removal at the
selected `pi_min` doubles as Step 4's own "fresh evidence" check,
since validation replicates were never used for the threshold
selection itself.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from mintnet.experiments.stage9c_bootstrap_rescue import Stage9cConfig

# Extended downward from Stage 9a's own {.70, .80, .90, .95}: a much
# smaller `bootstraps` here makes pi_final a coarser statistic, which
# may need a more lenient cut (docs/stage9c_charter.md's own Step 3).
_PI_MIN_GRID: tuple[float, ...] = (0.50, 0.60, 0.70, 0.80, 0.90)


_EXPLODED_COLUMNS = (
    "dgp", "n", "replicate", "i", "j", "is_true_edge", "retained", "category",
    "conditioning_size_used", "bootstrapped", "pi_final",
)


def explode_qualifying(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (dgp, n, replicate, i, j) -- only from replicates
    that ran successfully."""
    rows: list[dict[str, object]] = []
    for record in raw.loc[raw["status"] == "ok"].itertuples(index=False):
        for edge in json.loads(record.qualifying_json):
            rows.append(
                {
                    "dgp": record.dgp, "n": record.n, "replicate": record.replicate,
                    "i": edge["i"], "j": edge["j"], "is_true_edge": edge["is_true_edge"],
                    "retained": edge["retained"], "category": edge["category"],
                    "conditioning_size_used": edge["conditioning_size_used"],
                    "bootstrapped": edge["bootstrapped"], "pi_final": edge["pi_final"],
                }
            )
    return pd.DataFrame(rows, columns=list(_EXPLODED_COLUMNS)) if not rows else pd.DataFrame(rows)


def _filter_metrics(group: pd.DataFrame, pi_min: float) -> dict[str, float]:
    true_retained = group.loc[group["category"] == "true_retained", "pi_final"]
    false_wrongly_retained = group.loc[group["category"] == "false_wrongly_retained", "pi_final"]
    recall = float((true_retained >= pi_min).mean()) if len(true_retained) else float("nan")
    removal_rate = float((false_wrongly_retained < pi_min).mean()) if len(false_wrongly_retained) else float("nan")
    return {
        "pi_min": pi_min, "true_retained_count": len(true_retained), "recall": recall,
        "false_wrongly_retained_count": len(false_wrongly_retained), "removal_rate": removal_rate,
    }


@dataclass(frozen=True)
class Stage9cDecision:
    status: str  # "PROCEED" or "REASSESS"
    selected_pi_min: float | None
    development: dict[str, float] | None
    validation: dict[str, float] | None
    min_recall: float
    min_removal_rate: float
    min_count: int


def calibrate_and_validate(
    exploded: pd.DataFrame, min_recall: float = 0.95, min_removal_rate: float = 0.85, min_count: int = 10,
) -> Stage9cDecision:
    """Smallest eligible `pi_min` on development (replicate-even),
    confirmed on validation (replicate-odd) -- both against the
    charter's own final tolerance (`>=.95`/`>=.85`, mirroring Stage
    9b's own end-to-end bar), not the looser calibration-only bar
    Stage 9a used, since this charter combines calibration and
    end-to-end validation in one pass."""
    scored = exploded.loc[exploded["bootstrapped"] & exploded["pi_final"].notna()]
    dev = scored.loc[scored["replicate"] % 2 == 0]
    val = scored.loc[scored["replicate"] % 2 == 1]

    for pi_min in sorted(_PI_MIN_GRID):
        dev_metrics = _filter_metrics(dev, pi_min)
        if dev_metrics["true_retained_count"] < min_count or dev_metrics["false_wrongly_retained_count"] < min_count:
            continue
        if dev_metrics["recall"] >= min_recall and dev_metrics["removal_rate"] >= min_removal_rate:
            val_metrics = _filter_metrics(val, pi_min)
            if val_metrics["true_retained_count"] < min_count or val_metrics["false_wrongly_retained_count"] < min_count:
                return Stage9cDecision(
                    status="REASSESS", selected_pi_min=pi_min, development=dev_metrics, validation=val_metrics,
                    min_recall=min_recall, min_removal_rate=min_removal_rate, min_count=min_count,
                )
            status = "PROCEED" if val_metrics["recall"] >= min_recall and val_metrics["removal_rate"] >= min_removal_rate else "REASSESS"
            return Stage9cDecision(
                status=status, selected_pi_min=pi_min, development=dev_metrics, validation=val_metrics,
                min_recall=min_recall, min_removal_rate=min_removal_rate, min_count=min_count,
            )
    return Stage9cDecision(
        status="REASSESS", selected_pi_min=None, development=None, validation=None,
        min_recall=min_recall, min_removal_rate=min_removal_rate, min_count=min_count,
    )


def write_report(raw: pd.DataFrame, config: "Stage9cConfig", output_dir: Path) -> Stage9cDecision:
    exploded = explode_qualifying(raw)
    decision = calibrate_and_validate(exploded)

    output_dir.mkdir(parents=True, exist_ok=True)
    exploded.to_csv(output_dir / "exploded_qualifying.csv", index=False)
    (output_dir / "decision.json").write_text(json.dumps(asdict(decision), indent=2) + "\n", encoding="utf-8")
    return decision
