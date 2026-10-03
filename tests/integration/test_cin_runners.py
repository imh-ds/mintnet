from __future__ import annotations

import hashlib
import json
import csv
import os
import subprocess
import sys
from datetime import date
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from mintnet.experiments.cin_baseline import load_config as load_panel_config
from mintnet.experiments.cin_baseline import (
    CASE_ORDER,
    COMBINATION_COLUMNS as PANEL_COMBINATION_COLUMNS,
    expected_combinations as expected_panel_combinations,
    expected_row_count as expected_panel_rows,
    methods_for_case,
    run_baseline,
)
from mintnet.experiments.cin_cost import (
    COST_RAW_COLUMNS,
    expected_combinations as expected_cost_combinations,
    expected_row_count as expected_cost_rows,
    load_config as load_cost_config,
    run_cost,
)
from mintnet.experiments import cin_cost_reporting
from mintnet.experiments import cin_baseline_reporting
from mintnet.experiments import cin_baseline
from scripts.aggregate_cin_sidecars import aggregate_sidecars
from scripts.aggregate_shards import aggregate as aggregate_generic
from mintnet.experiments.cin_common import (
    IncrementalCsvWriter,
    canonical_pair_sidecar_name,
    derive_seed_bundle,
    sha256_text_file,
    write_provenance,
    write_resolved_config,
)
from mintnet.simulation.cin_networks import GeneratorAcceptanceError


ROOT = Path(__file__).resolve().parents[2]


def test_seed_bundle_uses_exact_five_children_and_full_grid_indices() -> None:
    root = np.random.SeedSequence([20260924, 9009, 2, 1, 1000])
    children = root.spawn(5)
    expected = tuple(int(child.generate_state(1, dtype=np.uint32)[0]) for child in children)
    bundle = derive_seed_bundle(20260924, 2, 1, 1000)

    assert (bundle.structure, bundle.sample, bundle.cin_fit, bundle.comparator_fit, bundle.stability) == expected
    assert bundle == derive_seed_bundle(20260924, 2, 1, 1000)
    assert bundle != derive_seed_bundle(20260924, 0, 1, 1000)
    assert bundle != derive_seed_bundle(20260924, 2, 0, 1000)


def test_incremental_writer_flushes_header_and_rows(tmp_path: Path) -> None:
    path = tmp_path / "raw_metrics.csv"
    writer = IncrementalCsvWriter(path, ("case", "status"))
    writer.append({"case": "A", "status": "complete"})
    assert path.read_text(encoding="utf-8") == "case,status\nA,complete\n"
    writer.append({"case": "B", "status": "error"})
    writer.close()
    assert path.read_text(encoding="utf-8") == "case,status\nA,complete\nB,error\n"


def test_common_names_and_resolved_config_hash_are_stable(tmp_path: Path) -> None:
    assert canonical_pair_sidecar_name("A", "validation", 1000, "cin") == (
        "A_validation_1000_cin_pairs.csv.gz"
    )
    payload = {"master_seed": 20260924, "cases": ["A", "F"]}
    digest = write_resolved_config(tmp_path, payload)
    expected = hashlib.sha256((tmp_path / "resolved_config.yaml").read_bytes()).hexdigest()
    assert digest == expected
    assert write_resolved_config(tmp_path, payload) == digest


def test_provenance_records_hashes_runtime_and_thread_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("master_seed: 20260924\n", encoding="utf-8")
    charter_path = tmp_path / "charter.md"
    charter_path.write_text("frozen", encoding="utf-8")
    write_provenance(
        tmp_path,
        config_payload={"master_seed": 20260924},
        source_path=config_path,
        charter_path=charter_path,
        runtime_seconds=1.25,
        peak_rss_mb=None,
    )
    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["config_sha256"] == sha256_text_file(config_path)
    assert metadata["charter_sha256"] == sha256_text_file(charter_path)
    assert metadata["runtime_seconds"] == 1.25
    assert metadata["peak_rss_mb"] is None
    assert metadata["thread_settings"]["environment"]["OMP_NUM_THREADS"] == "1"
    assert "threadpool_info" in metadata["thread_settings"]


def test_cost_config_has_eight_cells_and_disjoint_replicate_defaults() -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost.yaml")
    assert tuple(cell.cell_id for cell in config.cells) == (
        "c_p8_n100",
        "c_p30_n100",
        "c_p100_n100",
        "c_p100_n300",
        "c_p100_n1000",
        "k5_p30_n150",
        "k10_p100_n200",
        "mix_p100_n200",
    )
    assert config.repeats == (1, 2)


def test_cost_smoke_preserves_eight_ids_and_uses_tiny_dimensions() -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    assert all(cell.p <= 12 and cell.n <= 60 for cell in config.cells)
    assert next(cell for cell in config.cells if cell.cell_id == "k10_p100_n200").kind == "categorical10"


def test_cost_configs_declare_the_frozen_charter_and_same_cell_ids() -> None:
    full = load_cost_config(ROOT / "configs" / "cin_cost.yaml")
    smoke = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    expected = (
        "c_p8_n100", "c_p30_n100", "c_p100_n100", "c_p100_n300",
        "c_p100_n1000", "k5_p30_n150", "k10_p100_n200", "mix_p100_n200",
    )
    assert tuple(cell.cell_id for cell in full.cells) == expected
    assert tuple(cell.cell_id for cell in smoke.cells) == expected
    assert full.repeats == (1, 2)
    assert smoke.repeats == (1,)
    assert full.charter_path == ROOT / "docs" / "cin_cost_charter.md"
    charter = full.charter_path.read_text(encoding="utf-8")
    for gate in ("G-time-small", "G-time-100", "G-mem", "G-complete", "G-factor", "G-fallback"):
        assert gate in charter
    assert "This is a cost pilot; timings are single-dataset measurements on shared hosted runners." in charter


