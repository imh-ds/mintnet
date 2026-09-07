from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4h import Stage4hConfig


def _config(source_path: Path | None = None) -> Stage4hConfig:
    return Stage4hConfig(
        sample_sizes=(625, 750),
        strength=0.5,
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        false_edge_rate_tolerance=0.01,
        source_path=source_path,
    )


def _row(n, alpha, replicate, *, chain_tpr=1.0, fork_tpr=1.0, overlap_tpr=1.0, true_fpr=0.0,
         screening_fer=0.0, final_fer=0.0, pair_candidates=None, pair_correct=None, pair_neighbors=None):
    pair_candidates = pair_candidates or {"6_9": True, "6_10": True, "7_9": True, "7_10": True}
    pair_correct = pair_correct or {label: True for label in pair_candidates}
    pair_neighbors = pair_neighbors or {label: "8" for label in pair_candidates}
    row = {
        "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "chain_indirect_tpr": chain_tpr, "fork_indirect_tpr": fork_tpr, "overlap_indirect_tpr": overlap_tpr,
        "true_edge_prune_fpr": true_fpr, "screening_false_edge_rate": screening_fer,
        "final_false_edge_rate": final_fer, "status": "ok", "error": "",
    }
    for label, is_candidate in pair_candidates.items():
        row[f"candidate_{label}"] = is_candidate
        row[f"correctly_pruned_{label}"] = pair_correct[label] if is_candidate else np.nan
        row[f"tested_neighbors_{label}"] = pair_neighbors[label] if is_candidate else ""
    return row


def test_evaluate_n_proceeds_with_clean_evidence():
    from mintnet.experiments.stage4h_reporting import evaluate_n

    rows = [_row(750, 0.05, r) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 750, _config())

    assert decision.status == "PROCEED"
    assert decision.overlap_candidacy_rate == 1.0
    assert decision.overlap_conditional_accuracy == 1.0
    assert not decision.failures


def test_contamination_rate_flags_non_shared_neighbor():
    from mintnet.experiments.stage4h_reporting import evaluate_n

    rows = []
    for r in range(4):
        rows.append(
            _row(
                750, 0.05, r,
                overlap_tpr=0.0,  # all 4 wrongly retained
                pair_correct={"6_9": False, "6_10": False, "7_9": False, "7_10": False},
                pair_neighbors={"6_9": "1", "6_10": "8", "7_9": "1,2", "7_10": "8"},  # 2 non-shared, 2 shared
            )
        )
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 750, _config())

    assert decision.overlap_contamination_rate == 0.5


def test_evaluate_n_reassesses_on_low_overlap_tpr():
    from mintnet.experiments.stage4h_reporting import evaluate_n

    rows = [_row(750, 0.05, r, overlap_tpr=0.5) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 750, _config())

    assert decision.status == "REASSESS"
    assert any("overlap indirect TPR" in f for f in decision.failures)


def test_report_writes_required_evidence_and_skips_missing_baseline(tmp_path: Path) -> None:
    from mintnet.experiments.stage4h_reporting import write_stage4h_report

    config = _config(source_path=(tmp_path / "configs" / "stage4h_composed_noise.yaml"))
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "stage4h_composed_noise.yaml").write_text("placeholder\n", encoding="utf-8")

    rows = []
    for n in (625, 750):
        for r in range(4):
            rows.append(_row(n, 0.05, r))
    raw = pd.DataFrame(rows)

    decision = write_stage4h_report(raw, config, tmp_path / "evidence")

    assert len(decision.by_n) == 2
    for filename in ("decision.json", "stage4h_report.md", "overlap_tpr_by_n.png"):
        assert (tmp_path / "evidence" / filename).is_file()
