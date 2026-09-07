import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4q_a import load_stage4q_a_config, run_stage4q_a


def test_stage4q_a_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4q_a_config(Path("configs/stage4q_a_higher_n_smoke.yaml"))

    first = run_stage4q_a(config, tmp_path / "first")
    second = run_stage4q_a(config, tmp_path / "second")

    expected_rows = len(config.sample_sizes) * config.replicates
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4q_a_uses_a_single_predicted_alpha_per_n(tmp_path: Path) -> None:
    config = load_stage4q_a_config(Path("configs/stage4q_a_higher_n_smoke.yaml"))

    raw = run_stage4q_a(config, tmp_path / "evidence")

    for n in config.sample_sizes:
        assert raw.loc[raw["n"] == n, "alpha"].nunique() == 1


def test_stage4q_a_metrics_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4q_a_config(Path("configs/stage4q_a_higher_n_smoke.yaml"))

    raw = run_stage4q_a(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for col in ("chain_indirect_tpr", "fork_indirect_tpr", "overlap_indirect_tpr", "true_edge_prune_fpr"):
        assert (ok[col] >= 0.0).all() and (ok[col] <= 1.0).all()


def test_stage4q_a_seeds_are_new_never_used_in_stage4p(tmp_path: Path) -> None:
    """Part A tests N values (1750, 2000) never simulated before at this
    p; its own stream tag must not collide with Stage 4p's own dgp_index
    tags (0=overlap, 1=hub)."""
    from mintnet.experiments.stage4q_a import _STREAM

    assert _STREAM not in (0, 1)


def test_stage4q_a_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4q_a_config((repository_root / "configs/stage4q_a_higher_n_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4q_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4q_a(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