def test_panel_config_has_phase_ranges_and_smoke_overrides() -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline.yaml")
    smoke = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    assert config.cases == tuple("ABCDEFGHI") + ("regression",)
    assert config.development_replicates == (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert config.validation_replicates == tuple(range(1000, 1020))
    assert smoke.cases == ("A", "F")
    assert smoke.development_replicates == (0, 1)
    assert smoke.validation_replicates == (1000, 1001)
    assert smoke.n_overrides == {"A": 40, "F": 40}


def test_panel_config_has_frozen_charter_and_statistical_controls() -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline.yaml")
    smoke = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    charter = ROOT / "docs" / "cin_baseline_charter.md"
    expected_hash = sha256_text_file(charter)

    assert config.charter_path == charter
    assert smoke.charter_path == charter
    assert config.charter_sha256 == expected_hash
    assert smoke.charter_sha256 == expected_hash
    assert config.delta_candidates == (0.005, 0.01, 0.02)
    assert config.strong_edge_threshold == 0.01
    assert config.point_fit_max_seconds == 600.0
    assert config.stability_max_seconds == 600.0


def test_followup_f_generator_cap_is_passed_and_attempts_are_durable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = yaml.safe_load((ROOT / "configs" / "cin_followup_v1.yaml").read_text())
    payload["development_replicates"] = [2000]
    payload["validation_replicates"] = [3000]
    payload["f_max_tries"] = 500
    payload["charter"] = str((ROOT / "docs" / "cin_followup_charter_v1.md").resolve())
    config_path = tmp_path / "followup.yaml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    requested_caps: list[int] = []

    def exhaust_f_cap(case: str, **kwargs: object) -> None:
        requested_caps.append(int(kwargs["max_tries"]))
        raise GeneratorAcceptanceError(case, int(kwargs["max_tries"]))

    monkeypatch.setattr(cin_baseline, "generate_case", exhaust_f_cap)
    config = load_panel_config(config_path)
    raw = run_baseline(
        config,
        tmp_path / "panel",
        cases=("F",),
        replicate_batches=("dev0",),
        write_report=False,
        f_max_tries=1000,
    )

    assert requested_caps == [1000]
    assert raw["status"].tolist() == ["error"]
    assert raw["generator_attempts"].tolist() == [1000]
    assert yaml.safe_load((tmp_path / "panel" / "resolved_config.yaml").read_text())[
        "f_max_tries"
    ] == 1000


def test_followup_support_aware_setting_reaches_cin_config(monkeypatch: pytest.MonkeyPatch) -> None:
    seeds = derive_seed_bundle(20260928, CASE_ORDER.index("F"), 0, 2000)
    captured: dict[str, object] = {}
    fit_result = SimpleNamespace(
        pairs=pd.DataFrame(),
        metadata={"runtime": {"elapsed_seconds": 0.25}},
    )

    def capture_fit(_frame: pd.DataFrame, _schema: object, config: object) -> object:
        captured["support_aware_inner_splits"] = config.support_aware_inner_splits
        return fit_result

    monkeypatch.setattr(cin_baseline, "fit_network", capture_fit)

    cin_baseline._fit_method(
        "cin",
        pd.DataFrame({"V00": [0, 1]}),
        {"V00": {"kind": "categorical", "levels": [0, 1]}},
        seeds,
        support_aware_inner_splits=True,
    )

    assert captured["support_aware_inner_splits"] is True


def test_followup_baseline_override_is_recorded_in_resolved_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = yaml.safe_load((ROOT / "configs" / "cin_followup_v1.yaml").read_text())
    payload["development_replicates"] = [2000]
    payload["validation_replicates"] = [3000]
    payload["charter"] = str((ROOT / "docs" / "cin_followup_charter_v1.md").resolve())
    config_path = tmp_path / "followup.yaml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    config = load_panel_config(config_path)
    captured: dict[str, object] = {}
    frame = pd.DataFrame({"V00": [0, 1], "V01": [1, 0]})
    schema = {
        "V00": {"kind": "categorical", "levels": [0, 1]},
        "V01": {"kind": "categorical", "levels": [0, 1]},
    }
    pair_frame = pd.DataFrame(
        [{"node_i": "V00", "node_j": "V01", "weight_nats_raw": 0.1, "status": "complete"}]
    )
    nodes = pd.DataFrame(
        columns=[
            "node", "full_minus_intercept", "variance_floor_hits",
            "clipped_fraction_mean", "zero_sum_fallbacks", "min_probability",
        ]
    )
    fit_result = SimpleNamespace(nodes=nodes, metadata={"runtime": {"elapsed_seconds": 0.1}})

    monkeypatch.setattr(
        cin_baseline,
        "_dataset",
        lambda *_args: (frame, schema, frozenset(), None, {"rejection_tries": 2}),
    )

    def fake_fit(*_args: object, support_aware_inner_splits: bool = True) -> tuple[object, object, float]:
        captured["support_aware_inner_splits"] = support_aware_inner_splits
        return pair_frame, fit_result, 0.1

    monkeypatch.setattr(cin_baseline, "_fit_method", fake_fit)
    monkeypatch.setattr(cin_baseline, "_metrics", lambda *_args, **_kwargs: None)

    run_baseline(
        config,
        tmp_path / "baseline",
        cases=("F",),
        replicate_batches=("dev0",),
        write_report=False,
        support_aware_inner_splits=False,
    )

    resolved = yaml.safe_load((tmp_path / "baseline" / "resolved_config.yaml").read_text())
    assert captured["support_aware_inner_splits"] is False
    assert resolved["support_aware_inner_splits"] is False


def test_panel_smoke_persists_charter_identity(tmp_path: Path) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    raw = run_baseline(config, tmp_path / "panel", write_report=False)
    expected_hash = sha256_text_file(config.charter_path)

    assert raw["charter_sha256"].eq(expected_hash).all()
    metadata = json.loads((tmp_path / "panel" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert raw["charter_sha256"].nunique() == 1
    cin_rows = raw.loc[raw["method"] == "cin"]
    assert pd.to_numeric(cin_rows["point_fit_seconds"], errors="coerce").notna().all()


def test_optional_stability_failure_preserves_point_fit_and_pair_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    config = replace(
        config,
        stability_cases=("A",),
        stability_repeats=1,
        stability_max_seconds=30.0,
    )

    def fail_stability(*args: object, **kwargs: object) -> object:
        raise RuntimeError("forced optional stability failure")

    monkeypatch.setattr(cin_baseline, "estimate_stability", fail_stability)
    output = tmp_path / "optional-stability-failure"
    raw = run_baseline(
        config,
        output,
        cases=("A",),
        replicate_batches=("val0",),
        write_report=False,
    )
    row = raw.loc[raw["method"] == "cin"].iloc[0]

    assert row["status"] in {"complete", "incomplete"}
    assert pd.notna(row["pair_sidecar_file"])
    assert row["stability_status"] == "error"
    assert "forced optional stability failure" in row["stability_error"]
    assert pd.isna(row["stability_sidecar_file"])
    assert (output / "sidecars" / row["pair_sidecar_file"]).is_file()
    manifest = pd.read_csv(output / "sidecar_manifest.csv")
    assert set(manifest.loc[manifest["kind"] == "pairs", "file"]) >= {
        row["pair_sidecar_file"]
    }
    assert not manifest["kind"].eq("stability").any()


def test_invalid_config_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump({"master_seed": 1, "cases": ["Z"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown case"):
        load_panel_config(path)


def test_cost_expected_combinations_cover_full_grid() -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost.yaml")
    assert expected_cost_rows(config) == 16
    assert len(expected_cost_combinations(config)) == 16
    assert ("c_p100_n1000", 2) in expected_cost_combinations(config)


def test_cost_smoke_writes_incremental_raw_rows_and_pair_sidecars(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    output = tmp_path / "cost"
    raw = run_cost(config, output)

    assert list(raw.columns) == list(COST_RAW_COLUMNS)
    task10_columns = {
        "requested_directional_outer_fits", "status_histogram_json",
        "variance_floor_hit_rate", "probability_clipped_fraction",
        "probability_min", "zero_sum_fallbacks", "tuned_penalty_min_fraction",
        "tuned_penalty_max_fraction", "tuned_penalty_histogram_json",
        "first_scaled_normal_residual", "environment_json", "charter_sha256",
    }
    assert task10_columns <= set(raw.columns)
    assert raw["requested_directional_outer_fits"].notna().all()
    assert raw["status_histogram_json"].map(json.loads).map(lambda value: isinstance(value, dict)).all()
    assert raw["tuned_penalty_histogram_json"].map(json.loads).map(lambda value: isinstance(value, dict)).all()
    assert raw["charter_sha256"].nunique() == 1
    node_orders = raw["node_order_json"].map(json.loads)
    assert all(
        len(order) == int(p) and len(set(order)) == int(p)
        for order, p in zip(node_orders, raw["p"])
    )
    environments = raw["environment_json"].map(json.loads)
    assert environments.map(lambda value: "blas" in value and "cpu" in value).all()
    categorical = raw.loc[raw["kind"] == "categorical10"].iloc[0]
    assert categorical["q"] > 0
    assert categorical["t"] > 0
    assert categorical["n_requested_omissions"] > 0
    assert len(raw) == expected_cost_rows(config) == 8
    assert set(raw["status"]) == {"complete"}
    assert (output / "raw_metrics.csv").exists()
    assert (output / "resolved_config.yaml").exists()
    assert (output / "metadata.json").exists()
    manifest = raw["pair_sidecar_file"].dropna().tolist()
    assert len(manifest) == 8
    assert len(list((output / "sidecars").glob("*.csv.gz"))) == 8
    first = pd.read_csv(output / "sidecars" / manifest[0], compression="gzip")
    assert len(first) == 8 * 7 // 2
    assert "truth_edges" not in raw.columns
    assert (output / "cost_summary.csv").exists()
    assert (output / "cost_report.md").exists()


def test_cost_shard_selection_writes_only_selected_identity(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    output = tmp_path / "one-cell"
    raw = run_cost(config, output, cells=("c_p8_n100",), repeats=(1,), write_report=False)

    assert raw[["cell", "repeat"]].to_dict("records") == [{"cell": "c_p8_n100", "repeat": 1}]
    assert not (output / "cost_report.md").exists()


def test_cost_report_does_not_claim_recovery_metrics(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    raw = pd.DataFrame(
        [{"cell": "c_p8_n100", "repeat": 1, "status": "complete", "elapsed_seconds": 1.0}]
    )
    cin_cost_reporting.write_report(raw, config, tmp_path)
    report = (tmp_path / "cost_report.md").read_text(encoding="utf-8")
    assert "cost pilot" in report.lower()
    assert "recovery" not in report.lower()


def _gate_row(
    *,
    cell: str,
    repeat: int,
    p: int,
    elapsed: float,
    peak: float = 900.0,
    status: str = "complete",
    factors: int = 40,
    fallback: float = 0.0,
) -> dict[str, object]:
    return {
        "cell": cell,
        "repeat": repeat,
        "p": p,
        "n": 100,
        "elapsed_seconds": elapsed,
        "peak_rss_mb": peak,
        "n_large_factorizations": factors,
        "fallback_fraction": fallback,
        "status": status,
        "n_pairs_complete": 1 if status == "complete" else 0,
        "n_pairs_total": 1,
        "status_histogram_json": json.dumps({status: 1}),
    }


def test_cost_gate_evaluation_uses_slower_repeat_and_strict_memory_limit() -> None:
    from mintnet.experiments.cin_cost_reporting import evaluate_gates

    raw = pd.DataFrame([
        _gate_row(cell="c_p100_n100", repeat=1, p=100, elapsed=150.0),
        _gate_row(cell="c_p100_n100", repeat=2, p=100, elapsed=181.0),
    ])
    config = load_cost_config(ROOT / "configs" / "cin_cost.yaml")
    result = evaluate_gates(raw, config)
    cell = result.loc[result["cell"] == "c_p100_n100"].iloc[0]
    assert cell["effective_elapsed_seconds"] == 181.0
    assert cell["G-time-100"] == "fail"
    assert bool(cell["repeat_required"]) is True
    assert bool(cell["repeat_satisfied"]) is True

    raw.loc[:, "peak_rss_mb"] = 1024.0
    result = evaluate_gates(raw, config)
    assert result["G-mem"].eq("fail").all()


def test_cost_gate_evaluation_preserves_status_and_boundary_repeat_requirements() -> None:
    from mintnet.experiments.cin_cost_reporting import evaluate_gates

    raw = pd.DataFrame([
        _gate_row(cell="c_p8_n100", repeat=1, p=8, elapsed=25.0, status="numerical_failure"),
    ])
    result = evaluate_gates(raw, load_cost_config(ROOT / "configs" / "cin_cost.yaml"))
    cell = result.loc[result["cell"] == "c_p8_n100"].iloc[0]
    assert bool(cell["repeat_required"]) is True
    assert bool(cell["repeat_satisfied"]) is False
    assert cell["G-complete"] == "fail"


def test_cost_report_contains_gate_columns_and_the_exact_cost_nonclaim(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    raw = pd.DataFrame([_gate_row(cell="c_p8_n100", repeat=1, p=8, elapsed=1.0)])
    cin_cost_reporting.write_report(raw, config, tmp_path)
    summary = pd.read_csv(tmp_path / "cost_summary.csv")
    report = (tmp_path / "cost_report.md").read_text(encoding="utf-8")
    assert "G-complete" in summary.columns
    assert "This is a cost pilot; timings are single-dataset measurements on shared hosted runners." in report
    assert "recovery" not in report.lower()


def test_panel_method_matrix_and_full_phase_combinations() -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    assert PANEL_COMBINATION_COLUMNS == ("case", "phase", "method")
    assert methods_for_case("A") == ("cin", "cin_linear", "ebicglasso")
    assert methods_for_case("E") == ("cin", "cin_linear", "ebicglasso")
    assert methods_for_case("F") == ("cin",)
    assert methods_for_case("regression") == ("cin",)
    assert expected_panel_rows(config) == 16
    combinations = expected_panel_combinations(config)
    assert len(combinations) == 8
    assert ("A", "development", "ebicglasso") in combinations
    assert ("F", "validation", "cin_linear") not in combinations


def test_panel_smoke_writes_rows_for_supported_methods(tmp_path: Path) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    output = tmp_path / "panel"
    raw = run_baseline(config, output)

    assert len(raw) == expected_panel_rows(config)
    assert set(raw["status"]) <= {"complete", "incomplete"}
    assert set(raw.loc[raw["case"] == "F", "method"]) == {"cin"}
    assert set(raw.loc[raw["case"] == "A", "method"]) == {"cin", "cin_linear", "ebicglasso"}
    task11_columns = {
        "charter_sha256", "n_true_edges", "n_nonempty_delta_views",
        "n_nonempty_agreement_views", "oracle_cmi_mae_true", "oracle_cmi_mae_all",
        "orientation_gap_q50", "variance_floor_hits", "probability_clipped_fraction",
        "zero_sum_fallbacks", "minimum_probability",
    }
    assert task11_columns <= set(raw.columns)
    assert raw["charter_sha256"].notna().all()
    assert raw["n_true_edges"].notna().all()
    assert raw["n_nonempty_delta_views"].notna().all()
    assert (output / "raw_metrics.csv").exists()
    assert len(list((output / "sidecars").glob("*_pairs.csv.gz"))) == 16


def test_panel_metrics_record_complete_pair_truth_and_population_diagnostics() -> None:
    pair_frame = pd.DataFrame(
        [
            {"node_i": "A", "node_j": "B", "gain_i_to_j": 0.2, "gain_j_to_i": 0.2, "weight_nats_raw": 0.2, "orientation_gap": 0.1, "status": "complete"},
            {"node_i": "A", "node_j": "C", "gain_i_to_j": 0.1, "gain_j_to_i": -0.1, "weight_nats_raw": 0.1, "orientation_gap": 0.2, "status": "complete"},
            {"node_i": "B", "node_j": "C", "gain_i_to_j": 0.0, "gain_j_to_i": 0.0, "weight_nats_raw": 0.0, "orientation_gap": np.nan, "status": "complete"},
        ]
    )
    row = {column: None for column in cin_baseline.PANEL_RAW_COLUMNS}
    cin_baseline._metrics(
        row,
        pair_frame,
        frozenset({("A", "B"), ("B", "C")} ),
        {("A", "B"): 0.2, ("A", "C"): 0.05, ("B", "C"): 0.04},
        strong_edge_threshold=0.01,
    )

    assert row["n_true_edges"] == 2
    assert row["n_strong_edges"] == 2
    assert row["n_pairs_complete"] == 3
    assert row["n_failed_pairs"] == 0
    assert row["strong_edge_recall"] == 0.5
    assert row["oracle_cmi_mae_true"] == pytest.approx(0.02)
    assert row["oracle_cmi_mae_all"] == pytest.approx((0.0 + 0.05 + 0.04) / 3)
    assert row["delta_01_empty"] is False
    assert row["agreement_delta_0_displayed_count"] == 1
    assert row["n_nonempty_delta_views"] == 4
    assert row["n_nonempty_agreement_views"] == 4
    assert row["orientation_gap_q50"] == pytest.approx(0.15)


def test_panel_metrics_record_strong_recall_at_each_display_threshold() -> None:
    pair_frame = pd.DataFrame(
        [
            {"node_i": "A", "node_j": "B", "gain_i_to_j": 0.2, "gain_j_to_i": 0.2, "weight_nats_raw": 0.025, "orientation_gap": 0.0, "status": "complete"},
            {"node_i": "A", "node_j": "C", "gain_i_to_j": 0.1, "gain_j_to_i": 0.1, "weight_nats_raw": 0.018, "orientation_gap": 0.0, "status": "complete"},
            {"node_i": "A", "node_j": "D", "gain_i_to_j": 0.1, "gain_j_to_i": 0.1, "weight_nats_raw": 0.009, "orientation_gap": 0.0, "status": "complete"},
        ]
    )
    row = {column: None for column in cin_baseline.PANEL_RAW_COLUMNS}
    cin_baseline._metrics(
        row,
        pair_frame,
        frozenset({("A", "B"), ("A", "C"), ("A", "D")} ),
        {("A", "B"): 0.03, ("A", "C"): 0.005, ("A", "D"): 0.02},
        strong_edge_threshold=0.01,
    )

    assert row["delta_005_recall"] == pytest.approx(1.0)
    assert row["delta_005_strong_recall"] == pytest.approx(1.0)
    assert row["delta_01_recall"] == pytest.approx(2 / 3)
    assert row["delta_01_strong_recall"] == pytest.approx(0.5)
    assert row["delta_02_strong_recall"] == pytest.approx(0.5)


def test_panel_metrics_make_empty_precision_unavailable() -> None:
    pair_frame = pd.DataFrame(
        [
            {"node_i": "A", "node_j": "B", "gain_i_to_j": 0.0, "gain_j_to_i": 0.0, "weight_nats_raw": 0.0, "orientation_gap": 0.0, "status": "complete"},
        ]
    )
    row = {column: None for column in cin_baseline.PANEL_RAW_COLUMNS}
    cin_baseline._metrics(row, pair_frame, frozenset({("A", "B")} ), None, strong_edge_threshold=0.01)

    assert row["delta_0_empty"] is True
    assert np.isnan(row["delta_0_precision"])
    assert row["n_nonempty_delta_views"] == 0


def test_sidecar_aggregation_combines_cost_pairs_and_manifest(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    source = tmp_path / "source"
    run_cost(config, source, write_report=False)
    output = tmp_path / "aggregate"
    pairs, stability = aggregate_sidecars(source, output)

    assert len(pairs) == (8 * 7 // 2) + 7 * (12 * 11 // 2)
    assert stability.empty
    assert (output / "sidecars" / "pairs_all.csv.gz").exists()
    assert (output / "sidecars" / "sidecar_manifest.csv").exists()


def test_sidecar_aggregation_rejects_tampering_and_orphans(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    source = tmp_path / "source"
    run_cost(config, source, write_report=False)
    first = next((source / "sidecars").glob("*.csv.gz"))
    first.write_bytes(first.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="sha256"):
        aggregate_sidecars(source, tmp_path / "bad-hash")

    source = tmp_path / "orphan-source"
    run_cost(config, source, write_report=False)
    (source / "sidecars" / "orphan.csv.gz").write_bytes(b"not listed")
    with pytest.raises(ValueError, match="orphan"):
        aggregate_sidecars(source, tmp_path / "bad-orphan")

    manifestless = tmp_path / "manifestless-orphan"
    (manifestless / "sidecars").mkdir(parents=True)
    pd.DataFrame(
        [{"cell": "c_p8_n100", "repeat": 0, "method": "cin", "pair_sidecar_file": None}]
    ).to_csv(manifestless / "raw_metrics.csv", index=False)
    (manifestless / "sidecars" / "orphan.csv.gz").write_bytes(b"orphan")
    with pytest.raises(ValueError, match="orphan"):
        aggregate_sidecars(manifestless, tmp_path / "bad-manifestless-orphan")


def test_sidecar_aggregation_rejects_duplicate_raw_identity(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    source = tmp_path / "source"
    run_cost(config, source, cells=("c_p8_n100",), write_report=False)
    raw_path = source / "raw_metrics.csv"
    raw = pd.read_csv(raw_path)
    pd.concat([raw, raw.iloc[[0]]], ignore_index=True).to_csv(raw_path, index=False)
    with pytest.raises(ValueError, match="duplicate raw identity"):
        aggregate_sidecars(source, tmp_path / "duplicate")


def _write_synthetic_sidecar_shard(
    root: Path, table: pd.DataFrame, *, kind: str, raw_updates: dict[str, object]
) -> None:
    (root / "sidecars").mkdir(parents=True)
    file_name = f"A_validation_1000_cin_{kind}.csv.gz"
    sidecar_path = root / "sidecars" / file_name
    table.to_csv(sidecar_path, index=False, compression="gzip", lineterminator="\n")
    identity = {"case": "A", "phase": "validation", "replicate": 1000, "method": "cin"}
    raw_row = {
        **identity,
        "p": 3,
        "node_order_json": '["a","b","c"]',
        "pair_sidecar_file": None,
        "stability_sidecar_file": None,
        **raw_updates,
    }
    raw_row["pair_sidecar_file" if kind == "pairs" else "stability_sidecar_file"] = file_name
    pd.DataFrame([raw_row]).to_csv(root / "raw_metrics.csv", index=False, lineterminator="\n")
    manifest_row = {
        **identity,
        "file": file_name,
        "kind": kind,
        "n_rows": len(table),
        "sha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
    }
    pd.DataFrame([manifest_row]).to_csv(root / "sidecar_manifest.csv", index=False, lineterminator="\n")


def test_sidecar_aggregation_rejects_duplicate_pair_and_wrong_identity(tmp_path: Path) -> None:
    pairs = pd.DataFrame(
        {"node_i": ["a", "a", "a"], "node_j": ["b", "c", "b"], "status": ["complete"] * 3}
    )
    source = tmp_path / "duplicate-pair"
    _write_synthetic_sidecar_shard(source, pairs, kind="pairs", raw_updates={})
    with pytest.raises(ValueError, match="pair identit"):
        aggregate_sidecars(source, tmp_path / "duplicate-pair-out")

    wrong_identity = pd.DataFrame(
        {"node_i": ["a", "a", "b"], "node_j": ["b", "c", "c"], "status": ["complete"] * 3}
    )
    wrong_identity["case"] = "B"
    source = tmp_path / "wrong-identity"
    _write_synthetic_sidecar_shard(source, wrong_identity, kind="pairs", raw_updates={})
    with pytest.raises(ValueError, match="identity mismatch"):
        aggregate_sidecars(source, tmp_path / "wrong-identity-out")


def test_sidecar_aggregation_requires_canonical_node_order_metadata(tmp_path: Path) -> None:
    pairs = pd.DataFrame(
        {"node_i": ["a", "a", "b"], "node_j": ["b", "c", "c"], "status": ["complete"] * 3}
    )
    source = tmp_path / "missing-node-order"
    _write_synthetic_sidecar_shard(source, pairs, kind="pairs", raw_updates={})
    raw_path = source / "raw_metrics.csv"
    pd.read_csv(raw_path).drop(columns="node_order_json").to_csv(raw_path, index=False)

    with pytest.raises(ValueError, match="canonical node order metadata is missing"):
        aggregate_sidecars(source, tmp_path / "missing-node-order-out")


def test_sidecar_aggregation_requires_repeat_ids_and_requested_coverage(tmp_path: Path) -> None:
    rows = pd.DataFrame(
        {
            "repeat_id": [0, 0, 0],
            "repeat_seed": [11, 11, 11],
            "node_i": ["a", "a", "b"],
            "node_j": ["b", "c", "c"],
            "status": ["complete"] * 3,
        }
    )
    metadata = {
        "stability_repeats_requested": 2,
        "stability_repeat_seeds_json": "[11,22]",
        "stability_completed_repeat_ids_json": "[0,1]",
        "stability_node_order_json": '["a","b","c"]',
        "stability_status": "complete",
    }
    source = tmp_path / "missing-repeat"
    _write_synthetic_sidecar_shard(source, rows, kind="stability", raw_updates=metadata)
    with pytest.raises(ValueError, match="coverage disagrees"):
        aggregate_sidecars(source, tmp_path / "missing-repeat-out")

    no_repeat_id = rows.drop(columns="repeat_id")
    source = tmp_path / "no-repeat-id"
    _write_synthetic_sidecar_shard(source, no_repeat_id, kind="stability", raw_updates=metadata)
    with pytest.raises(ValueError, match="missing identity columns"):
        aggregate_sidecars(source, tmp_path / "no-repeat-id-out")


def test_sidecar_aggregation_accepts_metadata_matched_partial_stability(tmp_path: Path) -> None:
    rows = pd.DataFrame(
        {
            "repeat_id": [0, 0, 0],
            "repeat_seed": [11, 11, 11],
            "node_i": ["a", "a", "b"],
            "node_j": ["b", "c", "c"],
            "status": ["complete"] * 3,
        }
    )
    metadata = {
        "stability_repeats_requested": 2,
        "stability_repeat_seeds_json": "[11,22]",
        "stability_completed_repeat_ids_json": "[0]",
        "stability_node_order_json": '["a","b","c"]',
        "stability_status": "interrupted",
    }
    source = tmp_path / "partial"
    _write_synthetic_sidecar_shard(source, rows, kind="stability", raw_updates=metadata)
    _, stability = aggregate_sidecars(source, tmp_path / "partial-out")
    assert len(stability) == 3
    assert set(stability["repeat_id"]) == {0}


def test_baseline_report_requires_promised_pair_sidecars(tmp_path: Path) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    source = tmp_path / "panel"
    raw = run_baseline(config, source, write_report=False)
    sidecar = next((source / "sidecars").glob("*_pairs.csv.gz"))
    sidecar.unlink()
    with pytest.raises(FileNotFoundError, match="sidecar"):
        cin_baseline_reporting.write_report(raw, config, source)


def _without_runtime_columns(frame: pd.DataFrame) -> pd.DataFrame:
    ignored = {
        "elapsed_seconds", "point_fit_seconds", "peak_rss_mb", "prepare_seconds", "features_seconds",
        "gram_factor_seconds", "h_seconds", "omission_seconds", "score_seconds",
        "aggregate_seconds", "outputs_seconds",
    }
    result = frame.drop(columns=[column for column in ignored if column in frame], errors="ignore").replace({None: np.nan})
    return result.sort_values(
        [column for column in ("cell", "repeat", "case", "phase", "replicate", "method") if column in frame]
    ).reset_index(drop=True)


def test_cost_full_grid_equals_single_cell_shards(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    full = run_cost(config, tmp_path / "full", write_report=False)
    shard_frames = []
    for cell in config.cells:
        shard_frames.append(run_cost(config, tmp_path / f"shard-{cell.cell_id}", cells=(cell.cell_id,), write_report=False))
    sharded = pd.concat(shard_frames, ignore_index=True)
    pd.testing.assert_frame_equal(_without_runtime_columns(full), _without_runtime_columns(sharded), check_dtype=False)
    resolved = (tmp_path / "full" / "resolved_config.yaml").read_bytes()
    assert all((tmp_path / f"shard-{cell.cell_id}" / "resolved_config.yaml").read_bytes() == resolved for cell in config.cells)


def test_panel_full_grid_equals_case_and_batch_shards(tmp_path: Path) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    full = run_baseline(config, tmp_path / "full", write_report=False)
    shard_frames = []
    for case in config.cases:
        for batch in ("dev0", "val0", "val1"):
            shard_frames.append(run_baseline(config, tmp_path / f"{case}-{batch}", cases=(case,), replicate_batches=(batch,), write_report=False))
    sharded = pd.concat(shard_frames, ignore_index=True)
    pd.testing.assert_frame_equal(_without_runtime_columns(full), _without_runtime_columns(sharded), check_dtype=False)
    assert set(sharded.loc[sharded["phase"] == "development", "replicate"]) == {0, 1}
    assert set(sharded.loc[sharded["phase"] == "validation", "replicate"]) == {1000, 1001}


def test_panel_pairs_b_and_d_datasets_while_preserving_case_specific_fit_seeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = replace(
        load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml"), cases=("B", "D")
    )
    captured: dict[str, tuple[object, pd.DataFrame, frozenset[tuple[str, str]]]] = {}

    def capture_run_method(config, output_dir, case, phase, replicate, method, seeds, frame, schema, truth, population_cmi):
        if method == "cin":
            captured[case] = (seeds, frame.copy(), truth)
        row = cin_baseline._empty_row(case, phase, replicate, method, seeds, len(frame), len(frame.columns))
        row.update({"status": "complete", "charter_sha256": config.charter_sha256})
        return row

    monkeypatch.setattr(cin_baseline, "_run_method", capture_run_method)
    run_baseline(
        config,
        tmp_path / "paired",
        cases=("B", "D"),
        replicate_batches=("dev0",),
        write_report=False,
    )

    b_seeds, b_frame, b_truth = captured["B"]
    d_seeds, d_frame, d_truth = captured["D"]
    assert (b_seeds.structure, b_seeds.sample) == (d_seeds.structure, d_seeds.sample)
    assert b_seeds.cin_fit != d_seeds.cin_fit
    assert b_truth == d_truth
    pd.testing.assert_frame_equal(b_frame.iloc[:, 1::2], d_frame.iloc[:, 1::2])
    np.testing.assert_allclose(
        d_frame.iloc[:, ::2].to_numpy(), np.sinh(0.5 * b_frame.iloc[:, ::2].to_numpy())
    )


def test_categorical_excess_loss_uses_categorical_targets_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    seeds = derive_seed_bundle(config.master_seed, 7, 0, 0)
    pair_frame = pd.DataFrame(
        [{"node_i": "cat", "node_j": "continuous", "weight_nats_raw": 0.1, "status": "complete"}]
    )
    nodes = pd.DataFrame(
        [
            {"node": "cat", "full_minus_intercept": -0.1, "variance_floor_hits": 0,
             "clipped_fraction_mean": 0.0, "zero_sum_fallbacks": 0, "min_probability": 0.1},
            {"node": "continuous", "full_minus_intercept": 0.9, "variance_floor_hits": 0,
             "clipped_fraction_mean": 0.0, "zero_sum_fallbacks": 0, "min_probability": 0.1},
        ]
    )
    fit_result = SimpleNamespace(nodes=nodes)
    monkeypatch.setattr(cin_baseline, "_fit_method", lambda *_args, **_kwargs: (pair_frame, fit_result, 0.1))
    monkeypatch.setattr(cin_baseline, "_metrics", lambda *_args, **_kwargs: None)

    row = cin_baseline._run_method(
        config,
        tmp_path,
        "H",
        "development",
        0,
        "cin",
        seeds,
        pd.DataFrame({"cat": [0, 1], "continuous": [0.1, 0.2]}),
        {"cat": {"kind": "categorical", "levels": [0, 1]}, "continuous": {"kind": "continuous"}},
        frozenset(),
        None,
    )

    assert row["categorical_excess_loss"] == pytest.approx(0.1)
    assert row["n_categorical_targets"] == 1


def test_generic_aggregator_accepts_cost_shards(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "cin_cost_smoke.yaml"
    config = load_cost_config(config_path)
    shards = tmp_path / "shards"
    shards.mkdir()
    for cell in config.cells:
        run_cost(config, shards / cell.cell_id, cells=(cell.cell_id,), write_report=False)
    output = tmp_path / "aggregated"
    raw = aggregate_generic("mintnet.experiments.cin_cost", config_path, shards, output)
    assert len(raw) == expected_cost_rows(config)
    assert (output / "raw_metrics.csv").exists()


def test_panel_phase_aggregator_stages_sidecars_before_writing_report(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "cin_baseline_smoke.yaml"
    config = load_panel_config(config_path)
    shards = tmp_path / "development-shards"
    run_baseline(
        config,
        shards / "dev0",
        replicate_batches=("dev0",),
        write_report=False,
    )
    output = tmp_path / "development"

    raw = aggregate_generic(
        "mintnet.experiments.cin_baseline",
        config_path,
        shards,
        output,
        phase="development",
    )

    assert len(raw) == 8
    assert set(raw["phase"]) == {"development"}
    assert (output / "baseline_report.md").exists()
    pairs = pd.read_csv(output / "sidecars" / "pairs_all.csv.gz", compression="gzip")
    assert set(pairs["phase"]) == {"development"}
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["provenance_validated"] is True
    assert metadata["shard_count"] == 1
    assert metadata["shards"][0]["thread_settings"]["threadpool_info"] is not None
    assert metadata["environment_summary"]["peak_rss_mb_contributing_shards"] == 0


def test_panel_phase_aggregator_rejects_wrong_replicate_identities(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "cin_baseline_smoke.yaml"
    config = load_panel_config(config_path)
    shards = tmp_path / "development-shards"
    run_baseline(config, shards / "dev0", replicate_batches=("dev0",), write_report=False)
    raw_path = shards / "dev0" / "raw_metrics.csv"
    raw = pd.read_csv(raw_path)
    raw.loc[0, "replicate"] = 99
    raw.to_csv(raw_path, index=False)

    with pytest.raises(SystemExit, match="identit"):
        aggregate_generic(
            "mintnet.experiments.cin_baseline",
            config_path,
            shards,
            tmp_path / "wrong-identities",
            phase="development",
        )


def test_panel_aggregate_validates_sidecars_before_publishing_raw_or_report(tmp_path: Path) -> None:
    config_path = ROOT / "configs" / "cin_baseline_smoke.yaml"
    config = load_panel_config(config_path)
    shards = tmp_path / "development-shards"
    run_baseline(config, shards / "dev0", replicate_batches=("dev0",), write_report=False)
    next((shards / "dev0" / "sidecars").glob("*.csv.gz")).unlink()
    output = tmp_path / "invalid-aggregate"

    with pytest.raises(FileNotFoundError, match="missing sidecar"):
        aggregate_generic(
            "mintnet.experiments.cin_baseline",
            config_path,
            shards,
            output,
            phase="development",
        )

    assert not (output / "raw_metrics.csv").exists()
    assert not (output / "baseline_report.md").exists()


def test_comparator_failure_is_an_error_row_without_pair_sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    monkeypatch.setattr("mintnet.experiments.cin_baseline.fit_ebicglasso", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("forced comparator failure")))
    raw = run_baseline(config, tmp_path / "failure", cases=("A",), replicate_batches=("dev0",), write_report=False)
    failed = raw.loc[raw["method"] == "ebicglasso"].iloc[0]
    assert failed["status"] == "error"
    assert pd.isna(failed["pair_sidecar_file"])
    assert failed["error_type"] == "RuntimeError"


def test_cost_failure_leaves_prior_rows_and_explicit_error_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    original = __import__("mintnet.experiments.cin_cost", fromlist=["generate_cost_input"]).generate_cost_input

    def fail_one(kind: str, p: int, n: int, *, seed: int):
        if p == 12 and kind == "categorical5":
            raise RuntimeError("forced dataset failure")
        return original(kind, p, n, seed=seed)

    monkeypatch.setattr("mintnet.experiments.cin_cost.generate_cost_input", fail_one)
    raw = run_cost(config, tmp_path / "failure", write_report=False)
    assert len(raw) == 8
    assert (raw["status"] == "complete").sum() >= 1
    failed = raw.loc[raw["kind"] == "categorical5"].iloc[0]
    assert failed["status"] == "error"
    assert failed["error_type"] == "RuntimeError"


def test_metadata_preserves_thread_and_resolved_config_provenance(tmp_path: Path) -> None:
    config = load_cost_config(ROOT / "configs" / "cin_cost_smoke.yaml")
    output = tmp_path / "metadata"
    run_cost(config, output, cells=("c_p8_n100",), write_report=False)
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    resolved_hash = hashlib.sha256((output / "resolved_config.yaml").read_bytes()).hexdigest()
    assert metadata["config_sha256"] == resolved_hash
    assert metadata["git_commit"]
    assert all(value == "1" for value in metadata["thread_settings"]["environment"].values())
    assert "threadpool_info" in metadata["thread_settings"]
    assert "peak_rss_mb" in metadata


def test_compute_ledger_records_task_10_dispatch() -> None:
    ledger = ROOT / "docs" / "cin_compute_ledger.csv"
    with ledger.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "phase", "workflow_run_id", "jobs", "wall_hours_max", "runner_hours_sum",
            "dispatched_by", "date", "purpose",
        ]
        rows = list(reader)
    assert any(
        row["phase"] == "cost_pilot"
        and row["workflow_run_id"] == "36096470047"
        and row["purpose"] == "Task 10 hosted CIN cost and completion gate"
        for row in rows
    )
    dispatches = [(row["phase"], row["workflow_run_id"]) for row in rows]
    assert len(dispatches) == len(set(dispatches))
    for row in rows:
        assert row["phase"] and row["workflow_run_id"] and row["purpose"]
        assert int(row["jobs"]) > 0
        assert math.isfinite(float(row["wall_hours_max"])) and float(row["wall_hours_max"]) >= 0
        assert math.isfinite(float(row["runner_hours_sum"])) and float(row["runner_hours_sum"]) >= 0
        assert date.fromisoformat(row["date"]).isoformat() == row["date"]


def test_user_guide_contains_verified_commands_and_full_shard_axes() -> None:
    guide = (ROOT / "docs" / "cin_user_guide.md").read_text(encoding="utf-8")
    assert "gh workflow run sharded_benchmark.yml" in guide
    assert "-f runner_module=mintnet.experiments.cin_baseline" in guide
    assert "-f dim1_flag=--cases" in guide
    assert "A,B,C,D,E,F,G,H,I,regression" in guide
    assert "-f dim2_flag=--replicate-batches" in guide
    assert "dev0,val0,val1" in guide
    assert "-f dim1_flag=--cells" in guide
    assert "c_p8_n100,c_p30_n100,c_p100_n100,c_p100_n300,c_p100_n1000,k5_p30_n150,k10_p100_n200,mix_p100_n200" in guide
    assert "--workers 1" in guide
    assert "--phase development" in guide
    assert "--phase validation" in guide
    assert "--provenance" in guide
    assert "development_selection.json" in guide
    assert "python scripts/cin_gate_check.py" in guide
    assert "validation once" in guide
    assert "12 aggregate runner-hours" in guide


def test_sharded_workflow_exposes_src_package_path() -> None:
    workflow = (ROOT / ".github" / "workflows" / "sharded_benchmark.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count('export PYTHONPATH="$GITHUB_WORKSPACE/src"') == 1
    assert workflow.count(
        'export PYTHONPATH="$GITHUB_WORKSPACE/src:$GITHUB_WORKSPACE"'
    ) == 1


def test_sharded_workflow_enforces_f_followup_v2_preflight() -> None:
    workflow = (ROOT / ".github" / "workflows" / "sharded_benchmark.yml").read_text(
        encoding="utf-8"
    )

    assert "cin-followup-f-v2" in workflow
    assert "scripts/cin_followup_f_gate_check.py" in workflow
    assert "requirements-cin-followup-v1.txt" in workflow
    assert '"$AGGREGATION_PHASE" == "validation"' in workflow
    assert '"$DIM2_VALUES" != "val0,val1"' in workflow
    assert "cin-followup-f-v2-aggregate" in workflow


def test_aggregate_workflow_environment_can_import_sidecar_aggregator(tmp_path: Path) -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "sharded_benchmark.yml").read_text(
            encoding="utf-8"
        )
    )
    aggregate_run = next(
        step["run"]
        for step in workflow["jobs"]["aggregate"]["steps"]
        if "scripts/aggregate_shards.py" in step.get("run", "")
    )
    path_assignment = next(
        line.strip()
        for line in aggregate_run.splitlines()
        if line.strip().startswith("export PYTHONPATH=")
    )
    path_template = path_assignment.split("=", 1)[1].strip().strip('"')
    import_paths = [
        Path(part.replace("$GITHUB_WORKSPACE", str(ROOT)))
        for part in path_template.split(":")
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in import_paths)

    result = subprocess.run(
        [sys.executable, "-c", "import scripts.aggregate_cin_sidecars"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
