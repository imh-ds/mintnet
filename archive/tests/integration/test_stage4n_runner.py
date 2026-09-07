import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1l import TRUE_EDGES
from mintnet.experiments.stage4n import OPPOSITE_NODES, _pair_label, load_stage4n_config, run_stage4n


def test_stage4n_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4n_config(Path("configs/stage4n_cascading_error_overlap_smoke.yaml"))

    first = run_stage4n(config, tmp_path / "first")
    second = run_stage4n(config, tmp_path / "second")

    expected_rows = len(config.sample_sizes) * len(config.noise_counts) * config.replicates * len(config.alphas)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_opposite_nodes_covers_every_true_edge() -> None:
    assert set(OPPOSITE_NODES) == set(TRUE_EDGES)
    for (i, j), opposite in OPPOSITE_NODES.items():
        assert i not in opposite and j not in opposite
        assert set(opposite) & {0, 1, 2, 3, 4} == set(opposite)  # real nodes only


def test_stage4n_overlap_draw_is_identical_across_noise_conditions(tmp_path: Path) -> None:
    """The paired-comparison design requires the overlap draw to be
    bit-identical whether noise_count is 0 or 5. Verified indirectly: for
    a direct edge whose sequential decision never used a noise column as
    a tested neighbor, sequential_retained should match the noise-free
    control exactly."""
    config = load_stage4n_config(Path("configs/stage4n_cascading_error_overlap_smoke.yaml"))
    raw = run_stage4n(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    control = ok.loc[ok["noise_count"] == 0].set_index("replicate")
    for i, j in TRUE_EDGES:
        label = _pair_label(i, j)
        uncontaminated = ok.loc[
            (ok["noise_count"] == 5) & (~ok[f"sequential_noise_neighbor_used_{label}"].astype(bool))
        ]
        for _, row in uncontaminated.iterrows():
            assert row[f"sequential_retained_{label}"] == control.loc[row["replicate"], f"sequential_retained_{label}"]


def test_stage4n_metrics_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4n_config(Path("configs/stage4n_cascading_error_overlap_smoke.yaml"))
    raw = run_stage4n(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for i, j in TRUE_EDGES:
        label = _pair_label(i, j)
        assert ok[f"sequential_retained_{label}"].isin([True, False]).all()
        assert ok[f"conservative_retained_{label}"].isin([True, False]).all()
        assert not ok.loc[ok["noise_count"] == 0, f"sequential_noise_neighbor_used_{label}"].astype(bool).any()


def test_stage4n_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4n_config((repository_root / "configs/stage4n_cascading_error_overlap_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4n_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4n(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
