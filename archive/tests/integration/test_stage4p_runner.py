import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4p import DGPS, ENGINES, load_stage4p_config, run_stage4p


def test_stage4p_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4p_config(Path("configs/stage4p_canonical_benchmark_smoke.yaml"))

    first = run_stage4p(config, tmp_path / "first")
    second = run_stage4p(config, tmp_path / "second")

    expected_rows = len(DGPS) * len(config.sample_sizes) * config.replicates * len(ENGINES)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4p_covers_every_dgp_n_engine_combination(tmp_path: Path) -> None:
    config = load_stage4p_config(Path("configs/stage4p_canonical_benchmark.yaml"))
    config = config.__class__(
        sample_sizes=(400, 750),
        strength=config.strength,
        screening_alpha=config.screening_alpha,
        replicates=4,
        master_seed=config.master_seed,
        development_replicates=(0, 1),
        validation_replicates=(2, 3),
        minimum_indirect_prune_tpr=config.minimum_indirect_prune_tpr,
        maximum_true_edge_prune_fpr=config.maximum_true_edge_prune_fpr,
        false_edge_rate_tolerance=config.false_edge_rate_tolerance,
    )

    raw = run_stage4p(config, tmp_path / "evidence")

    combos = set(zip(raw["dgp"], raw["n"], raw["engine"]))
    expected = {(d, n, e) for d in DGPS for n in config.sample_sizes for e in ENGINES}
    assert combos == expected


def test_stage4p_both_engines_use_same_alpha_and_same_underlying_draw(tmp_path: Path) -> None:
    """Paired same-draw design: both engines must see identical alpha
    (same D-012 formula) and, since the DGP draw only depends on seed
    (shared across engines), identical underlying data at each
    (dgp, N, replicate)."""
    config = load_stage4p_config(Path("configs/stage4p_canonical_benchmark_smoke.yaml"))

    raw = run_stage4p(config, tmp_path / "evidence")

    for dgp in DGPS:
        for n in config.sample_sizes:
            cell = raw.loc[(raw["dgp"] == dgp) & (raw["n"] == n)]
            assert cell["alpha"].nunique() == 1
            seeds_by_engine = cell.groupby("engine")["seed"].apply(lambda s: tuple(sorted(s)))
            assert seeds_by_engine.nunique() == 1  # same seed set for both engines


def test_stage4p_metrics_are_well_formed(tmp_path: Path) -> None:
    config = load_stage4p_config(Path("configs/stage4p_canonical_benchmark_smoke.yaml"))

    raw = run_stage4p(config, tmp_path / "evidence")

    ok = raw.loc[raw["status"] == "ok"]
    assert not ok.empty
    for col in ("chain_indirect_tpr", "fork_indirect_tpr", "third_indirect_tpr", "true_edge_prune_fpr"):
        assert (ok[col] >= 0.0).all() and (ok[col] <= 1.0).all()
    assert (ok["final_false_edge_rate"] <= ok["screening_false_edge_rate"] + 1e-9).all()


def test_stage4p_provenance_records_charter_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4p_config((repository_root / "configs/stage4p_canonical_benchmark_smoke.yaml").resolve())
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4p_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()

    monkeypatch.chdir(tmp_path)
    run_stage4p(config, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
