from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mintnet.experiments.cin_baseline import load_config
from mintnet.experiments.cin_baseline_reporting import (
    aggregate_panel_metrics,
    select_development_delta,
)


ROOT = Path(__file__).resolve().parents[2]


def _row(
    *,
    case: str,
    phase: str,
    replicate: int,
    precision: float,
    strong_recall: float,
    ap: float = 0.3,
    empty: bool = False,
) -> dict[str, object]:
    return {
        "case": case,
        "phase": phase,
        "replicate": replicate,
        "method": "cin",
        "status": "complete",
        "ap": ap,
        "delta_005_precision": precision,
        "delta_005_empty": empty,
        "delta_005_recall": strong_recall,
        "delta_01_precision": min(0.95, precision + 0.05),
        "delta_01_empty": empty,
        "delta_01_recall": min(1.0, strong_recall + 0.1),
        "delta_02_precision": min(0.99, precision + 0.1),
        "delta_02_empty": empty,
        "delta_02_recall": min(1.0, strong_recall + 0.2),
        "strong_edge_recall": strong_recall,
    }


def test_select_development_delta_uses_only_cin_a_b_and_prefers_recall() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    rows = []
    for replicate in (0, 1):
        rows.extend(
            [
                _row(case="A", phase="development", replicate=replicate, precision=0.75, strong_recall=0.4),
                _row(case="B", phase="development", replicate=replicate, precision=0.75, strong_recall=0.4),
            ]
        )
    rows.append(_row(case="A", phase="validation", replicate=1000, precision=0.01, strong_recall=0.0))
    rows.append({**rows[0], "method": "cin_linear", "delta_005_precision": 0.01})

    selection = select_development_delta(pd.DataFrame(rows), config)

    assert selection["selected_delta"] == pytest.approx(0.02)
    assert selection["expected_gate_failure"] is False
    assert selection["selection_phase"] == "development"
    assert all(candidate["phase"] == "development" for candidate in selection["candidates"])


def test_select_development_delta_marks_fallback_when_no_candidate_qualifies() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    rows = [
        _row(case=case, phase="development", replicate=0, precision=0.40, strong_recall=0.1)
        for case in ("A", "B")
    ]

    selection = select_development_delta(pd.DataFrame(rows), config)

    assert selection["expected_gate_failure"] is True
    assert selection["selected_delta"] == pytest.approx(0.02)
    assert selection["fallback_reason"] == "no candidate met development precision/nonempty rule"


def test_aggregate_panel_metrics_preserves_counts_and_mcse() -> None:
    config = load_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    raw = pd.DataFrame(
        [
            _row(case="A", phase="development", replicate=0, precision=0.7, strong_recall=0.2, ap=0.2),
            _row(case="A", phase="development", replicate=1, precision=0.8, strong_recall=0.3, ap=0.4),
        ]
    )

    summary = aggregate_panel_metrics(raw, pd.DataFrame(), config, selected_delta=0.01)
    ap = summary.loc[
        (summary["case"] == "A")
        & (summary["phase"] == "development")
        & (summary["method"] == "cin")
        & (summary["metric"] == "ap")
    ].iloc[0]

    assert ap["n"] == 2
    assert ap["mean"] == pytest.approx(0.3)
    assert ap["mcse"] == pytest.approx(0.1)
