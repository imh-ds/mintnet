from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1b import Stage1bConfig


def _config(source_path: Path | None = None) -> Stage1bConfig:
    return Stage1bConfig(
        sample_sizes=(500, 750, 1000),
        strengths=(0.5,),
        triangle_families=("moderate",),
        alphas=(0.001, 0.05, 0.50),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.8,
        maximum_triangle_true_edge_prune_fpr=0.1,
        source_path=source_path,
    )


def _raw_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        for n in (500, 750, 1000):
            for alpha in (0.001, 0.05, 0.50):
                for motif in ("chain", "fork", "triangle"):
                    indirect_tpr = 1.0 if motif != "triangle" else float("nan")
                    true_edge_fpr = 0.0
                    rows.append(
                        {
                            "motif": motif,
                            "family": "moderate" if motif == "triangle" else "gaussian",
                            "strength": 0.5,
                            "n": n,
                            "alpha": alpha,
                            "replicate": replicate,
                            "seed": 1,
                            "retained_01": True,
                            "retained_02": motif == "triangle",
                            "retained_12": True,
                            "indirect_prune_tpr": indirect_tpr,
                            "true_edge_prune_fpr": true_edge_fpr,
                            "perfect_recovery": 1.0,
                            "elapsed_seconds": 0.0001,
                            "status": "ok",
                            "error": "",
                        }
                    )
    return pd.DataFrame(rows)


def test_report_writes_required_evidence_and_skips_missing_baseline(tmp_path: Path) -> None:
    from mintnet.experiments.stage4a_reporting import write_stage4a_report

    # No results/generated/stage1b_dpi under this isolated repository root, so
    # the cross-engine comparison must degrade gracefully rather than error.
    config = _config(source_path=(tmp_path / "configs" / "stage4a_sequential.yaml"))
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "stage4a_sequential.yaml").write_text("placeholder\n", encoding="utf-8")

    decision = write_stage4a_report(_raw_rows(), config, tmp_path / "evidence")

    assert decision.status == "PROCEED"
    for filename in (
        "aggregate_metrics.csv", "decision.json", "stage4a_report.md",
        "stage1b_comparison.csv", "dpi_operating_curve.png",
    ):
        assert (tmp_path / "evidence" / filename).is_file()
    comparison = pd.read_csv(tmp_path / "evidence" / "stage1b_comparison.csv")
    assert comparison.empty


def test_report_compares_against_stage1b_baseline_when_present(tmp_path: Path) -> None:
    from mintnet.experiments.stage4a_reporting import write_stage4a_report

    repository_root = tmp_path
    (repository_root / "configs").mkdir()
    config_path = repository_root / "configs" / "stage4a_sequential.yaml"
    config_path.write_text("placeholder\n", encoding="utf-8")
    baseline_dir = repository_root / "results" / "generated" / "stage1b_dpi"
    baseline_dir.mkdir(parents=True)
    baseline = pd.DataFrame(
        [
            {
                "motif": "chain", "n": 500, "strength": 0.5, "alpha": 0.05,
                "indirect_prune_tpr": 0.9, "true_edge_prune_fpr": 0.0,
            }
        ]
    )
    baseline.to_csv(baseline_dir / "aggregate_metrics.csv", index=False)

    config = _config(source_path=config_path)
    write_stage4a_report(_raw_rows(), config, repository_root / "evidence")

    comparison = pd.read_csv(repository_root / "evidence" / "stage1b_comparison.csv")
    assert not comparison.empty
    row = comparison.loc[(comparison["motif"] == "chain") & (comparison["n"] == 500) & (comparison["alpha"] == 0.05)]
    assert len(row) == 1
    assert row["indirect_prune_tpr_stage1b"].iloc[0] == 0.9
