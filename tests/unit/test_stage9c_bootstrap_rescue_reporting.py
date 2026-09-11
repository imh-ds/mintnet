import pandas as pd

from mintnet.experiments.stage9c_bootstrap_rescue_reporting import calibrate_and_validate, explode_qualifying


def _row(dgp, n, replicate, edges):
    import json

    return {
        "dgp": dgp, "n": n, "alpha": 0.1, "replicate": replicate, "seed": 0,
        "qualifying_json": json.dumps(edges), "n_qualifying": len(edges),
        "dataset_bootstrapped": any(e["bootstrapped"] for e in edges), "elapsed_seconds": 1.0,
        "status": "ok", "error": "",
    }


def _edge(i, j, is_true, retained, size, bootstrapped, pi_final):
    category = ("true_retained" if retained else "true_wrongly_pruned") if is_true else (
        "false_wrongly_retained" if retained else "false_correctly_pruned"
    )
    return {
        "i": i, "j": j, "is_true_edge": is_true, "retained": retained, "category": category,
        "conditioning_size_used": size, "bootstrapped": bootstrapped, "pi_final": pi_final,
    }


def test_explode_qualifying_handles_zero_qualifying_edges_without_error():
    raw = pd.DataFrame([_row("chain_fork_hub", 750, 0, [])])
    exploded = explode_qualifying(raw)
    assert len(exploded) == 0
    assert "bootstrapped" in exploded.columns  # regression: must not be columnless when empty


def test_calibrate_and_validate_proceeds_when_a_pi_min_clears_the_bar_on_both_splits():
    rows = []
    for replicate in range(40):
        # True edges: high pi_final (correctly identified as real) at every replicate.
        # False-wrongly-retained edges: low pi_final (correctly flagged as unstable).
        edges = [
            _edge(0, 1, True, True, 2, True, 0.95),
            _edge(0, 2, False, True, 2, True, 0.10),
        ]
        rows.append(_row("overlap", 750, replicate, edges))
    raw = pd.DataFrame(rows)
    exploded = explode_qualifying(raw)

    decision = calibrate_and_validate(exploded, min_recall=0.95, min_removal_rate=0.85, min_count=10)

    assert decision.status == "PROCEED"
    assert decision.selected_pi_min is not None


def test_calibrate_and_validate_reassesses_when_no_pi_min_clears_the_bar():
    rows = []
    for replicate in range(40):
        # pi_final is uninformative -- true and false edges look identical.
        edges = [
            _edge(0, 1, True, True, 2, True, 0.5),
            _edge(0, 2, False, True, 2, True, 0.5),
        ]
        rows.append(_row("overlap", 750, replicate, edges))
    raw = pd.DataFrame(rows)
    exploded = explode_qualifying(raw)

    decision = calibrate_and_validate(exploded, min_recall=0.95, min_removal_rate=0.85, min_count=10)

    assert decision.status == "REASSESS"


def test_calibrate_and_validate_reassesses_below_min_count():
    rows = [_row("overlap", 750, 0, [_edge(0, 1, True, True, 2, True, 0.95)])]
    raw = pd.DataFrame(rows)
    exploded = explode_qualifying(raw)

    decision = calibrate_and_validate(exploded, min_count=10)

    assert decision.status == "REASSESS"
