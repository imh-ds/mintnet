from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4c import Stage4cConfig


def _config() -> Stage4cConfig:
    return Stage4cConfig(sample_sizes=(100,), alphas=(0.10,), noise_counts=(0, 5), replicates=20, master_seed=20260830)


def _row(n, alpha, noise_count, replicate, *, seq_retained, cons_retained, noise_used=False, clique_intact=True):
    return {
        "n": n, "alpha": alpha, "noise_count": noise_count, "replicate": replicate,
        "sequential_candidate": True, "sequential_retained": seq_retained,
        "sequential_tested_neighbors": "3" if noise_used else "0",
        "sequential_noise_neighbor_used": noise_used,
        "conservative_candidate": True, "conservative_retained": cons_retained,
        "conservative_component_size": 3, "conservative_component_is_validated_clique": clique_intact,
        "status": "ok", "error": "",
    }


def test_summarize_cell_computes_wrong_prune_rates():
    from mintnet.experiments.stage4c_reporting import summarize_cell

    rows = []
    for r in range(10):
        rows.append(_row(100, 0.10, 0, r, seq_retained=(r < 8), cons_retained=(r < 9)))
    raw = pd.DataFrame(rows)

    summary = summarize_cell(raw, 100, 0.10, 0)

    assert abs(summary.sequential_wrong_prune_rate - 0.2) < 1e-9
    assert abs(summary.conservative_wrong_prune_rate - 0.1) < 1e-9


def test_q3_implication_rate_only_counts_wrongly_pruned_replicates():
    from mintnet.experiments.stage4c_reporting import q3_noise_implication_rate

    rows = []
    # 2 wrongly-pruned replicates: one noise-implicated, one not. 8 correct.
    rows.append(_row(100, 0.10, 5, 0, seq_retained=False, cons_retained=True, noise_used=True))
    rows.append(_row(100, 0.10, 5, 1, seq_retained=False, cons_retained=True, noise_used=False))
    for r in range(2, 10):
        rows.append(_row(100, 0.10, 5, r, seq_retained=True, cons_retained=True))
    raw = pd.DataFrame(rows)

    rate = q3_noise_implication_rate(raw, 100, 0.10, 5)

    assert abs(rate - 0.5) < 1e-9  # 1 of 2 wrongly-pruned replicates implicated noise


def test_q3_returns_none_for_noise_free_condition():
    from mintnet.experiments.stage4c_reporting import q3_noise_implication_rate

    rows = [_row(100, 0.10, 0, r, seq_retained=False, cons_retained=True) for r in range(4)]
    raw = pd.DataFrame(rows)

    assert q3_noise_implication_rate(raw, 100, 0.10, 0) is None


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage4c_reporting import write_stage4c_report

    rows = []
    for noise_count in (0, 5):
        for r in range(10):
            rows.append(_row(100, 0.10, noise_count, r, seq_retained=(r < 8), cons_retained=(r < 9)))
    raw = pd.DataFrame(rows)

    summaries = write_stage4c_report(raw, _config(), tmp_path)

    assert len(summaries) == 2  # 1 N x 1 alpha x 2 noise_counts
    for filename in ("summary.json", "stage4c_report.md", "wrong_prune_rate_by_engine.png"):
        assert (tmp_path / filename).is_file()
