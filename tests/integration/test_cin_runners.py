from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from mintnet.experiments.cin_baseline import load_config as load_panel_config
from mintnet.experiments.cin_baseline import (
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
from scripts.aggregate_cin_sidecars import aggregate_sidecars
from mintnet.experiments.cin_common import (
    IncrementalCsvWriter,
    canonical_pair_sidecar_name,
    derive_seed_bundle,
    write_provenance,
    write_resolved_config,
)


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
    assert metadata["config_sha256"] == hashlib.sha256(config_path.read_bytes()).hexdigest()
    assert metadata["charter_sha256"] == hashlib.sha256(charter_path.read_bytes()).hexdigest()
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


def test_panel_method_matrix_and_full_phase_combinations() -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    assert PANEL_COMBINATION_COLUMNS == ("case", "phase", "method")
    assert methods_for_case("A") == ("cin", "cin_linear", "ebicglasso")
    assert methods_for_case("F") == ("cin",)
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
    assert (output / "raw_metrics.csv").exists()
    assert len(list((output / "sidecars").glob("*_pairs.csv.gz"))) == 16


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


def test_baseline_report_requires_promised_pair_sidecars(tmp_path: Path) -> None:
    config = load_panel_config(ROOT / "configs" / "cin_baseline_smoke.yaml")
    source = tmp_path / "panel"
    raw = run_baseline(config, source, write_report=False)
    sidecar = next((source / "sidecars").glob("*_pairs.csv.gz"))
    sidecar.unlink()
    with pytest.raises(FileNotFoundError, match="sidecar"):
        cin_baseline_reporting.write_report(raw, config, source)
