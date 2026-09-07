import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1c import load_stage1c_config, run_stage1c


def test_stage1c_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    """Changing Stage 1c seed derivation must change neither raw evidence run."""
    config = load_stage1c_config(Path("configs/stage1c_dpi_smoke.yaml"))

    first = run_stage1c(config, tmp_path / "first")
    second = run_stage1c(config, tmp_path / "second")

    assert len(first) == 3 * 2 * 1 * 2 * len(config.alphas)
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


def test_stage1c_reuses_stage1b_seeds_for_previously_tested_sample_sizes(tmp_path: Path) -> None:
    """Appending new N values must not perturb seeds at N already tested by R2b."""
    from mintnet.experiments.stage1b import load_stage1b_config, run_stage1b

    stage1b_config = load_stage1b_config(Path("configs/stage1b_dpi_smoke.yaml"))
    stage1c_config = load_stage1c_config(Path("configs/stage1c_dpi_smoke.yaml"))

    stage1b_raw = run_stage1b(stage1b_config, tmp_path / "stage1b")
    stage1c_raw = run_stage1c(stage1c_config, tmp_path / "stage1c")

    stage1b_seeds = stage1b_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ]
    stage1c_seeds = stage1c_raw.drop_duplicates(["motif", "n", "strength", "replicate"])[
        ["motif", "n", "strength", "replicate", "seed"]
    ]
    shared_n = stage1c_seeds.loc[stage1c_seeds["n"].isin(stage1b_seeds["n"])].reset_index(drop=True)
    matching_stage1b = stage1b_seeds.reset_index(drop=True)
    pd.testing.assert_frame_equal(shared_n, matching_stage1b)


def test_stage1c_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    """Launching elsewhere must preserve the charter hash and repository commit."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1c_config((repository_root / "configs/stage1c_dpi_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1c_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1c(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
