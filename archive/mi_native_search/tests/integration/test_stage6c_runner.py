from pathlib import Path

import yaml

from mintnet.experiments.stage6c import (
    ALT_CONDITIONS,
    NULL_CONDITIONS,
    StageAConfig,
    StageBConfig,
    StageCConfig,
    run_stage_a,
    run_stage_b,
    run_stage_c,
)
from mintnet.experiments.stage6c_reporting import write_stage_a_report, write_stage_b_report, write_stage_c_report

_SMOKE_CONFIG = Path("configs/stage6c_null_calibration_smoke.yaml")


def _load(block: str) -> dict:
    with _SMOKE_CONFIG.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)[block]


def test_stage_a_smoke_runner(tmp_path: Path) -> None:
    block = _load("stage_a")
    config = StageAConfig(
        k_cmi_values=tuple(block["k_cmi_values"]),
        sample_sizes=tuple(block["sample_sizes"]),
        replicates=block["replicates"],
        master_seed=block["master_seed"],
    )
    raw = run_stage_a(config, tmp_path, max_workers=1)
    assert len(raw) == len(config.k_cmi_values) * len(NULL_CONDITIONS) * len(config.sample_sizes) * config.replicates
    assert (raw["status"] == "ok").all()
    write_stage_a_report(raw, config, tmp_path)
    assert (tmp_path / "stage_a_report.md").is_file()


def test_stage_b_smoke_runner_defensibility_columns(tmp_path: Path) -> None:
    block = _load("stage_b")
    config = StageBConfig(
        k_cmi=block["k_cmi"],
        k_perm_labels=tuple(block["k_perm_labels"]),
        sample_sizes=tuple(block["sample_sizes"]),
        replicates=block["replicates"],
        permutations=block["permutations"],
        alphas=tuple(block["alphas"]),
        master_seed=block["master_seed"],
    )
    raw = run_stage_b(config, tmp_path, max_workers=1)
    assert (raw["status"] == "ok").all()
    # |S|=0 cells only ever use kperm5 (global permutation, k_perm irrelevant)
    s0_labels = raw.loc[raw["s"] == 0, "k_perm_label"].unique()
    assert set(s0_labels) == {"kperm5"}
    cells = write_stage_b_report(raw, config, tmp_path)
    assert (tmp_path / "stage_b_verdict.json").is_file()
    assert all(0.0 <= c.rate <= 1.0 for c in cells)


def test_stage_c_smoke_runner(tmp_path: Path) -> None:
    block = _load("stage_c")
    config = StageCConfig(
        k_cmi=block["k_cmi"],
        k_perm_label=block["k_perm_label"],
        sample_sizes=tuple(block["sample_sizes"]),
        replicates=block["replicates"],
        permutations=block["permutations"],
        alphas=tuple(block["alphas"]),
        master_seed=block["master_seed"],
    )
    raw = run_stage_c(config, tmp_path, max_workers=1)
    assert len(raw) == len(ALT_CONDITIONS) * len(config.sample_sizes) * config.replicates
    assert (raw["status"] == "ok").all()
    write_stage_c_report(raw, config, tmp_path)
    assert (tmp_path / "stage_c_report.md").is_file()
