import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1j import load_stage1j_config, run_stage1j
from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form


def test_stage1j_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    """Changing Stage 1j seed derivation must change neither raw evidence run."""
    config = load_stage1j_config(Path("configs/stage1j_dpi_smoke.yaml"))

    first = run_stage1j(config, tmp_path / "first")
    second = run_stage1j(config, tmp_path / "second")

    assert len(first) == 3 * 1 * 1 * 4
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage1j_uses_the_single_formula_predicted_alpha_not_a_grid(tmp_path: Path) -> None:
    config = load_stage1j_config(Path("configs/stage1j_dpi_smoke.yaml"))
    n = config.sample_sizes[0]
    expected_alpha = select_form(fit_candidate_forms()).predict(float(n))

    raw = run_stage1j(config, tmp_path / "evidence")

    assert set(raw["alpha"].unique()) == {expected_alpha}
    assert len(raw["alpha"].unique()) == 1


def test_stage1j_provenance_uses_config_repository_when_cwd_changes(
    tmp_path: Path, monkeypatch
) -> None:
    """Launching elsewhere must preserve the charter hash and repository commit."""
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage1j_config((repository_root / "configs/stage1j_dpi_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256(
        (repository_root / "docs/stage1j_charter.md").read_bytes()
    ).hexdigest()
    expected_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, text=True
    ).strip()

    monkeypatch.chdir(tmp_path)
    run_stage1j(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
