import json

import numpy as np
import pandas as pd
import pytest

from mintnet.experiments.stage9a_bootstrap_stability import (
    Stage9aConfig,
    _category,
    expected_combinations,
    expected_row_count,
    run_stage9a,
)
from mintnet.experiments.stage9a_bootstrap_stability_reporting import (
    calibrate_pi_min_filter,
    evaluate_h9,
    explode_qualifying,
    pi_final_summary,
)


def _config(**overrides) -> Stage9aConfig:
    values = dict(
        sample_sizes=(1000, 1750),
        strength=0.5,
        screening_alpha=0.001,
        max_conditioning_size=4,
        replicates=40,
        base_master_seed=80200,
        bootstrap_master_seed=80900,
        bootstraps=10,
        max_bootstrapped_replicates_per_cell=3,
        development_replicates=(0, 19),
        validation_replicates=(20, 39),
    )
    values.update(overrides)
    return Stage9aConfig(**values)


def test_category_labels():
    assert _category(is_true_edge=True, retained=True) == "true_retained"
    assert _category(is_true_edge=True, retained=False) == "true_wrongly_pruned"
    assert _category(is_true_edge=False, retained=True) == "false_wrongly_retained"
    assert _category(is_true_edge=False, retained=False) == "false_correctly_pruned"


def test_expected_row_count_matches_the_full_grid():
    config = _config()
    assert expected_row_count(config) == 2 * 2 * 40
    combos = expected_combinations(config)
    assert ("chain_fork_hub", 1000, 0) in combos
    assert ("overlap", 1750, 39) in combos


def test_run_stage9a_produces_one_row_per_expected_combination(tmp_path):
    config = _config()
    raw = run_stage9a(config, tmp_path / "out", write_report=False)
    combos = set(zip(raw["dgp"], raw["n"], raw["replicate"]))
    assert combos == expected_combinations(config)
    assert len(raw) == expected_row_count(config)
    assert (raw["status"] == "ok").all()


def test_run_stage9a_respects_the_bootstrap_cap_per_cell_and_partition(tmp_path):
    """No more than max_bootstrapped_replicates_per_cell replicates may
    pay the bootstrap cost within EITHER the development or the
    validation partition of any (dgp, n) cell -- tracked separately per
    partition (D-077's own fix), not as one global running count, so a
    front-loaded qualifying rate in one partition cannot starve the
    other of any bootstrapped instances at all."""
    config = _config(
        replicates=200, max_bootstrapped_replicates_per_cell=3,
        development_replicates=(0, 99), validation_replicates=(100, 199),
    )
    raw = run_stage9a(config, tmp_path / "out", write_report=False)

    for (dgp, n), group in raw.groupby(["dgp", "n"]):
        bootstrapped_by_partition = {"development": set(), "validation": set()}
        for _, row in group.iterrows():
            partition = "development" if row["replicate"] <= 99 else "validation"
            for edge in json.loads(row["qualifying_json"]):
                if edge["bootstrapped"]:
                    bootstrapped_by_partition[partition].add(row["replicate"])
        assert len(bootstrapped_by_partition["development"]) <= 3
        assert len(bootstrapped_by_partition["validation"]) <= 3


def test_run_stage9a_gives_both_partitions_a_chance_to_reach_the_cap_independently(tmp_path):
    """D-077's own regression test: a qualifying-replicate rate dense
    enough to exhaust the cap well within the development range alone
    must not leave validation with zero bootstrapped instances."""
    config = _config(
        replicates=200, max_bootstrapped_replicates_per_cell=3,
        development_replicates=(0, 99), validation_replicates=(100, 199),
    )
    raw = run_stage9a(config, tmp_path / "out", write_report=False)

    for (dgp, n), group in raw.groupby(["dgp", "n"]):
        validation_bootstrapped = False
        for _, row in group.iterrows():
            if row["replicate"] <= 99:
                continue
            for edge in json.loads(row["qualifying_json"]):
                if edge["bootstrapped"]:
                    validation_bootstrapped = True
        # Not every cell is guaranteed a qualifying edge in this small a
        # smoke-scale replicate range, but at least one of the four
        # (dgp, n) cells here should show validation got its own share.
        if validation_bootstrapped:
            return
    pytest.fail("no (dgp, n) cell's own validation partition ever got a bootstrapped instance")


def test_run_stage9a_replicates_that_skip_bootstrap_have_null_pi_final(tmp_path):
    config = _config(replicates=200, max_bootstrapped_replicates_per_cell=1)
    raw = run_stage9a(config, tmp_path / "out", write_report=False)

    saw_a_skip = False
    for _, row in raw.iterrows():
        for edge in json.loads(row["qualifying_json"]):
            if not edge["bootstrapped"]:
                saw_a_skip = True
                assert edge["pi_final"] is None
    assert saw_a_skip  # sanity: the cap actually bound something in this run


