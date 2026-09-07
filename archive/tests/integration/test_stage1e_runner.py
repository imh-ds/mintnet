import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1e import load_stage1e_config, run_stage1e


def test_stage1e_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    """Changing Stage 1e seed derivation must change neither raw evidence run."""
    config = load_stage1e_config(Path("configs/stage1e_dpi_smoke.yaml"))

    first = run_stage1e(config, tmp_path / "first")
    second = run_stage1e(config, tmp_path / "second")

    assert len(first) == 3 * 2 * 1 * 4 * len(config.alphas)
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in (
            "raw_metrics.csv",
            "resolved_config.yaml",
            "metadata.json",
        ):
            assert (output / filename).is_file()


def test_stage1e_reuses_stage1c_seeds_for_previously_tested_replicates(tmp_path: Path) -> None:
    """Extending the replicate count must not perturb seeds already used by R2c/R2d."""
    from mintnet.experiments.stage1c import load_stage1c_config, run_stage1c

    stage1c_config = load_stage1c_config(Path("configs/stage1c_dpi_smoke.yaml"))
    stage1e_config = load_stage1e_config(Path("configs/stage1e_dpi_smoke.yaml"))

    stage1c_raw = run_stage1c(stage1c_config, tmp_path / "stage1c")
    stage1e_raw = run_stage1e(stage1e_config, tmp_path / "stage1e")

    stage1c_seeds = stage1c_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ]
    stage1e_seeds = stage1e_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ]
    shared_replicates = stage1e_seeds.loc[
        stage1e_seeds["replicate"].isin(stage1c_seeds["replicate"])
    ].reset_index(drop=True)
    matching_stage1c = stage1c_seeds.reset_index(drop=True)
    pd.testing.assert_frame_equal(shared_replicates, matching_stage1c)


def test_stage1e_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    """Launching elsewhere must preserve the charter hash and repository commit."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1e_config((repository_root / "configs/stage1e_dpi_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1e_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1e(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
