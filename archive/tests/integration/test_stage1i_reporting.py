from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1i import Stage1iConfig
from mintnet.experiments.stage1i_reporting import evaluate_stage1i_gate, write_stage1i_report


def _config() -> Stage1iConfig:
    return Stage1iConfig(
        sample_sizes=(100, 750),
        strengths=(0.5,),
        triangle_families=("moderate",),
        alphas=(0.05, 0.10, 0.40, 0.45),
        replicates=2,
        master_seed=20260829,
        development_replicates=(0, 0),
        validation_replicates=(1, 1),
        minimum_indirect_prune_tpr=0.80,
        maximum_triangle_true_edge_prune_fpr=0.10,
    )


# N=100: no alpha jointly satisfies both criteria (a real, wide gap).
# N=750: (0.40, 0.45) both comfortably satisfy both criteria.
_CELL_VALUES = {
    100: {
        0.05: (0.95, 0.95, 0.50),
        0.10: (0.90, 0.90, 0.40),
        0.40: (0.60, 0.60, 0.09),
        0.45: (0.55, 0.55, 0.08),
    },
    750: {
        0.05: (0.99, 0.99, 0.15),
        0.10: (0.97, 0.97, 0.12),
        0.40: (0.90, 0.90, 0.05),
        0.45: (0.88, 0.88, 0.04),
    },
}


def _raw_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for replicate in (0, 1):
        for n, by_alpha in _CELL_VALUES.items():
            for alpha, (chain_tpr, fork_tpr, triangle_fpr) in by_alpha.items():
                for motif, tpr in (("chain", chain_tpr), ("fork", fork_tpr)):
                    rows.append(
                        {
                            "motif": motif,
                            "family": "gaussian",
                            "strength": 0.5,
                            "n": n,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": 1,
                            "retained_01": True,
                            "retained_02": False,
                            "retained_12": True,
                            "partial_r_01": 0.5,
                            "partial_r_02": 0.0,
                            "partial_r_12": 0.5,
                            "p_value_01": 0.001,
                            "p_value_02": 0.9,
                            "p_value_12": 0.001,
                            "confidence_01": 0.999,
                            "confidence_02": 0.1,
                            "confidence_12": 0.999,
                            "indirect_prune_tpr": tpr,
                            "true_edge_prune_fpr": float("nan"),
                            "perfect_recovery": 1.0,
                            "elapsed_seconds": 0.001,
                            "status": "ok",
                            "error": "",
                        }
                    )
                rows.append(
                    {
                        "motif": "triangle",
                        "family": "moderate",
                        "strength": 0.5,
                        "n": n,
                        "alpha": alpha,
                        "replicate": replicate,
                        "seed": 1,
                        "retained_01": True,
                        "retained_02": True,
                        "retained_12": True,
                        "partial_r_01": 0.5,
                        "partial_r_02": 0.3,
                        "partial_r_12": 0.5,
                        "p_value_01": 0.001,
                        "p_value_02": 0.05,
                        "p_value_12": 0.001,
                        "confidence_01": 0.999,
                        "confidence_02": 0.95,
                        "confidence_12": 0.999,
                        "indirect_prune_tpr": float("nan"),
                        "true_edge_prune_fpr": triangle_fpr,
                        "perfect_recovery": 1.0 if triangle_fpr == 0.0 else 0.0,
                        "elapsed_seconds": 0.001,
                        "status": "ok",
                        "error": "",
                    }
                )
    return pd.DataFrame(rows)


def test_each_n_is_selected_and_gated_independently():
    """N=100 must REASSESS (no viable alpha) while N=750 PROCEEDs, in one run."""
    decision = evaluate_stage1i_gate(_raw_rows(), _config())

    by_n = {d.n: d for d in decision.by_n}
    assert by_n[100].status == "REASSESS"
    assert by_n[100].selected_alpha_pair is None
    assert by_n[750].status == "PROCEED"
    assert by_n[750].selected_alpha_pair == (0.40, 0.45)


def test_report_writes_a_per_n_table(tmp_path: Path) -> None:
    decision = write_stage1i_report(_raw_rows(), _config(), tmp_path)

    assert len(decision.by_n) == 2
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage1i_report.md",
        "dpi_operating_curve.png",
        "performance_vs_alpha.png",
        "margin_vs_n.png",
        "calibration_summary.csv",
    ):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage1i_report.md").read_text(encoding="utf-8")
    assert "REASSESS" in report_text
    assert "PROCEED" in report_text
