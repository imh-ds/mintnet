from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4q_a import Stage4qAConfig


def _config() -> Stage4qAConfig:
    return Stage4qAConfig(
        sample_sizes=(1750, 2000),
        strength=0.5,
        screening_alpha=0.001,
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        false_edge_rate_tolerance=0.01,
        required_margin=0.032,
    )


def _row(n, alpha, replicate, *, overlap_tpr=1.0, chain_tpr=1.0, fork_tpr=1.0, true_fpr=0.0, screening_fer=0.0, final_fer=0.0, status="ok", error=""):
    return {
        "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "chain_indirect_tpr": chain_tpr, "fork_indirect_tpr": fork_tpr, "overlap_indirect_tpr": overlap_tpr,
        "true_edge_prune_fpr": true_fpr, "screening_false_edge_rate": screening_fer,
        "final_false_edge_rate": final_fer, "status": status, "error": error,
    }


def test_evaluate_n_flags_comfortable_margin():
    from mintnet.experiments.stage4q_a_reporting import evaluate_n

    rows = [_row(1750, 0.10, r, overlap_tpr=0.90) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 1750, _config())

    assert decision.status == "PROCEED"
    assert abs(decision.margin - 0.10) < 1e-9
    assert decision.comfortable is True


def test_evaluate_n_flags_thin_margin_as_not_comfortable():
    from mintnet.experiments.stage4q_a_reporting import evaluate_n

    rows = [_row(1750, 0.10, r, overlap_tpr=0.81) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_n(raw, 1750, _config())

    assert decision.status == "PROCEED"  # clears the .80 gate
    assert decision.comfortable is False  # but not the .032 comfort margin


def test_report_writes_required_evidence_and_states_verdict(tmp_path: Path) -> None:
    from mintnet.experiments.stage4q_a_reporting import write_stage4q_a_report

    config = _config()
    rows = []
    for n in config.sample_sizes:
        for replicate in range(4):
            rows.append(_row(n, 0.10, replicate, overlap_tpr=0.90))
    raw = pd.DataFrame(rows)

    decision = write_stage4q_a_report(raw, config, tmp_path)

    assert len(decision.by_n) == 2
    for filename in ("decision.json", "stage4q_a_report.md", "margin_by_n.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4q_a_report.md").read_text(encoding="utf-8")
    assert "Verdict" in report_text
