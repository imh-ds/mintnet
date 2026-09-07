from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1f import Stage1fConfig
from mintnet.experiments.stage1f_reporting import select_alpha_pair, write_stage1f_report


def _config() -> Stage1fConfig:
    return Stage1fConfig(
        sample_sizes=(500, 750, 1000),
        strengths=(0.3, 0.5, 0.7),
        triangle_families=("balanced", "moderate", "strong"),
        alphas=(0.001, 0.05, 0.10, 0.20),
        replicates=4,
        master_seed=20260829,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.8,
        maximum_triangle_true_edge_prune_fpr=0.1,
    )


def _raw_rows() -> pd.DataFrame:
    """A single bad cell at alpha=.05 pools under .10 on average but fails individually."""
    rows: list[dict[str, object]] = []
    families = {0.3: "balanced", 0.5: "moderate", 0.7: "strong"}
    for replicate in range(4):
        for n in (500, 750, 1000):
            for alpha in (0.001, 0.05, 0.10, 0.20):
                for strength in (0.3, 0.5, 0.7):
                    for motif in ("chain", "fork", "triangle"):
                        indirect_tpr = 1.0 if motif != "triangle" else float("nan")
                        true_edge_fpr = 0.0
                        if alpha == 0.001:
                            indirect_tpr = 0.0 if motif != "triangle" else float("nan")
                            true_edge_fpr = 1.0
                        if (
                            alpha == 0.05
                            and motif == "triangle"
                            and n == 750
                            and strength == 0.7
                        ):
                            true_edge_fpr = 0.5
                        rows.append(
                            {
                                "motif": motif,
                                "family": families[strength] if motif == "triangle" else "gaussian",
                                "strength": strength,
                                "n": n,
                                "alpha": alpha,
                                "replicate": replicate,
                                "seed": 1,
                                "retained_01": True,
                                "retained_02": motif == "triangle",
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
                                "indirect_prune_tpr": indirect_tpr,
                                "true_edge_prune_fpr": true_edge_fpr,
                                "perfect_recovery": 1.0 if alpha != 0.001 else 0.0,
                                "elapsed_seconds": 0.001,
                                "status": "ok",
                                "error": "",
                            }
                        )
    return pd.DataFrame(rows)


def test_per_cell_selection_skips_a_pair_that_only_passes_pooled():
    """A single bad cell must disqualify alpha=.05 even though its pooled average is fine."""
    pair = select_alpha_pair(_raw_rows(), _config())

    assert pair == (0.10, 0.20)


def test_report_writes_passing_decision_and_required_evidence(tmp_path: Path) -> None:
    decision = write_stage1f_report(_raw_rows(), _config(), tmp_path)

    assert decision.status == "PROCEED"
    assert decision.selected_alpha_pair == (0.10, 0.20)
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage1f_report.md",
        "dpi_operating_curve.png",
        "performance_vs_alpha.png",
        "runtime_vs_n.png",
        "calibration_summary.csv",
    ):
        assert (tmp_path / filename).is_file()
