import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4k import MOTIFS, load_stage4k_config, run_stage4k


def test_stage4k_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4k_config(Path("configs/stage4k_shape_strength_sweep_smoke.yaml"))

    first = run_stage4k(config, tmp_path / "first")
    second = run_stage4k(config, tmp_path / "second")

    expected_rows = len(MOTIFS) * len(config.strengths) * len(config.sample_sizes) * config.replicates
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "d012_formula.json"):
            assert (output / filename).is_file()


def test_stage4k_covers_every_motif_strength_n_combination(tmp_path: Path) -> None:
    config = load_stage4k_config(Path("configs/stage4k_shape_strength_sweep.yaml"))
    config = config.__class__(
        strengths=(0.3, 0.5),
        sample_sizes=(750, 1500),
        replicates=4,
        master_seed=config.master_seed,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_conditional_accuracy=config.minimum_conditional_accuracy,
        maximum_true_edge_prune_fpr=config.maximum_true_edge_prune_fpr,
        required_margin=config.required_margin,
    )

    raw = run_stage4k(config, tmp_path / "evidence")

    combos = set(zip(raw["motif"], raw["strength"], raw["n"]))
    expected = {(m, s, n) for m in MOTIFS for s in config.strengths for n in config.sample_sizes}
    assert combos == expected


def test_stage4k_uses_the_same_alpha_across_motifs_and_strengths_at_a_given_n(tmp_path: Path) -> None:
    config = load_stage4k_config(Path("configs/stage4k_shape_strength_sweep_smoke.yaml"))

    raw = run_stage4k(config, tmp_path / "evidence")

    for n in config.sample_sizes:
        assert raw.loc[raw["n"] == n, "alpha"].nunique() == 1


def test_stage4k_true_edge_columns_and_candidacy_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4k_config(Path("configs/stage4k_shape_strength_sweep_smoke.yaml"))

    raw = run_stage4k(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    assert (ok["true_edge_prune_fpr"] >= 0.0).all() and (ok["true_edge_prune_fpr"] <= 1.0).all()
    assert ok["candidate"].isin([True, False]).all()
    candidate = ok["candidate"].astype(bool)
    assert (ok.loc[candidate, "correctly_pruned"].isin([True, False])).all()
    assert ok.loc[~candidate, "correctly_pruned"].isna().all()


def test_stage4k_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4k_config((repository_root / "configs/stage4k_shape_strength_sweep_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4k_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4k(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
