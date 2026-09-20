from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2d import Stage2dConfig
from mintnet.experiments.stage2d_reporting import evaluate_stage2d_gate, write_stage2d_report


def _config() -> Stage2dConfig:
    return Stage2dConfig(
        sample_sizes=(750, 1500),
        strength=0.5,
        screening_alpha=0.001,
        replicates=4,
        master_seed=20260829,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _row(n, replicate, chain_tpr, fork_tpr, overlap_tpr, fpr, screening_fer, final_fer, clean) -> dict[str, object]:
    return {
        "n": n,
        "replicate": replicate,
        "seed": 1,
        "dpi_alpha": 0.15,
        "chain_indirect_tpr": chain_tpr,
        "fork_indirect_tpr": fork_tpr,
        "overlap_indirect_tpr": overlap_tpr,
        "true_edge_prune_fpr": fpr,
        "screening_false_edge_rate": screening_fer,
        "final_false_edge_rate": final_fer,
        "chain_is_triad": 1.0,
        "fork_is_triad": 1.0,
        "overlap_is_validated": clean,
        "overlap_clean_clique": clean,
        "elapsed_seconds": 0.001,
        "status": "ok",
        "error": "",
    }


def _raw_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        # N=750: chain/fork pass comfortably, but overlap TPR fails -- a pooled
        # average across all three would still pass (mean = (.95+.95+.60)/3=.833),
        # which is exactly the D-004 pooling blind spot this design avoids.
        rows.append(_row(750, replicate, 0.95, 0.95, 0.60, 0.0, 0.001, 0.001, 0.3))
        # N=1500: everything passes.
        rows.append(_row(1500, replicate, 0.95, 0.95, 0.85, 0.0, 0.001, 0.001, 0.9))
    return pd.DataFrame(rows)


def test_per_motif_gate_catches_an_overlap_specific_failure_pooling_would_hide():
    decision = evaluate_stage2d_gate(_raw_rows(), _config())
    by_n = {d.n: d for d in decision.by_n}

    assert by_n[750].status == "REASSESS"
    assert any("overlap indirect TPR" in f for f in by_n[750].failures)
    assert not any("chain" in f or "fork" in f for f in by_n[750].failures)


def test_gate_passes_when_all_three_motifs_individually_clear_the_bar():
    decision = evaluate_stage2d_gate(_raw_rows(), _config())
    by_n = {d.n: d for d in decision.by_n}
    assert by_n[1500].status == "PROCEED"


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    decision = write_stage2d_report(_raw_rows(), _config(), tmp_path)
    assert len(decision.by_n) == 2
    for filename in ("decision.json", "stage2d_report.md", "overlap_clean_clique_vs_tpr.png"):
        assert (tmp_path / filename).is_file()