def test_run_stage9a_is_deterministic_given_the_same_config_and_seed(tmp_path):
    config = _config()
    first = run_stage9a(config, tmp_path / "a", write_report=False)
    second = run_stage9a(config, tmp_path / "b", write_report=False)
    columns = [c for c in first.columns if c != "elapsed_seconds"]
    pd.testing.assert_frame_equal(first[columns], second[columns])


def test_explode_qualifying_and_pi_final_summary(tmp_path):
    config = _config(replicates=200, max_bootstrapped_replicates_per_cell=5)
    raw = run_stage9a(config, tmp_path / "out", write_report=False)
    exploded = explode_qualifying(raw)
    assert set(exploded.columns) >= {"dgp", "n", "replicate", "i", "j", "category", "pi_final", "bootstrapped"}
    if not exploded.empty:
        summary = pi_final_summary(exploded)
        assert (summary["count"] > 0).all()


def test_evaluate_h9_confirms_when_wrongly_retained_is_reliably_lower():
    rng = np.random.default_rng(0)
    true_retained = pd.Series(rng.uniform(0.9, 1.0, size=50))
    false_wrongly_retained = pd.Series(rng.uniform(0.4, 0.6, size=50))
    exploded = pd.concat(
        [
            pd.DataFrame({"dgp": "chain_fork_hub", "n": 1000, "category": "true_retained", "pi_final": true_retained, "bootstrapped": True}),
            pd.DataFrame({"dgp": "chain_fork_hub", "n": 1000, "category": "false_wrongly_retained", "pi_final": false_wrongly_retained, "bootstrapped": True}),
        ]
    )
    verdict = evaluate_h9(exploded, min_count=20)
    assert verdict.status == "CONFIRMED"


def test_evaluate_h9_not_confirmed_when_distributions_overlap_fully():
    rng = np.random.default_rng(1)
    true_retained = pd.Series(rng.uniform(0.4, 1.0, size=50))
    false_wrongly_retained = pd.Series(rng.uniform(0.4, 1.0, size=50))
    exploded = pd.concat(
        [
            pd.DataFrame({"dgp": "chain_fork_hub", "n": 1000, "category": "true_retained", "pi_final": true_retained, "bootstrapped": True}),
            pd.DataFrame({"dgp": "chain_fork_hub", "n": 1000, "category": "false_wrongly_retained", "pi_final": false_wrongly_retained, "bootstrapped": True}),
        ]
    )
    verdict = evaluate_h9(exploded, min_count=20)
    assert verdict.status == "NOT_CONFIRMED"


def test_evaluate_h9_inconclusive_below_min_count():
    exploded = pd.DataFrame(
        {
            "dgp": ["chain_fork_hub"] * 4,
            "n": [1000] * 4,
            "category": ["true_retained", "true_retained", "false_wrongly_retained", "false_wrongly_retained"],
            "pi_final": [0.9, 0.95, 0.5, 0.55],
            "bootstrapped": [True, True, True, True],
        }
    )
    verdict = evaluate_h9(exploded, min_count=20)
    assert verdict.status == "INCONCLUSIVE"


def test_calibrate_pi_min_filter_proceeds_with_clean_separation():
    rng = np.random.default_rng(2)

    def _make(replicate_range, n_each=60):
        replicates = rng.integers(replicate_range[0], replicate_range[1] + 1, size=n_each * 2)
        true_retained = pd.DataFrame(
            {"category": "true_retained", "pi_final": rng.uniform(0.9, 1.0, size=n_each), "replicate": replicates[:n_each], "bootstrapped": True}
        )
        false_wrongly_retained = pd.DataFrame(
            {"category": "false_wrongly_retained", "pi_final": rng.uniform(0.3, 0.6, size=n_each), "replicate": replicates[n_each:], "bootstrapped": True}
        )
        return pd.concat([true_retained, false_wrongly_retained])

    exploded = pd.concat([_make((0, 29)), _make((30, 59))])
    decision = calibrate_pi_min_filter(exploded, development_replicates=(0, 29), validation_replicates=(30, 59))
    assert decision.status == "PROCEED"
    assert decision.selected_pi_min is not None


def test_calibrate_pi_min_filter_reassesses_when_no_threshold_works():
    rng = np.random.default_rng(3)

    def _make(replicate_range, n_each=60):
        replicates = rng.integers(replicate_range[0], replicate_range[1] + 1, size=n_each * 2)
        true_retained = pd.DataFrame(
            {"category": "true_retained", "pi_final": rng.uniform(0.5, 1.0, size=n_each), "replicate": replicates[:n_each], "bootstrapped": True}
        )
        false_wrongly_retained = pd.DataFrame(
            {"category": "false_wrongly_retained", "pi_final": rng.uniform(0.5, 1.0, size=n_each), "replicate": replicates[n_each:], "bootstrapped": True}
        )
        return pd.concat([true_retained, false_wrongly_retained])

    exploded = pd.concat([_make((0, 29)), _make((30, 59))])
    decision = calibrate_pi_min_filter(exploded, development_replicates=(0, 29), validation_replicates=(30, 59))
    assert decision.status == "REASSESS"
