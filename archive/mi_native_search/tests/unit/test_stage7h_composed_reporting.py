import json

import numpy as np
import pandas as pd

from mintnet.experiments.stage7h_composed_reporting import (
    accessibility_gate,
    confidence_transfer_check,
    evaluate,
    explode_qualifying,
    stratified_accuracy_table,
)


def _row(condition, dgp, strength, n, replicate, edges):
    return {
        "condition": condition, "dgp": dgp, "strength": strength, "n": n, "replicate": replicate,
        "alpha": 0.1, "seed": 0, "qualifying_json": json.dumps(edges), "n_qualifying": len(edges),
        "elapsed_seconds": 1.0, "status": "ok", "error": "",
    }


def _edge(i, j, is_true, retained, size, p, confidence):
    return {
        "i": i, "j": j, "is_true_edge": is_true, "retained": retained,
        "conditioning_size_used": size, "decisive_p_value": p, "confidence": confidence,
    }


def test_explode_qualifying_only_uses_ok_rows():
    rows = [
        _row("chain_fork_hub_0", "chain_fork_hub", 0.5, 400, 0, [_edge(0, 1, True, True, 1, 0.01, 0.9)]),
        {**_row("chain_fork_hub_0", "chain_fork_hub", 0.5, 400, 1, []), "status": "error", "error": "boom"},
    ]
    raw = pd.DataFrame(rows)
    exploded = explode_qualifying(raw)
    assert len(exploded) == 1
    assert bool(exploded.iloc[0]["is_true_edge"]) is True


def test_stratified_accuracy_table_separates_retain_from_prune_reliability():
    exploded = pd.DataFrame(
        [
            {"condition": "c", "dgp": "chain_fork_hub", "strength": 0.5, "n": 400, "replicate": 0,
             "i": 0, "j": 1, "is_true_edge": True, "retained": True, "conditioning_size_used": 1,
             "decisive_p_value": 0.01, "confidence": 0.9},
            {"condition": "c", "dgp": "chain_fork_hub", "strength": 0.5, "n": 400, "replicate": 1,
             "i": 0, "j": 1, "is_true_edge": True, "retained": True, "conditioning_size_used": 1,
             "decisive_p_value": 0.01, "confidence": 0.9},
            {"condition": "c", "dgp": "chain_fork_hub", "strength": 0.5, "n": 400, "replicate": 0,
             "i": 0, "j": 2, "is_true_edge": False, "retained": True, "conditioning_size_used": 2,
             "decisive_p_value": 0.5, "confidence": 0.3},
            {"condition": "c", "dgp": "chain_fork_hub", "strength": 0.5, "n": 400, "replicate": 1,
             "i": 0, "j": 2, "is_true_edge": False, "retained": False, "conditioning_size_used": 2,
             "decisive_p_value": 0.02, "confidence": 0.8},
        ]
    )
    table = stratified_accuracy_table(exploded)

    true_edge_row = table.loc[table["is_true_edge"]].iloc[0]
    assert true_edge_row["accuracy"] == 1.0
    assert true_edge_row["count"] == 2

    false_edge_row = table.loc[~table["is_true_edge"]].iloc[0]
    assert false_edge_row["accuracy"] == 0.5  # one correctly pruned, one wrongly retained
    assert false_edge_row["count"] == 2


def test_accessibility_gate_reassesses_below_the_min_true_edge_accuracy():
    table = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "strength": 0.5, "n": 400, "is_true_edge": True, "conditioning_size_used": 1, "count": 100, "accuracy": 0.99},
            {"dgp": "overlap", "strength": 0.5, "n": 400, "is_true_edge": True, "conditioning_size_used": 3, "count": 100, "accuracy": 0.80},
        ]
    )
    status, min_accuracy = accessibility_gate(table)
    assert status == "REASSESS"
    assert min_accuracy == 0.80


def test_accessibility_gate_proceeds_when_every_true_edge_cell_clears_the_bar():
    table = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "strength": 0.5, "n": 400, "is_true_edge": True, "conditioning_size_used": 1, "count": 100, "accuracy": 0.99},
            {"dgp": "overlap", "strength": 0.5, "n": 400, "is_true_edge": True, "conditioning_size_used": 3, "count": 100, "accuracy": 0.96},
        ]
    )
    status, min_accuracy = accessibility_gate(table)
    assert status == "PROCEED"
    assert min_accuracy == 0.96


def test_confidence_transfer_check_proceeds_when_confidence_is_informative_and_trends_with_n():
    rng = np.random.default_rng(0)
    rows = []
    for n in (400, 750, 1500):
        for replicate in range(30):
            correct = replicate % 3 != 0  # 2/3 correct
            confidence = rng.normal(loc=0.8 if correct else 0.3, scale=0.05) + 0.0001 * n
            rows.append(
                {
                    "condition": "overlap_0", "dgp": "overlap", "strength": 0.5, "n": n, "replicate": replicate,
                    "i": 0, "j": 1, "is_true_edge": True, "retained": correct, "conditioning_size_used": 3,
                    "decisive_p_value": 0.01, "confidence": float(np.clip(confidence, 0.0, 1.0)),
                }
            )
    exploded = pd.DataFrame(rows)

    transfer = confidence_transfer_check(exploded, min_count=10)
    row = transfer.loc[(transfer["dgp"] == "overlap") & (transfer["strength"] == 0.5)].iloc[0]
    assert row["status"] == "PROCEED"


def test_confidence_transfer_check_reassesses_below_min_count():
    exploded = pd.DataFrame(
        [
            {"condition": "overlap_0", "dgp": "overlap", "strength": 0.5, "n": 400, "replicate": 0,
             "i": 0, "j": 1, "is_true_edge": True, "retained": True, "conditioning_size_used": 3,
             "decisive_p_value": 0.01, "confidence": 0.9},
        ]
    )
    transfer = confidence_transfer_check(exploded, min_count=20)
    row = transfer.iloc[0]
    assert row["status"] == "REASSESS"


def test_evaluate_combines_both_parts():
    table = pd.DataFrame(
        [{"dgp": "chain_fork_hub", "strength": 0.5, "n": 400, "is_true_edge": True, "conditioning_size_used": 1, "count": 100, "accuracy": 0.99}]
    )
    transfer = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "strength": 0.5, "n_decisions": 100, "mean_confidence_correct": 0.8,
             "mean_confidence_incorrect": 0.3, "informative": True, "spearman_correlation": 0.2,
             "spearman_p_value": 0.001, "significant_positive_trend": True, "status": "PROCEED"},
            {"dgp": "overlap", "strength": 0.5, "n_decisions": 100, "mean_confidence_correct": 0.5,
             "mean_confidence_incorrect": 0.5, "informative": False, "spearman_correlation": 0.0,
             "spearman_p_value": 0.9, "significant_positive_trend": False, "status": "REASSESS"},
        ]
    )
    decision = evaluate(table, transfer)
    assert decision.part_a_status == "PROCEED"
    assert decision.part_b_status == "REASSESS"
    assert decision.part_b_failing_cells == [["overlap", 0.5]]
