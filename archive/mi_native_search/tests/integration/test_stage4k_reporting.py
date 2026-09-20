from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage4k import Stage4kConfig


def _config() -> Stage4kConfig:
    return Stage4kConfig(
        strengths=(0.3, 0.5),
        sample_sizes=(750, 1500),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_conditional_accuracy=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )


def _row(motif, strength, n, alpha, replicate, *, candidate: bool, correct: bool | None, fpr=0.0, status="ok", error=""):
    return {
        "motif": motif, "strength": strength, "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "candidate": candidate, "correctly_pruned": (correct if candidate else np.nan),
        "true_edge_prune_fpr": fpr, "status": status, "error": error,
    }


def test_evaluate_cell_proceeds_with_clean_evidence():
    from mintnet.experiments.stage4k_reporting import evaluate_cell

    rows = [_row("chain", 0.3, 750, 0.10, r, candidate=True, correct=True) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, "chain", 0.3, 750, _config())

    assert decision.status == "PROCEED"
    assert decision.candidacy_rate == 1.0
    assert decision.conditional_accuracy == 1.0


def test_evaluate_cell_reassesses_on_low_accuracy():
    from mintnet.experiments.stage4k_reporting import evaluate_cell

    rows = [_row("fork", 0.3, 750, 0.10, 0, candidate=True, correct=True)]
    rows.append(_row("fork", 0.3, 750, 0.10, 1, candidate=True, correct=True))
    rows.append(_row("fork", 0.3, 750, 0.10, 2, candidate=True, correct=False))
    rows.append(_row("fork", 0.3, 750, 0.10, 3, candidate=True, correct=False))
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, "fork", 0.3, 750, _config())

    assert decision.status == "REASSESS"
    assert any("conditional accuracy" in f for f in decision.failures)


def test_evaluate_stage4k_gate_overall_reassess_if_any_cell_fails():
    from mintnet.experiments.stage4k import MOTIFS
    from mintnet.experiments.stage4k_reporting import evaluate_stage4k_gate

    config = _config()
    rows = []
    for motif in MOTIFS:
        for strength in config.strengths:
            for n in config.sample_sizes:
                correct = not (motif == "hub" and strength == 0.5 and n == 1500)
                for replicate in range(4):
                    rows.append(_row(motif, strength, n, 0.10, replicate, candidate=True, correct=correct))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage4k_gate(raw, config)

    assert decision.overall_status == "REASSESS"
    failing = [c for c in decision.by_cell if c.status != "PROCEED"]
    assert len(failing) == 1
    assert failing[0].motif == "hub"
    assert failing[0].strength == 0.5
    assert failing[0].n == 1500


def test_report_writes_required_evidence_and_per_motif_tables(tmp_path: Path) -> None:
    from mintnet.experiments.stage4k import MOTIFS
    from mintnet.experiments.stage4k_reporting import write_stage4k_report

    config = _config()
    rows = []
    for motif in MOTIFS:
        for strength in config.strengths:
            for n in config.sample_sizes:
                for replicate in range(4):
                    rows.append(_row(motif, strength, n, 0.10, replicate, candidate=True, correct=True))
    raw = pd.DataFrame(rows)

    decision = write_stage4k_report(raw, config, tmp_path)

    assert decision.overall_status == "PROCEED"
    assert len(decision.by_cell) == len(MOTIFS) * len(config.strengths) * len(config.sample_sizes)
    for filename in ("decision.json", "stage4k_report.md", "strength_sweep.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4k_report.md").read_text(encoding="utf-8")
    for motif in MOTIFS:
        assert f"Motif: {motif}" in report_text
