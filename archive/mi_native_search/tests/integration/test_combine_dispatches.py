import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

sys.path.insert(0, "scripts")
from combine_dispatches import combine  # noqa: E402

from mintnet.experiments.stage7_isolation_timing import expected_combinations, expected_row_count, run_stage7_timing


def _write_config(path: Path, *, master_seed: int, replicates: int = 2) -> None:
    values = {
        "motifs": ["triad_balanced", "hub"],
        "sample_sizes": [150, 300],
        "replicates": replicates,
        "alpha": 0.05,
        "k_cmi": 10,
        "k_perm": 3,
        "permutations": 19,
        "master_seed": master_seed,
    }
    path.write_text(yaml.safe_dump(values), encoding="utf-8")


def test_combine_two_dispatches_remaps_replicates_and_covers_full_range(tmp_path: Path) -> None:
    from mintnet.experiments.stage7_isolation_timing import load_config

    config_a_path = tmp_path / "dispatch_a.yaml"
    config_b_path = tmp_path / "dispatch_b.yaml"
    _write_config(config_a_path, master_seed=1001)
    _write_config(config_b_path, master_seed=1002)

    dispatch_a_dir = tmp_path / "dispatch_a_artifacts"
    dispatch_b_dir = tmp_path / "dispatch_b_artifacts"
    run_stage7_timing(load_config(config_a_path), dispatch_a_dir)
    run_stage7_timing(load_config(config_b_path), dispatch_b_dir)

    combined_dir = tmp_path / "combined"
    combined = combine(
        "mintnet.experiments.stage7_isolation_timing",
        [config_a_path, config_b_path],
        [dispatch_a_dir, dispatch_b_dir],
        combined_dir,
    )

    # dispatch A's local replicates {0,1} -> global {0,1}; dispatch B's {0,1} -> global {2,3}
    assert set(combined["replicate"].unique()) == {0, 1, 2, 3}
    assert len(combined) == 2 * expected_row_count(load_config(config_a_path))
    assert (combined_dir / "raw_metrics.csv").is_file()
    assert (combined_dir / "combined_manifest.json").is_file()
    assert (combined_dir / "timing_report.md").is_file()

    manifest_combos = set(zip(combined["motif"], combined["n"], combined["replicate"]))
    # combined config has replicates=4; check full coverage via the module's own contract
    from dataclasses import replace

    combined_config = replace(load_config(config_a_path), replicates=4)
    assert manifest_combos == expected_combinations(combined_config)


def test_combine_refuses_dispatches_with_different_design(tmp_path: Path) -> None:
    from mintnet.experiments.stage7_isolation_timing import load_config

    config_a_path = tmp_path / "dispatch_a.yaml"
    config_b_path = tmp_path / "dispatch_b.yaml"
    _write_config(config_a_path, master_seed=2001)
    # different alpha -- a genuine design mismatch, not just a different seed/replicate count
    _write_config(config_b_path, master_seed=2002)
    b_values = yaml.safe_load(config_b_path.read_text())
    b_values["alpha"] = 0.01
    config_b_path.write_text(yaml.safe_dump(b_values), encoding="utf-8")

    dispatch_a_dir = tmp_path / "dispatch_a_artifacts"
    dispatch_b_dir = tmp_path / "dispatch_b_artifacts"
    run_stage7_timing(load_config(config_a_path), dispatch_a_dir)
    run_stage7_timing(load_config(config_b_path), dispatch_b_dir)

    with pytest.raises(SystemExit, match="disagree on field 'alpha'"):
        combine(
            "mintnet.experiments.stage7_isolation_timing",
            [config_a_path, config_b_path],
            [dispatch_a_dir, dispatch_b_dir],
            tmp_path / "combined",
        )


def test_combine_refuses_an_incomplete_dispatch(tmp_path: Path) -> None:
    from mintnet.experiments.stage7_isolation_timing import load_config

    config_a_path = tmp_path / "dispatch_a.yaml"
    _write_config(config_a_path, master_seed=3001)

    dispatch_a_dir = tmp_path / "dispatch_a_artifacts"
    raw = run_stage7_timing(load_config(config_a_path), dispatch_a_dir)
    # simulate a truncated/incomplete artifact (one row missing)
    raw.iloc[:-1].to_csv(dispatch_a_dir / "raw_metrics.csv", index=False)

    with pytest.raises(SystemExit, match="incomplete"):
        combine(
            "mintnet.experiments.stage7_isolation_timing",
            [config_a_path],
            [dispatch_a_dir],
            tmp_path / "combined",
        )
