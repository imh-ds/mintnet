import json

import pandas as pd
import pytest

from mintnet.experiments.stage9b_stability_rescue_validation import (
    Stage9bConfig,
    expected_combinations,
    expected_row_count,
    run_stage9b,
)
from mintnet.experiments.stage9b_stability_rescue_validation_reporting import (
    evaluate_stage9b_gate,
    explode_qualifying,
    recall_removal_table,
)


def _config(**overrides) -> Stage9bConfig:
    values = dict(
        sample_sizes=(1000, 1750),
        strength=0.5,
        screening_alpha=0.001,
        max_conditioning_size=4,
        replicates=30,
        base_master_seed=81000,
        bootstrap_master_seed=81100,
        bootstraps=10,
        pi_min=0.90,
        max_bootstrapped_replicates_per_cell=3,
    )
    values.update(overrides)
    return Stage9bConfig(**values)


def test_expected_row_count_matches_the_full_grid():
    config = _config()
    assert expected_row_count(config) == 2 * 2 * 30
    combos = expected_combinations(config)
    assert ("chain_fork_hub", 1000, 0) in combos
    assert ("overlap", 1750, 29) in combos


def test_run_stage9b_produces_one_row_per_expected_combination(tmp_path):
    config = _config()
    raw = run_stage9b(config, tmp_path / "out", write_report=False)
    combos = set(zip(raw["dgp"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_run_stage9b_respects_the_bootstrap_cap_per_cell(tmp_path):
    config = _config(replicates=100, max_bootstrapped_replicates_per_cell=3)
    raw = run_stage9b(config, tmp_path / "out", write_report=False)

    for (dgp, n), group in raw.groupby(["dgp", "n"]):
        assert int(group["dataset_bootstrapped"].sum()) <= 3


def test_run_stage9b_uncapped_replicates_still_report_qualifying_edges_without_pi_final(tmp_path):
    """A replicate processed after the cap is exhausted still records
    its own conditioning_size_used >= 2 edges (for accuracy bookkeeping)
    but with pi_final left NaN (never bootstrapped) and rescued=False."""
    config = _config(replicates=100, max_bootstrapped_replicates_per_cell=1)
    raw = run_stage9b(config, tmp_path / "out", write_report=False)

    saw_unbootstrapped_qualifying_edge = False
    for _, row in raw.iterrows():
        if row["dataset_bootstrapped"]:
            continue
        for edge in json.loads(row["qualifying_json"]):
            saw_unbootstrapped_qualifying_edge = True
            assert edge["pi_final"] != edge["pi_final"]  # NaN
            assert edge["rescued"] is False
    assert saw_unbootstrapped_qualifying_edge


def test_run_stage9b_replicate_range_restricts_to_exactly_that_range(tmp_path):
    """Unlike Stage 9a's own partition semantics, replicate_range here
    exists purely to bound a shard's own wall-clock cost -- each
    range-restricted call gets its own FRESH cap budget, so chaining
    multiple chunks accumulates MORE bootstrapped instances in total
    than one unsharded pass with the same cap (intentional: this is
    exactly how the real dispatch reaches its own target sample size).
    This test only checks the range restriction itself, not equivalence
    to an unsharded run under a shared budget."""
    config = _config(replicates=40, max_bootstrapped_replicates_per_cell=2)
    first_chunk = run_stage9b(config, tmp_path / "a", replicate_range=(0, 19), write_report=False)
    second_chunk = run_stage9b(config, tmp_path / "b", replicate_range=(20, 39), write_report=False)

    assert set(first_chunk["replicate"]) <= set(range(0, 20))
    assert set(second_chunk["replicate"]) <= set(range(20, 40))
    for (dgp, n), group in first_chunk.groupby(["dgp", "n"]):
        assert int(group["dataset_bootstrapped"].sum()) <= 2
    for (dgp, n), group in second_chunk.groupby(["dgp", "n"]):
        assert int(group["dataset_bootstrapped"].sum()) <= 2


def test_run_stage9b_replicate_range_is_deterministic(tmp_path):
    config = _config(replicates=40, max_bootstrapped_replicates_per_cell=2)
    first = run_stage9b(config, tmp_path / "a", replicate_range=(0, 19), write_report=False)
    second = run_stage9b(config, tmp_path / "b", replicate_range=(0, 19), write_report=False)
    columns = [c for c in first.columns if c != "elapsed_seconds"]
    pd.testing.assert_frame_equal(first[columns], second[columns])


def test_run_stage9b_is_deterministic_given_the_same_config(tmp_path):
    config = _config()
    first = run_stage9b(config, tmp_path / "a", write_report=False)
    second = run_stage9b(config, tmp_path / "b", write_report=False)
    columns = [c for c in first.columns if c != "elapsed_seconds"]
    pd.testing.assert_frame_equal(first[columns], second[columns])


def test_evaluate_stage9b_gate_proceeds_when_every_cell_clears_the_bar():
    table = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "n": 1000, "true_retained_count": 50, "recall": 0.98, "false_wrongly_retained_count": 20, "removal_rate": 0.9},
            {"dgp": "overlap", "n": 1000, "true_retained_count": 60, "recall": 0.99, "false_wrongly_retained_count": 15, "removal_rate": 0.95},
        ]
    )
    decision = evaluate_stage9b_gate(table)
    assert decision.status == "PROCEED"
    assert not decision.cells_failing


def test_evaluate_stage9b_gate_reassesses_when_a_cell_fails():
    table = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "n": 1000, "true_retained_count": 50, "recall": 0.80, "false_wrongly_retained_count": 20, "removal_rate": 0.9},
        ]
    )
    decision = evaluate_stage9b_gate(table)
    assert decision.status == "REASSESS"
    assert decision.cells_failing == [["chain_fork_hub", 1000]]


def test_evaluate_stage9b_gate_inconclusive_below_min_count():
    table = pd.DataFrame(
        [{"dgp": "chain_fork_hub", "n": 1000, "true_retained_count": 3, "recall": 1.0, "false_wrongly_retained_count": 2, "removal_rate": 1.0}]
    )
    decision = evaluate_stage9b_gate(table, min_count=10)
    assert decision.status == "REASSESS"
    assert decision.cells_inconclusive == [["chain_fork_hub", 1000]]


def test_explode_and_recall_removal_table_end_to_end(tmp_path):
    config = _config(replicates=60, max_bootstrapped_replicates_per_cell=5)
    raw = run_stage9b(config, tmp_path / "out", write_report=False)
    exploded = explode_qualifying(raw)
    assert set(exploded.columns) >= {"dgp", "n", "replicate", "i", "j", "is_true_edge", "pi_final", "rescued"}
    table = recall_removal_table(exploded)
    if not table.empty:
        assert (table["true_retained_count"] >= 0).all()
