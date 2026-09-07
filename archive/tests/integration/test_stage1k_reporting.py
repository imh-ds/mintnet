from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1k import Stage1kConfig
from mintnet.experiments.stage1k_reporting import evaluate_stage1k_gate, write_stage1k_report


def _config() -> Stage1kConfig:
    return Stage1kConfig(
        sample_sizes=(750, 1500),
        strength=0.5,
        replicates=4,
        master_seed=20260829,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
    )


def _row(n, replicate, tpr, fpr) -> dict[str, object]:
    return {
        "n": n,
        "replicate": replicate,
        "seed": 1,
        "alpha": 0.15,
        "indirect_prune_tpr": tpr,
        "true_edge_prune_fpr": fpr,
        "elapsed_seconds": 0.001,
        "status": "ok",
        "error": "",
    }


def _raw_rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        rows.append(_row(750, replicate, 0.90, 0.02))  # comfortable pass
        rows.append(_row(1500, replicate, 0.81, 0.02))  # margin below required 0.02
    return pd.DataFrame(rows)


def test_gate_requires_margin_at_least_the_configured_threshold():
    decision = evaluate_stage1k_gate(_raw_rows(), _config())
    by_n = {d.n: d for d in decision.by_n}

    assert by_n[750].status == "PROCEED"
    assert by_n[1500].status == "REASSESS"
    assert "margin" in by_n[1500].failures[-1]


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    decision = write_stage1k_report(_raw_rows(), _config(), tmp_path)
    assert len(decision.by_n) == 2
    for filename in ("decision.json", "stage1k_report.md"):
        assert (tmp_path / filename).is_file()
