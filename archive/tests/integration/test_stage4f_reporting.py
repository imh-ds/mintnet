from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4f import Stage4fConfig


def _config() -> Stage4fConfig:
    return Stage4fConfig(sample_sizes=(300, 750), alphas=(0.10,), replicates=50, master_seed=20260830)


def _row(n, alpha, replicate, i, j, *, candidate, r_marginal, r_partial=None, correctly_pruned=None):
    return {
        "n": n, "alpha": alpha, "replicate": replicate, "seed": 1, "i": i, "j": j,
        "r_marginal": r_marginal, "candidate": candidate,
        "r_partial": r_partial if r_partial is not None else np.nan,
        "correctly_pruned": correctly_pruned if correctly_pruned is not None else np.nan,
        "status": "ok", "error": "",
    }


def test_summarize_cell_only_uses_candidates():
    from mintnet.experiments.stage4f_reporting import summarize_cell

    rng = np.random.default_rng(0)
    rows = []
    for replicate in range(50):
        rows.append(_row(300, 0.10, replicate, 0, 3, candidate=False, r_marginal=0.05))
        marginal = float(rng.uniform(0.1, 0.3))
        partial = marginal * 0.5 + float(rng.normal(0, 0.05))
        rows.append(
            _row(300, 0.10, replicate, 0, 4, candidate=True, r_marginal=marginal, r_partial=partial,
                 correctly_pruned=abs(partial) < 0.1)
        )
    raw = pd.DataFrame(rows)

    summary = summarize_cell(raw, 300, 0.10)

    assert summary.candidates == 50  # only the candidate rows counted, not the 50 non-candidate rows
    assert summary.q1_correlation is not None
    assert summary.q2_mean_abs_r_partial is not None


def test_summarize_cell_handles_zero_candidates():
    from mintnet.experiments.stage4f_reporting import summarize_cell

    rows = [_row(300, 0.10, r, 0, 3, candidate=False, r_marginal=0.05) for r in range(10)]
    raw = pd.DataFrame(rows)

    summary = summarize_cell(raw, 300, 0.10)

    assert summary.candidates == 0
    assert summary.q1_correlation is None
    assert summary.q2_mean_abs_r_partial is None


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage4f_reporting import write_stage4f_report

    rng = np.random.default_rng(1)
    rows = []
    for n in (300, 750):
        for replicate in range(30):
            for i, j in ((0, 3), (0, 4), (1, 3), (1, 4)):
                marginal = float(rng.uniform(0.1, 0.3))
                partial = float(rng.normal(0, 0.05))
                rows.append(
                    _row(n, 0.10, replicate, i, j, candidate=True, r_marginal=marginal,
                         r_partial=partial, correctly_pruned=abs(partial) < 0.1)
                )
    raw = pd.DataFrame(rows)

    summaries = write_stage4f_report(raw, _config(), tmp_path)

    assert len(summaries) == 2
    for filename in ("summary.json", "stage4f_report.md", "marginal_vs_partial.png"):
        assert (tmp_path / filename).is_file()
