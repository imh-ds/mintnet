from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2 import Stage2Config
from mintnet.experiments.stage2_reporting import evaluate_stage2_gate, select_rule, write_stage2_report


def _config() -> Stage2Config:
    return Stage2Config(
        sample_sizes=(750, 1500),
        strength=0.5,
        triangle_family="moderate",
        noise_count=6,
        uncorrected_alphas=(0.01, 0.05),
        bh_q_values=(0.10,),
        replicates=4,
        master_seed=20260829,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_recall=0.80,
        maximum_fdr=0.10,
    )


def _row(n, rule_kind, threshold, replicate, recall, fdr) -> dict[str, object]:
    # Unit-weight synthetic counts (true_pair_count=1, total_flagged=1 per
    # row) so the pooled sum-of-counts computation in _rule_metrics exactly
    # reproduces these per-replicate recall/fdr values -- valid here because
    # every replicate within a given (n, rule_kind, threshold) group below
    # uses the same recall/fdr, so pooling and averaging coincide.
    return {
        "n": n,
        "replicate": replicate,
        "seed": 1,
        "rule_kind": rule_kind,
        "threshold": threshold,
        "true_positives": recall,
        "false_positives": fdr,
        "total_flagged": 1.0,
        "true_pair_count": 1.0,
        "recall": recall,
        "false_discovery_rate": fdr,
        "per_edge_fpr": 0.01,
        "any_false_edge": 1.0 if fdr > 0 else 0.0,
        "elapsed_seconds": 0.001,
        "status": "ok",
        "error": "",
    }


def _raw_rows(*, n_1500_uncorrected_fails: bool = False) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for replicate in range(4):
        # N=750: both uncorrected(.01) and bh(.10) eligible -> prefer uncorrected (simplest).
        rows.append(_row(750, "uncorrected", 0.01, replicate, 0.90, 0.05))
        rows.append(_row(750, "uncorrected", 0.05, replicate, 0.95, 0.40))  # fails FDR
        rows.append(_row(750, "bh", 0.10, replicate, 0.90, 0.08))

        # N=1500: only bh(.10) eligible (uncorrected all fail FDR unless flagged otherwise).
        uncorrected_fdr = 0.05 if n_1500_uncorrected_fails is False else 0.40
        uncorrected_ok = not n_1500_uncorrected_fails
        rows.append(_row(1500, "uncorrected", 0.01, replicate, 0.90 if uncorrected_ok else 0.90, uncorrected_fdr))
        rows.append(_row(1500, "uncorrected", 0.05, replicate, 0.95, 0.40))
        rows.append(_row(1500, "bh", 0.10, replicate, 0.90, 0.08))
    return pd.DataFrame(rows)


def test_select_rule_prefers_uncorrected_over_bh_when_both_eligible():
    raw = _raw_rows()
    selected = select_rule(raw, 750, _config())
    assert selected == ("uncorrected", 0.01)


def test_select_rule_falls_back_to_bh_when_no_uncorrected_rule_is_eligible():
    raw = _raw_rows(n_1500_uncorrected_fails=True)
    selected = select_rule(raw, 1500, _config())
    assert selected == ("bh", 0.10)


def test_gate_produces_a_per_n_table():
    decision = evaluate_stage2_gate(_raw_rows(), _config())

    by_n = {d.n: d for d in decision.by_n}
    assert by_n[750].status == "PROCEED"
    assert by_n[750].selected_rule_kind == "uncorrected"
    assert by_n[750].selected_threshold == 0.01


def test_report_writes_required_evidence(tmp_path: Path) -> None:
    decision = write_stage2_report(_raw_rows(), _config(), tmp_path)

    assert len(decision.by_n) == 2
    for filename in (
        "aggregate_metrics.csv",
        "decision.json",
        "stage2_report.md",
        "screening_operating_curve.png",
    ):
        assert (tmp_path / filename).is_file()
