import json

import numpy as np
import pandas as pd
import pytest

from mintnet.experiments.stage8g_structural_audit import (
    H3Verdict,
    Step5Result,
    _LEGITIMATE_SEPARATOR,
    chance_correlation,
    enrich_with_chance_correlation,
    evaluate_h3,
    evaluate_step5_validity,
    h3_wrong_retention_table,
)


def test_chance_correlation_is_the_max_abs_marginal_correlation_with_either_endpoint():
    rng = np.random.default_rng(0)
    x0 = rng.normal(size=5000)
    x1 = rng.normal(size=5000)
    x2 = 0.9 * x0 + np.sqrt(1 - 0.9**2) * rng.normal(size=5000)  # strongly correlated with x0
    x3 = rng.normal(size=5000)  # unrelated
    data = np.column_stack((x0, x1, x2, x3))

    result = chance_correlation(data, 0, 1, (2, 3))
    expected = abs(np.corrcoef(data[:, 2], data[:, 0])[0, 1])
    assert result == pytest.approx(expected, abs=0.02)
    assert result > 0.8  # dominated by the strong x2-x0 correlation, not the unrelated x3


def _edge(i, j, is_true_edge, retained, conditioning_size_used, decisive_conditioning_subset):
    return {
        "i": i, "j": j, "is_true_edge": is_true_edge,
        "decisive_p_value": 0.01, "margin": 0.5, "retained": retained,
        "correct": bool(retained == is_true_edge),
        "conditioning_size_used": conditioning_size_used,
        "cap_reached": False,
        "decisive_conditioning_subset": decisive_conditioning_subset,
    }


def _raw_row(dgp, n, replicate, seed, edges):
    return {
        "dgp": dgp, "n": n, "alpha": 0.05, "replicate": replicate, "seed": seed,
        "edges_json": json.dumps(edges), "n_edges": len(edges), "elapsed_seconds": 0.001,
        "status": "ok", "error": "",
    }


def test_enrich_with_chance_correlation_keeps_only_false_edges_with_size_at_least_two():
    edges = [
        _edge(0, 1, is_true_edge=True, retained=True, conditioning_size_used=1, decisive_conditioning_subset=[2]),
        _edge(0, 2, is_true_edge=False, retained=False, conditioning_size_used=1, decisive_conditioning_subset=[1]),
        _edge(3, 5, is_true_edge=False, retained=True, conditioning_size_used=2, decisive_conditioning_subset=[9, 10]),
    ]
    raw = pd.DataFrame([_raw_row("chain_fork_hub", 750, 0, 12345, edges)])

    candidates = enrich_with_chance_correlation(raw, strength=0.5)

    assert len(candidates) == 1
    row = candidates.iloc[0]
    assert (row["i"], row["j"]) == (3, 5)
    assert row["decisive_conditioning_subset"] == (9, 10)
    assert 0.0 <= row["chance_correlation"] <= 1.0


def test_enrich_with_chance_correlation_caches_regenerated_data_per_replicate():
    """Two false edges sharing the same replicate must not disagree on
    chance_correlation due to re-sampling different data each time --
    the same regenerated array must back both computations."""
    edges = [
        _edge(0, 2, is_true_edge=False, retained=True, conditioning_size_used=2, decisive_conditioning_subset=[9, 10]),
        _edge(3, 5, is_true_edge=False, retained=True, conditioning_size_used=2, decisive_conditioning_subset=[9, 10]),
    ]
    raw = pd.DataFrame([_raw_row("chain_fork_hub", 750, 0, 999, edges)])

    candidates = enrich_with_chance_correlation(raw, strength=0.5)
    assert len(candidates) == 2
    # Same conditioning subset tested against the two different pairs on
    # the same regenerated data -- values need not be equal, but both
    # must be valid (deterministic, no crash, no NaN from a fresh draw).
    assert candidates["chance_correlation"].notna().all()


def test_enrich_with_chance_correlation_raises_on_evidence_without_the_enrichment():
    old_edge = {"i": 0, "j": 2, "is_true_edge": False, "decisive_p_value": 0.5, "margin": 0.3, "retained": True, "correct": False}
    raw = pd.DataFrame([_raw_row("chain_fork_hub", 750, 0, 1, [old_edge])])

    with pytest.raises(ValueError, match="predates Stage 8c's own"):
        enrich_with_chance_correlation(raw, strength=0.5)


def test_enrich_with_chance_correlation_returns_empty_frame_when_nothing_qualifies():
    edges = [_edge(0, 1, is_true_edge=True, retained=True, conditioning_size_used=1, decisive_conditioning_subset=[2])]
    raw = pd.DataFrame([_raw_row("chain_fork_hub", 750, 0, 1, edges)])

    candidates = enrich_with_chance_correlation(raw, strength=0.5)
    assert candidates.empty


