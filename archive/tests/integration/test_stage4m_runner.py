import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4m import MOTIFS, _DIRECT_EDGES, _pair_label, load_stage4m_config, run_stage4m


def test_stage4m_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4m_config(Path("configs/stage4m_cascading_error_chain_fork_hub_smoke.yaml"))

    first = run_stage4m(config, tmp_path / "first")
    second = run_stage4m(config, tmp_path / "second")

    expected_rows = (
        len(MOTIFS) * len(config.sample_sizes) * len(config.noise_counts) * config.replicates * len(config.alphas)
    )
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4m_motif_draw_is_identical_across_noise_conditions(tmp_path: Path) -> None:
    """The paired-comparison design requires the motif draw to be
    bit-identical whether noise_count is 0 or 5. Verified indirectly: for
    a direct edge whose sequential decision never used a noise column as
    a tested neighbor, sequential_retained should match the noise-free
    control exactly."""
    config = load_stage4m_config(Path("configs/stage4m_cascading_error_chain_fork_hub_smoke.yaml"))
    raw = run_stage4m(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    for motif in MOTIFS:
        motif_ok = ok.loc[ok["motif"] == motif]
        control = motif_ok.loc[motif_ok["noise_count"] == 0].set_index("replicate")
        for i, j in _DIRECT_EDGES[motif]:
            label = _pair_label(i, j)
            uncontaminated = motif_ok.loc[
                (motif_ok["noise_count"] == 5) & (~motif_ok[f"sequential_noise_neighbor_used_{label}"].astype(bool))
            ]
            for _, row in uncontaminated.iterrows():
                assert row[f"sequential_retained_{label}"] == control.loc[row["replicate"], f"sequential_retained_{label}"]


def test_stage4m_metrics_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4m_config(Path("configs/stage4m_cascading_error_chain_fork_hub_smoke.yaml"))
    raw = run_stage4m(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for motif in MOTIFS:
        motif_ok = ok.loc[ok["motif"] == motif]
        for i, j in _DIRECT_EDGES[motif]:
            label = _pair_label(i, j)
            assert motif_ok[f"sequential_retained_{label}"].isin([True, False]).all()
            assert motif_ok[f"conservative_retained_{label}"].isin([True, False]).all()
            assert not motif_ok.loc[
                motif_ok["noise_count"] == 0, f"sequential_noise_neighbor_used_{label}"
            ].astype(bool).any()


def test_stage4m_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4m_config((repository_root / "configs/stage4m_cascading_error_chain_fork_hub_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4m_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4m(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
