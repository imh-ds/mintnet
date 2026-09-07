import json
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1l import TRUE_EDGES
from mintnet.experiments.stage4n import Stage4nConfig, _pair_label


def _config() -> Stage4nConfig:
    return Stage4nConfig(sample_sizes=(100,), alphas=(0.10,), noise_counts=(0, 5), replicates=20, master_seed=20260830)


def _row(n, alpha, noise_count, replicate, *, retained_by_edge, noise_used_by_edge=None, opposite_used_by_edge=None, clique_intact=True):
    noise_used_by_edge = noise_used_by_edge or {e: False for e in TRUE_EDGES}
    opposite_used_by_edge = opposite_used_by_edge or {e: False for e in TRUE_EDGES}
    row = {"n": n, "alpha": alpha, "noise_count": noise_count, "replicate": replicate, "status": "ok", "error": ""}
    for i, j in TRUE_EDGES:
        label = _pair_label(i, j)
        row[f"sequential_candidate_{label}"] = True
        row[f"sequential_retained_{label}"] = retained_by_edge[(i, j)]
        row[f"sequential_tested_neighbors_{label}"] = "0"
        row[f"sequential_noise_neighbor_used_{label}"] = noise_used_by_edge[(i, j)]
        row[f"sequential_opposite_neighbor_used_{label}"] = opposite_used_by_edge[(i, j)]
        row[f"conservative_candidate_{label}"] = True
        row[f"conservative_retained_{label}"] = retained_by_edge[(i, j)]
        row[f"conservative_component_size_{label}"] = 3
        row[f"conservative_component_is_validated_clique_{label}"] = clique_intact
    return row


def _all_retained(value: bool) -> dict:
    return {e: value for e in TRUE_EDGES}


def test_summarize_cell_pools_across_all_six_edges():
    from mintnet.experiments.stage4n_reporting import summarize_cell

    rows = []
    for r in range(10):
        # first edge wrong in 2/10, all others always correct -> pooled wrong = 2/60
        retained = _all_retained(True)
        edge0 = TRUE_EDGES[0]
        retained[edge0] = r >= 2
        rows.append(_row(100, 0.10, 0, r, retained_by_edge=retained))
    raw = pd.DataFrame(rows)

    summary = summarize_cell(raw, 100, 0.10, 0)

    assert abs(summary.sequential_wrong_prune_rate - (2 / 60)) < 1e-9


def test_q3_implication_rate_only_counts_wrongly_pruned_instances():
    from mintnet.experiments.stage4n_reporting import q3_noise_implication_rate

    edge0, edge1 = TRUE_EDGES[0], TRUE_EDGES[1]
    rows = []
    retained = _all_retained(True)
    retained[edge0] = False
    noise_used = {e: False for e in TRUE_EDGES}
    noise_used[edge0] = True
    rows.append(_row(100, 0.10, 5, 0, retained_by_edge=retained, noise_used_by_edge=noise_used))
    retained2 = _all_retained(True)
    retained2[edge1] = False
    rows.append(_row(100, 0.10, 5, 1, retained_by_edge=retained2))
    for r in range(2, 10):
        rows.append(_row(100, 0.10, 5, r, retained_by_edge=_all_retained(True)))
    raw = pd.DataFrame(rows)

    rate = q3_noise_implication_rate(raw, 100, 0.10, 5)

    assert abs(rate - 0.5) < 1e-9  # 1 of 2 wrongly-pruned edge-instances implicated noise


def test_q4_returns_rate_even_without_noise():
    from mintnet.experiments.stage4n_reporting import q4_opposite_branch_implication_rate

    edge0 = TRUE_EDGES[0]
    retained = _all_retained(True)
    retained[edge0] = False
    opposite_used = {e: False for e in TRUE_EDGES}
    opposite_used[edge0] = True
    rows = [_row(100, 0.10, 0, r, retained_by_edge=retained, opposite_used_by_edge=opposite_used) for r in range(4)]
    raw = pd.DataFrame(rows)

    rate = q4_opposite_branch_implication_rate(raw, 100, 0.10, 0)

    assert abs(rate - 1.0) < 1e-9


def test_report_writes_required_evidence_and_skips_comparison_without_paths(tmp_path: Path) -> None:
    from mintnet.experiments.stage4n_reporting import write_stage4n_report

    config = _config()
    rows = []
    for noise_count in (0, 5):
        for r in range(10):
            retained = _all_retained(r < 8)
            rows.append(_row(100, 0.10, noise_count, r, retained_by_edge=retained))
    raw = pd.DataFrame(rows)

    summaries = write_stage4n_report(raw, config, tmp_path)

    assert len(summaries) == 2  # 1 N x 1 alpha x 2 noise_counts
    for filename in ("summary.json", "stage4n_report.md", "wrong_prune_rate.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4n_report.md").read_text(encoding="utf-8")
    assert "comparison skipped" in report_text


def test_report_includes_three_way_comparison_when_paths_given(tmp_path: Path) -> None:
    from mintnet.experiments.stage4n_reporting import write_stage4n_report

    config = _config()
    rows = []
    for noise_count in (0, 5):
        for r in range(10):
            retained = _all_retained(r < 8)
            rows.append(_row(100, 0.10, noise_count, r, retained_by_edge=retained))
    raw = pd.DataFrame(rows)

    stage4c_summary = [
        {"n": 100, "alpha": 0.10, "noise_count": 0, "sequential_wrong_prune_rate": 0.5, "conservative_wrong_prune_rate": 0.1, "conservative_clique_intact_rate": 0.5},
        {"n": 100, "alpha": 0.10, "noise_count": 5, "sequential_wrong_prune_rate": 0.5, "conservative_wrong_prune_rate": 0.1, "conservative_clique_intact_rate": 0.1},
    ]
    stage4m_summary = [
        {"motif": motif, "n": 100, "alpha": 0.10, "noise_count": nc, "sequential_wrong_prune_rate": 0.4, "conservative_wrong_prune_rate": 0.1, "conservative_clique_intact_rate": 0.2}
        for motif in ("chain", "fork", "hub") for nc in (0, 5)
    ]
    stage4c_path = tmp_path / "stage4c_summary.json"
    stage4m_path = tmp_path / "stage4m_summary.json"
    stage4c_path.write_text(json.dumps(stage4c_summary), encoding="utf-8")
    stage4m_path.write_text(json.dumps(stage4m_summary), encoding="utf-8")

    write_stage4n_report(raw, config, tmp_path, stage4c_path, stage4m_path)

    report_text = (tmp_path / "stage4n_report.md").read_text(encoding="utf-8")
    assert "Three-way comparison (overlap vs. Stage 4c's triangle vs. Stage 4m's chain/fork/hub)" in report_text
    assert "triangle (Stage 4c)" in report_text
    assert "chain (Stage 4m)" in report_text
