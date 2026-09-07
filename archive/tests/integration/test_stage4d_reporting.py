from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4b import Stage4bConfig


def _config() -> Stage4bConfig:
    return Stage4bConfig(
        sample_sizes=(300, 600, 650, 700, 750),
        hub_strength=0.5,
        alphas=(0.05, 0.10),
        replicates=4,
        master_seed=20260830,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=0.80,
        maximum_true_edge_prune_fpr=0.10,
        required_margin=0.02,
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
        "status": "ok",
        "error": "",
    }


def test_early_stop_met_when_transition_matches_base_mechanism():
    from mintnet.experiments.stage4d_reporting import write_stage4d_report

    rows = []
    for n, tpr in ((300, 0.3), (600, 0.5), (650, 0.95), (700, 0.95), (750, 0.95)):
        for shape in ("hub", "overlap"):
            for replicate in range(4):
                rows.append(_row(shape, n, 0.10, replicate, tpr=tpr, fpr=0.0))
    raw = pd.DataFrame(rows)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        write_stage4d_report(raw, _config(), Path(tmp))
        report = (Path(tmp) / "stage4d_report.md").read_text(encoding="utf-8")

    assert "MET" in report
    assert "NOT MET" not in report


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    from mintnet.experiments.stage4d_reporting import write_stage4d_report

    rows = []
    for n in (300, 600, 650, 700, 750):
        for shape in ("hub", "overlap"):
            for replicate in range(4):
                rows.append(_row(shape, n, 0.10, replicate, tpr=0.9, fpr=0.0))
    raw = pd.DataFrame(rows)

    decision = write_stage4d_report(raw, _config(), tmp_path)

    assert len(decision.by_cell) == 10  # 2 shapes x 5 N
    for filename in ("decision.json", "stage4d_report.md", "indirect_tpr_vs_n.png"):
        assert (tmp_path / filename).is_file()
