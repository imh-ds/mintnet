from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1g import Stage1gConfig
from mintnet.experiments.stage1g_reporting import select_alpha_pair, write_stage1g_report


def _config() -> Stage1gConfig:
    return Stage1gConfig(
        sample_sizes=(750,),
        strengths=(0.5,),
        triangle_families=("moderate",),
        alphas=(0.01, 0.05, 0.10, 0.15, 0.20),
        replicates=2,
        master_seed=20260829,
        development_replicates=(0, 0),
        validation_replicates=(1, 1),
        minimum_indirect_prune_tpr=0.80,
        maximum_triangle_true_edge_prune_fpr=0.10,
    )


# (chain TPR, fork TPR, triangle FPR) per alpha: 0.01 ineligible, 0.05/0.10
# barely eligible (tiny margin), 0.15/0.20 comfortably eligible (large margin).
_CELL_VALUES = {
    0.01: (0.70, 0.70, 0.50),
    0.05: (0.801, 0.801, 0.099),
    0.10: (0.802, 0.802, 0.098),
    0.15: (0.95, 0.95, 0.02),
    0.20: (0.96, 0.96, 0.01),
}


def _raw_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for replicate in (0, 1):
        for alpha, (chain_tpr, fork_tpr, triangle_fpr) in _CELL_VALUES.items():
            for motif, tpr in (("chain", chain_tpr), ("fork", fork_tpr)):
                rows.append(
                    {
                        "motif": motif,
                        "family": "gaussian",
                        "strength": 0.5,
                        "n": 750,
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
                    "n": 750,
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


def test_margin_robust_selection_prefers_the_more_robust_pair_over_the_first_eligible_one():
    """(0.05, 0.10) is eligible first but barely; (0.15, 0.20) has far more margin."""
    pair = select_alpha_pair(_raw_rows(), _config())

    assert pair == (0.15, 0.20)


def test_report_writes_the_margin_robust_pair(tmp_path: Path) -> None:
    decision = write_stage1g_report(_raw_rows(), _config(), tmp_path)

    assert decision.status == "PROCEED"
    assert decision.selected_alpha_pair == (0.15, 0.20)
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage1g_report.md",
        "calibration_summary.csv",
    ):
        assert (tmp_path / filename).is_file()
