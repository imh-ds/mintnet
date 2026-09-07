from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4p import DGPS, ENGINES, Stage4pConfig


def _config() -> Stage4pConfig:
    return Stage4pConfig(
        sample_sizes=(400, 750),
        strength=0.5,
        screening_alpha=0.001,
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        false_edge_rate_tolerance=0.01,
    )


def _row(dgp, engine, n, alpha, replicate, *, chain_tpr=1.0, fork_tpr=1.0, third_tpr=1.0, true_fpr=0.0, screening_fer=0.0, final_fer=0.0, status="ok", error=""):
    return {
        "dgp": dgp, "engine": engine, "n": n, "alpha": alpha, "replicate": replicate, "seed": 1,
        "chain_indirect_tpr": chain_tpr, "fork_indirect_tpr": fork_tpr, "third_indirect_tpr": third_tpr,
        "true_edge_prune_fpr": true_fpr, "screening_false_edge_rate": screening_fer,
        "final_false_edge_rate": final_fer, "status": status, "error": error,
    }


def test_evaluate_cell_proceeds_with_clean_evidence():
    from mintnet.experiments.stage4p_reporting import evaluate_cell

    rows = [_row("overlap", "sequential", 750, 0.10, r) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, "overlap", "sequential", 750, _config())

    assert decision.status == "PROCEED"
    assert not decision.failures


def test_evaluate_cell_reassesses_on_low_third_shape_tpr():
    from mintnet.experiments.stage4p_reporting import evaluate_cell

    rows = [_row("overlap", "conservative", 750, 0.10, r, third_tpr=0.5) for r in range(4)]
    raw = pd.DataFrame(rows)

    decision = evaluate_cell(raw, "overlap", "conservative", 750, _config())

    assert decision.status == "REASSESS"
    assert any("third-shape indirect TPR" in f for f in decision.failures)


def test_evaluate_stage4p_gate_covers_every_combination():
    from mintnet.experiments.stage4p_reporting import evaluate_stage4p_gate

    config = _config()
    rows = []
    for dgp in DGPS:
        for engine in ENGINES:
            for n in config.sample_sizes:
                for replicate in range(4):
                    rows.append(_row(dgp, engine, n, 0.10, replicate))
    raw = pd.DataFrame(rows)

    decision = evaluate_stage4p_gate(raw, config)

    assert len(decision.by_cell) == len(DGPS) * len(ENGINES) * len(config.sample_sizes)
    assert all(c.status == "PROCEED" for c in decision.by_cell)


def test_report_writes_required_evidence_and_side_by_side_tables(tmp_path: Path) -> None:
    from mintnet.experiments.stage4p_reporting import write_stage4p_report

    config = _config()
    rows = []
    for dgp in DGPS:
        for engine in ENGINES:
            for n in config.sample_sizes:
                for replicate in range(4):
                    rows.append(_row(dgp, engine, n, 0.10, replicate))
    raw = pd.DataFrame(rows)

    decision = write_stage4p_report(raw, config, tmp_path)

    assert len(decision.by_cell) == len(DGPS) * len(ENGINES) * len(config.sample_sizes)
    for filename in ("decision.json", "stage4p_report.md", "tpr_by_n_side_by_side.png"):
        assert (tmp_path / filename).is_file()
    report_text = (tmp_path / "stage4p_report.md").read_text(encoding="utf-8")
    for dgp in DGPS:
        assert f"{dgp}-based p=15 network" in report_text
    assert "conservative status" in report_text and "sequential status" in report_text
