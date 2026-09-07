from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4b import Stage4bConfig


def _config(source_path: Path | None = None) -> Stage4bConfig:
    return Stage4bConfig(
        sample_sizes=(750, 1500),
        hub_strength=0.5,
        alphas=(0.05, 0.10, 0.20),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
        source_path=source_path,
    )


def _row(shape, n, alpha, replicate, *, tpr, fpr):
    return {
        "shape": shape,
        "n": n,
        "alpha": alpha,
        "replicate": replicate,
        "seed": 1,
        "indirect_prune_tpr": tpr,
        "true_edge_prune_fpr": fpr,
        "conditionally_tested_pairs": 1,
        "confirmed_pairs": 2,
        "status": "ok",
        "error": "",
    }


def test_select_alpha_picks_largest_eligible_not_smallest():
    from mintnet.experiments.stage4b_reporting import select_alpha

    rows = []
    for replicate in range(2):  # development replicates 0-1
        rows.append(_row("hub", 750, 0.05, replicate, tpr=0.95, fpr=0.0))
        rows.append(_row("hub", 750, 0.10, replicate, tpr=0.90, fpr=0.0))
        rows.append(_row("hub", 750, 0.20, replicate, tpr=0.60, fpr=0.30))  # ineligible: fails both
    raw = pd.DataFrame(rows)

    selected = select_alpha(raw, "hub", 750, _config())

    assert selected == 0.10  # largest of the two eligible alphas (0.05, 0.10)


def test_evaluate_cell_proceeds_when_validation_clears_margin():
    from mintnet.experiments.stage4b_reporting import evaluate_cell

    rows = []
    for replicate in range(4):
        rows.append(_row("overlap", 1500, 0.10, replicate, tpr=0.95, fpr=0.0))
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, "overlap", 1500, _config())

    assert decision.status == "PROCEED"
    assert decision.selected_alpha == 0.10
    assert not decision.failures


def test_evaluate_cell_reassesses_when_no_alpha_is_eligible():
    from mintnet.experiments.stage4b_reporting import evaluate_cell

    rows = [_row("hub", 750, 0.05, r, tpr=0.5, fpr=0.4) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, "hub", 750, _config())

    assert decision.status == "REASSESS"
    assert decision.selected_alpha is None
    assert "no eligible development alpha" in decision.failures


def test_report_writes_required_evidence_and_skips_missing_baselines(tmp_path: Path) -> None:
    from mintnet.experiments.stage4b_reporting import write_stage4b_report

    (tmp_path / "configs").mkdir()
    config_path = tmp_path / "configs" / "stage4b_hub_overlap.yaml"
    config_path.write_text("placeholder\n", encoding="utf-8")
    config = _config(source_path=config_path)

    rows = []
    for shape in ("hub", "overlap"):
        for n in (750, 1500):
            for replicate in range(4):
                rows.append(_row(shape, n, 0.10, replicate, tpr=0.95, fpr=0.0))
    raw = pd.DataFrame(rows)

    decision = write_stage4b_report(raw, config, tmp_path / "evidence")

    assert len(decision.by_cell) == 4
    for filename in (
        "decision.json", "stage4b_report.md", "conservative_comparison.csv", "indirect_tpr_by_shape.png",
    ):
        assert (tmp_path / "evidence" / filename).is_file()
    comparison = pd.read_csv(tmp_path / "evidence" / "conservative_comparison.csv")
    # No results/generated/... baselines exist under this isolated repository root.
    assert comparison["baseline_hand_fed_tpr"].isna().all()
