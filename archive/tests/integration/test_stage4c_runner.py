import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4c import load_stage4c_config, run_stage4c


def test_stage4c_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4c_config(Path("configs/stage4c_cascading_error_smoke.yaml"))

    first = run_stage4c(config, tmp_path / "first")
    second = run_stage4c(config, tmp_path / "second")

    expected_rows = len(config.sample_sizes) * len(config.noise_counts) * config.replicates * len(config.alphas)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4c_triangle_draw_is_identical_across_noise_conditions(tmp_path: Path) -> None:
    """The paired-comparison design requires the triangle draw to be
    bit-identical whether noise_count is 0 or 5 -- only the noise stream
    should differ. Verified indirectly: with alpha loose enough that the
    weak edge's candidacy never depends on noise, sequential_retained
    should match between noise=0 and noise=5 whenever no noise column was
    actually used as a tested neighbor."""
    config = load_stage4c_config(Path("configs/stage4c_cascading_error_smoke.yaml"))
    raw = run_stage4c(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    uncontaminated = ok.loc[(ok["noise_count"] == 5) & (~ok["sequential_noise_neighbor_used"].astype(bool))]
    control = ok.loc[ok["noise_count"] == 0].set_index("replicate")
    for _, row in uncontaminated.iterrows():
        # Same replicate, same triangle draw, no noise column touched the
        # weak-edge decision -- the sequential outcome must match the
        # noise-free control exactly.
        assert row["sequential_retained"] == control.loc[row["replicate"], "sequential_retained"]


def test_stage4c_metrics_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4c_config(Path("configs/stage4c_cascading_error_smoke.yaml"))
    raw = run_stage4c(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    assert ok["sequential_retained"].isin([True, False]).all()
    assert ok["conservative_retained"].isin([True, False]).all()
    # Noise columns never touch the weak-edge decision when noise_count=0.
    assert not ok.loc[ok["noise_count"] == 0, "sequential_noise_neighbor_used"].astype(bool).any()


def test_stage4c_provenance_uses_config_repository_when_cwd_changes(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4c_config((repository_root / "configs/stage4c_cascading_error_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4c_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4c(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