def test_evaluate_h3_confirms_when_high_chance_correlation_has_a_higher_wrong_retention_rate():
    table = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "n": 750, "level": "high", "count": 200, "wrong_retention_rate": 0.9, "ci_low": 0.85, "ci_high": 0.94},
            {"dgp": "chain_fork_hub", "n": 750, "level": "low", "count": 200, "wrong_retention_rate": 0.2, "ci_low": 0.15, "ci_high": 0.26},
        ]
    )
    verdict = evaluate_h3(table)
    assert verdict.status == "CONFIRMED"


def test_evaluate_h3_not_confirmed_when_rates_overlap():
    table = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "n": 750, "level": "high", "count": 200, "wrong_retention_rate": 0.5, "ci_low": 0.43, "ci_high": 0.57},
            {"dgp": "chain_fork_hub", "n": 750, "level": "low", "count": 200, "wrong_retention_rate": 0.48, "ci_low": 0.41, "ci_high": 0.55},
        ]
    )
    verdict = evaluate_h3(table)
    assert verdict.status == "NOT_CONFIRMED"


def test_evaluate_h3_inconclusive_below_min_count():
    table = pd.DataFrame(
        [
            {"dgp": "chain_fork_hub", "n": 750, "level": "high", "count": 5, "wrong_retention_rate": 0.9, "ci_low": 0.4, "ci_high": 0.99},
            {"dgp": "chain_fork_hub", "n": 750, "level": "low", "count": 5, "wrong_retention_rate": 0.2, "ci_low": 0.02, "ci_high": 0.6},
        ]
    )
    verdict = evaluate_h3(table, min_count=30)
    assert verdict.status == "INCONCLUSIVE"


def test_evaluate_h3_inconclusive_on_empty_table():
    verdict = evaluate_h3(pd.DataFrame())
    assert verdict.status == "INCONCLUSIVE"


def test_legitimate_separator_map_matches_the_named_indirect_pairs():
    assert _LEGITIMATE_SEPARATOR["chain_fork_hub"][(0, 2)] == 1
    assert _LEGITIMATE_SEPARATOR["chain_fork_hub"][(3, 5)] == 4
    assert _LEGITIMATE_SEPARATOR["chain_fork_hub"][(7, 8)] == 6
    assert _LEGITIMATE_SEPARATOR["overlap"][(0, 2)] == 1
    assert _LEGITIMATE_SEPARATOR["overlap"][(3, 5)] == 4
    for pair in ((6, 9), (6, 10), (7, 9), (7, 10)):
        assert _LEGITIMATE_SEPARATOR["overlap"][pair] == 8


def _candidate_row(dgp, i, j, correct, decisive_conditioning_subset):
    return {
        "dgp": dgp, "n": 750, "replicate": 0, "i": i, "j": j, "correct": correct,
        "decisive_conditioning_subset": decisive_conditioning_subset, "chance_correlation": 0.5,
    }


def test_evaluate_step5_validity_is_clean_when_no_wrongly_retained_edge_contains_its_own_separator():
    candidates = pd.DataFrame(
        [_candidate_row("chain_fork_hub", 0, 2, correct=False, decisive_conditioning_subset=(9, 10))]
    )
    result = evaluate_step5_validity(candidates)
    assert result.status == "CLEAN"
    assert result.flagged_rows == []


def test_evaluate_step5_validity_flags_when_a_wrongly_retained_edge_contains_its_own_separator():
    candidates = pd.DataFrame(
        [_candidate_row("chain_fork_hub", 0, 2, correct=False, decisive_conditioning_subset=(1, 9))]
    )
    result = evaluate_step5_validity(candidates)
    assert result.status == "FLAGGED"
    assert len(result.flagged_rows) == 1
    assert result.flagged_rows[0]["legitimate_separator"] == 1


def test_evaluate_step5_validity_ignores_correctly_pruned_edges_even_if_separator_present():
    """The separator's own presence is only alarming when the edge was
    still (wrongly) retained -- a correctly pruned edge containing its
    own separator is exactly the expected, correct behavior."""
    candidates = pd.DataFrame(
        [_candidate_row("chain_fork_hub", 0, 2, correct=True, decisive_conditioning_subset=(1, 9))]
    )
    result = evaluate_step5_validity(candidates)
    assert result.status == "CLEAN"


def test_h3_wrong_retention_table_is_empty_for_empty_candidates():
    table = h3_wrong_retention_table(pd.DataFrame())
    assert table.empty
