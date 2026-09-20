import pandas as pd

from mintnet.experiments.stage7f_frontier import Stage7fConfig
from mintnet.experiments.stage7f_frontier_reporting import (
    frontier_table,
    smallest_resolvable_target_rho,
    verify_confidence_score,
)


def _config(**overrides) -> Stage7fConfig:
    values = dict(
        sample_sizes=(400, 750),
        strengths=(0.3, 0.5, 0.7),
        target_rhos=(0.08, 0.20),
        degree=1, ridge_lambda=1.0, cv_folds=5, k_perm=3, permutations=199,
        replicates=10, batch_size=10, master_seed=1,
    )
    values.update(overrides)
    return Stage7fConfig(**values)


def _row(condition: str, motif: str, index: int, n: int, replicate: int, p01: float, p02: float, p12: float) -> dict:
    return {
        "condition": condition, "motif": motif, "index": index, "n": n, "replicate": replicate, "seed": 0,
        "decisive_p_value_01": p01, "decisive_p_value_02": p02, "decisive_p_value_12": p12,
        "n_significance_tests": 3, "elapsed_seconds": 0.1, "status": "ok", "error": "",
    }


def test_frontier_table_marks_a_cell_feasible_when_a_shared_alpha_satisfies_both_requirements():
    """Chain/fork's own indirect pair (0,2) is cleanly null (p always
    large); the triangle's own weak edge (1,2) is easily resolved (p
    always small) -- a wide range of alpha should work at every N."""
    rows = []
    for n in (400, 750):
        for replicate in range(5):
            for i in range(3):
                rows.append(_row(f"chain_{i}", "chain", i, n, replicate, p01=0.001, p02=0.90, p12=0.001))
                rows.append(_row(f"fork_{i}", "fork", i, n, replicate, p01=0.001, p02=0.90, p12=0.001))
            rows.append(_row("triangle_0", "triangle", 0, n, replicate, p01=0.001, p02=0.001, p12=0.001))
            rows.append(_row("triangle_1", "triangle", 1, n, replicate, p01=0.001, p02=0.001, p12=0.90))
    raw = pd.DataFrame(rows)
    config = _config()

    table = frontier_table(raw, config)

    easy = table.loc[(table["n"] == 400) & (table["target_rho"] == 0.08)]
    assert bool(easy["feasible"].iloc[0])

    hard = table.loc[(table["n"] == 400) & (table["target_rho"] == 0.20)]
    assert not bool(hard["feasible"].iloc[0])


def test_smallest_resolvable_target_rho_reports_nan_when_nothing_resolves():
    table = pd.DataFrame(
        [
            {"n": 400, "target_rho": 0.08, "feasible": False, "window_low": float("nan"), "window_high": float("nan"), "n_feasible_alphas": 0},
            {"n": 400, "target_rho": 0.20, "feasible": True, "window_low": 0.1, "window_high": 0.2, "n_feasible_alphas": 5},
            {"n": 750, "target_rho": 0.08, "feasible": False, "window_low": float("nan"), "window_high": float("nan"), "n_feasible_alphas": 0},
            {"n": 750, "target_rho": 0.20, "feasible": False, "window_low": float("nan"), "window_high": float("nan"), "n_feasible_alphas": 0},
        ]
    )
    result = smallest_resolvable_target_rho(table)

    assert result.loc[result["n"] == 400, "smallest_resolvable_target_rho"].iloc[0] == 0.20
    assert pd.isna(result.loc[result["n"] == 750, "smallest_resolvable_target_rho"].iloc[0])


def test_verify_confidence_score_proceeds_when_confidence_tracks_correctness_and_grows_with_n():
    """Construct decisions where confidence is high exactly when the
    decision is correct, and the frontier edge's own p-value gets
    closer to zero (higher confidence) as N grows -- both checks should
    PROCEED."""
    rows = []
    for n, frontier_p in ((400, 0.09), (750, 0.03)):
        for replicate in range(20):
            for i in range(3):
                # Clean, easy null (correctly pruned at alpha=0.10) and clean, easy true edges.
                rows.append(_row(f"chain_{i}", "chain", i, n, replicate, p01=0.001, p02=0.95, p12=0.001))
                rows.append(_row(f"fork_{i}", "fork", i, n, replicate, p01=0.001, p02=0.95, p12=0.001))
            rows.append(_row("triangle_0", "triangle", 0, n, replicate, p01=0.001, p02=0.001, p12=frontier_p))
            rows.append(_row("triangle_1", "triangle", 1, n, replicate, p01=0.001, p02=0.001, p12=0.001))
    raw = pd.DataFrame(rows)
    config = _config()

    verification = verify_confidence_score(raw, config)

    assert verification.informative_at_every_n
    assert verification.monotonic_with_n
    assert verification.status == "PROCEED"


def test_verify_confidence_score_reassesses_when_frontier_confidence_shrinks_with_n():
    rows = []
    for n, frontier_p in ((400, 0.03), (750, 0.09)):  # reversed: gets WORSE with more data
        for replicate in range(20):
            for i in range(3):
                rows.append(_row(f"chain_{i}", "chain", i, n, replicate, p01=0.001, p02=0.95, p12=0.001))
                rows.append(_row(f"fork_{i}", "fork", i, n, replicate, p01=0.001, p02=0.95, p12=0.001))
            rows.append(_row("triangle_0", "triangle", 0, n, replicate, p01=0.001, p02=0.001, p12=frontier_p))
            rows.append(_row("triangle_1", "triangle", 1, n, replicate, p01=0.001, p02=0.001, p12=0.001))
    raw = pd.DataFrame(rows)
    config = _config()

    verification = verify_confidence_score(raw, config)

    assert not verification.monotonic_with_n
    assert verification.status == "REASSESS"
