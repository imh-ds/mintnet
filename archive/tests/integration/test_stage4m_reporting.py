from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4m import MOTIFS, Stage4mConfig, _DIRECT_EDGES, _pair_label


def _config() -> Stage4mConfig:
    return Stage4mConfig(
        strength=0.15, sample_sizes=(100,), alphas=(0.10,), noise_counts=(0, 5), replicates=20, master_seed=20260830
    )


def _row(motif, n, alpha, noise_count, replicate, *, retained_by_edge, noise_used_by_edge=None, clique_intact=True):
    edges = _DIRECT_EDGES[motif]
    noise_used_by_edge = noise_used_by_edge or {e: False for e in edges}
    row = {"motif": motif, "n": n, "alpha": alpha, "noise_count": noise_count, "replicate": replicate, "status": "ok", "error": ""}
    for i, j in edges:
        label = _pair_label(i, j)
        row[f"sequential_candidate_{label}"] = True
        row[f"sequential_retained_{label}"] = retained_by_edge[(i, j)]
        noise_used = noise_used_by_edge[(i, j)]
        row[f"sequential_tested_neighbors_{label}"] = "3" if noise_used else "0"
        row[f"sequential_noise_neighbor_used_{label}"] = noise_used
        row[f"conservative_candidate_{label}"] = True
        row[f"conservative_retained_{label}"] = retained_by_edge[(i, j)]
        row[f"conservative_component_size_{label}"] = 3
        row[f"conservative_component_is_validated_clique_{label}"] = clique_intact
    return row


def test_summarize_cell_pools_across_both_direct_edges():
    from mintnet.experiments.stage4m_reporting import summarize_cell

    motif = "chain"
    edges = _DIRECT_EDGES[motif]
    rows = []
    for r in range(10):
        # edge 0 wrong in 2/10, edge 1 wrong in 4/10 -> pooled 6/20 = 0.3
        retained = {edges[0]: r >= 2, edges[1]: r >= 4}
        rows.append(_row(motif, 100, 0.10, 0, r, retained_by_edge=retained))
    raw = pd.DataFrame(rows)

    summary = summarize_cell(raw, motif, 100, 0.10, 0)

    assert abs(summary.sequential_wrong_prune_rate - 0.3) < 1e-9


def test_q3_implication_rate_pools_across_both_edges():
    from mintnet.experiments.stage4m_reporting import q3_noise_implication_rate

    motif = "fork"
    edges = _DIRECT_EDGES[motif]
    rows = []
    # replicate 0: edge0 wrong+noise-implicated, edge1 correct.
    rows.append(_row(motif, 100, 0.10, 5, 0, retained_by_edge={edges[0]: False, edges[1]: True}, noise_used_by_edge={edges[0]: True, edges[1]: False}))
    # replicate 1: edge0 wrong, no noise; edge1 correct.
    rows.append(_row(motif, 100, 0.10, 5, 1, retained_by_edge={edges[0]: False, edges[1]: True}, noise_used_by_edge={edges[0]: False, edges[1]: False}))
    for r in range(2, 10):
        rows.append(_row(motif, 100, 0.10, 5, r, retained_by_edge={edges[0]: True, edges[1]: True}))
    raw = pd.DataFrame(rows)

    rate = q3_noise_implication_rate(raw, motif, 100, 0.10, 5)

    assert abs(rate - 0.5) < 1e-9  # 1 of 2 wrongly-pruned edge-instances implicated noise


def test_q3_returns_none_for_noise_free_condition():
    from mintnet.experiments.stage4m_reporting import q3_noise_implication_rate

    motif = "hub"
    edges = _DIRECT_EDGES[motif]
    rows = [_row(motif, 100, 0.10, 0, r, retained_by_edge={edges[0]: False, edges[1]: False}) for r in range(4)]
    raw = pd.DataFrame(rows)

    assert q3_noise_implication_rate(raw, motif, 100, 0.10, 0) is None


def test_report_writes_required_evidence_for_all_motifs(tmp_path: Path) -> None:
    from mintnet.experiments.stage4m_reporting import write_stage4m_report

    config = _config()
    rows = []
    for motif in MOTIFS:
        edges = _DIRECT_EDGES[motif]
        for noise_count in (0, 5):
            for r in range(10):
                rows.append(_row(motif, 100, 0.10, noise_count, r, retained_by_edge={edges[0]: r < 8, edges[1]: r < 8}))
    raw = pd.DataFrame(rows)

    summaries = write_stage4m_report(raw, config, tmp_path)

    assert len(summaries) == len(MOTIFS) * 2  # 3 motifs x 1 N x 1 alpha x 2 noise_counts
    for filename in ("summary.json", "stage4m_report.md", "wrong_prune_rate_by_motif.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4m_report.md").read_text(encoding="utf-8")
    for motif in MOTIFS:
        assert f"Motif: {motif}" in report_text
    assert "Cross-motif comparison" in report_text
