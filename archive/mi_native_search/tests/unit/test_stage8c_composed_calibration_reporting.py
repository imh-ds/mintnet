import json

import numpy as np
import pandas as pd

from mintnet.experiments.stage8c_composed_calibration_reporting import (
    evaluate_stage8c_gate,
    explode_edges,
    exploratory_false_edge_recalibration,
)


class _FakeConfig:
    def __init__(self, ece_tolerance=0.10, bin_count=10, development_replicates=(0, 249), validation_replicates=(250, 499)):
        self.ece_tolerance = ece_tolerance
        self.bin_count = bin_count
        self.development_replicates = development_replicates
        self.validation_replicates = validation_replicates


def _edges_row(dgp, n, replicate, edges):
    return {"dgp": dgp, "n": n, "replicate": replicate, "edges_json": json.dumps(edges), "status": "ok"}


def test_explode_edges_produces_one_row_per_edge_and_skips_error_replicates() -> None:
    raw = pd.DataFrame(
        [
            _edges_row("chain_fork_hub", 750, 0, [
                {"i": 0, "j": 1, "is_true_edge": True, "decisive_p_value": 0.001, "margin": 0.9, "retained": True, "correct": True},
                {"i": 0, "j": 2, "is_true_edge": False, "decisive_p_value": 0.5, "margin": 0.3, "retained": False, "correct": True},
            ]),
            {"dgp": "chain_fork_hub", "n": 750, "replicate": 1, "edges_json": "[]", "status": "error"},
        ]
    )
    exploded = explode_edges(raw)
    assert len(exploded) == 2
    assert set(exploded["is_true_edge"]) == {True, False}


def _synthetic_exploded(rng: np.random.Generator, dgp: str, n: int, replicates: int, well_calibrated: bool) -> pd.DataFrame:
    rows = []
    for replicate in range(replicates):
        for is_true_edge in (True, False):
            margin = rng.uniform(0.0, 1.0)
            if well_calibrated:
                correct = float(rng.uniform() < margin)
            else:
                correct = 1.0 if margin >= 0.9 else float(rng.uniform() < 0.9)
            rows.append(
                {"dgp": dgp, "n": n, "replicate": replicate, "i": 0, "j": 1, "is_true_edge": is_true_edge,
                 "margin": margin, "correct": correct, "status": "ok"}
            )
    return pd.DataFrame(rows)


def test_evaluate_stage8c_gate_proceeds_when_true_edges_are_well_calibrated() -> None:
    rng = np.random.default_rng(0)
    exploded = _synthetic_exploded(rng, "chain_fork_hub", 750, 2000, well_calibrated=True)

    decision, true_bins, false_bins = evaluate_stage8c_gate(exploded, _FakeConfig())

    assert decision.status == "PROCEED"
    assert decision.max_true_edge_ece <= 0.10


def test_evaluate_stage8c_gate_reassesses_when_true_edges_are_flat_below_high_margin() -> None:
    """If composition broke the previously-clean true-edge calibration
    (the case D-066 never found a problem with), the gate must catch
    it -- this synthesizes exactly that failure mode."""
    rows = []
    rng = np.random.default_rng(1)
    for replicate in range(2000):
        true_margin = rng.uniform(0.0, 1.0)
        true_correct = 1.0 if true_margin >= 0.9 else float(rng.uniform() < 0.5)  # flat, uninformative below 0.9
        rows.append(
            {"dgp": "chain_fork_hub", "n": 750, "replicate": replicate, "i": 0, "j": 1,
             "is_true_edge": True, "margin": true_margin, "correct": true_correct, "status": "ok"}
        )
        false_margin = rng.uniform(0.0, 1.0)  # well-calibrated false edges -- isolates the true-edge failure
        rows.append(
            {"dgp": "chain_fork_hub", "n": 750, "replicate": replicate, "i": 0, "j": 2,
             "is_true_edge": False, "margin": false_margin, "correct": float(rng.uniform() < false_margin),
             "status": "ok"}
        )
    exploded = pd.DataFrame(rows)

    decision, _, _ = evaluate_stage8c_gate(exploded, _FakeConfig())
    assert decision.status == "REASSESS"


def test_exploratory_false_edge_recalibration_only_uses_false_edges_and_the_val_split() -> None:
    rng = np.random.default_rng(2)
    exploded = _synthetic_exploded(rng, "overlap", 750, 500, well_calibrated=False)
    config = _FakeConfig(development_replicates=(0, 249), validation_replicates=(250, 499))

    ece = exploratory_false_edge_recalibration(exploded, config)
    assert "overlap_n750" in ece
    assert ece["overlap_n750"] < 0.10  # the fresh curve should fix the same flat-region pattern D-067 fixed
