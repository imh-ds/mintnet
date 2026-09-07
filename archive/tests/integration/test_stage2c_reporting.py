from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2c import Stage2cConfig
from mintnet.experiments.stage2c_reporting import evaluate_stage2c_gate, write_stage2c_report


def _config() -> Stage2cConfig:
    return Stage2cConfig(
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


def _row(n, replicate, indirect_tpr, true_edge_fpr, screening_fer, final_fer) -> dict[str, object]:
    return {
        "n": n,
        "replicate": replicate,
        "seed": 1,
        "dpi_alpha": 0.15,
        "indirect_prune_tpr": indirect_tpr,
        "true_edge_prune_fpr": true_edge_fpr,
        "screening_false_edge_rate": screening_fer,
        "final_false_edge_rate": final_fer,
        "chain_is_triad": 1.0,
        "fork_is_triad": 1.0,
        "hub_is_validated": 1.0,
        "elapsed_seconds": 0.001,
        "status": "ok",
        "error": "",
    }


def _raw_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        # N=750: passes everything.
        rows.append(_row(750, replicate, 1.0, 0.0, 0.001, 0.001))
        # N=1500: final false-edge rate regresses beyond the tolerance.
        rows.append(_row(1500, replicate, 1.0, 0.0, 0.001, 0.05))
    return pd.DataFrame(rows)


def test_gate_passes_when_no_regression_and_thresholds_met():
    decision = evaluate_stage2c_gate(_raw_rows(), _config())
    by_n = {d.n: d for d in decision.by_n}
    assert by_n[750].status == "PROCEED"


def test_gate_fails_on_false_edge_rate_regression_beyond_tolerance():
    decision = evaluate_stage2c_gate(_raw_rows(), _config())
    by_n = {d.n: d for d in decision.by_n}
    assert by_n[1500].status == "REASSESS"
    assert "exceeds screening baseline" in by_n[1500].failures[0]


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    decision = write_stage2c_report(_raw_rows(), _config(), tmp_path)
    assert len(decision.by_n) == 2
    for filename in ("decision.json", "stage2c_report.md", "false_edge_rate_comparison.png"):
        assert (tmp_path / filename).is_file()
