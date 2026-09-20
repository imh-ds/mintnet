import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "scripts")
from stage7e_alpha_refinement import refine  # noqa: E402

from mintnet.experiments.stage7e_isolation import load_config, run_stage7e_isolation

_SMOKE_CONFIG = Path("configs/stage7e_isolation_smoke.yaml")


def test_refine_reproduces_the_source_evidence_at_the_original_alphas(tmp_path: Path) -> None:
    """Re-thresholding at exactly the source config's own alphas must
    reproduce the same aggregate metrics the original run computed --
    the whole premise of this tool is that it adds no new information
    beyond re-deriving decisions from already-stored p-values."""
    config = load_config(_SMOKE_CONFIG)
    source_dir = tmp_path / "source"
    run_stage7e_isolation(config, source_dir, write_report=False)

    output_dir = tmp_path / "refined"
    aggregate, decision = refine(
        source_dir / "raw_metrics.csv", _SMOKE_CONFIG, tuple(config.alphas), output_dir
    )

    assert (output_dir / "refined_raw_metrics.csv").is_file()
    assert (output_dir / "refined_aggregate_metrics.csv").is_file()
    assert (output_dir / "refined_decision.json").is_file()
    assert set(aggregate["alpha"].unique()) == set(config.alphas)

    original_raw = pd.read_csv(source_dir / "raw_metrics.csv")
    original_aggregate = original_raw.groupby(
        ["motif", "strength", "n", "alpha"], as_index=False
    )["indirect_prune_tpr"].mean()
    refined_aggregate = aggregate.groupby(["motif", "strength", "n", "alpha"], as_index=False)[
        "indirect_prune_tpr"
    ].mean()
    merged = original_aggregate.merge(
        refined_aggregate, on=["motif", "strength", "n", "alpha"], suffixes=("_orig", "_refined")
    )
    assert (merged["indirect_prune_tpr_orig"] - merged["indirect_prune_tpr_refined"]).abs().max() < 1e-9


def test_refine_at_a_finer_grid_covers_every_requested_alpha(tmp_path: Path) -> None:
    config = load_config(_SMOKE_CONFIG)
    source_dir = tmp_path / "source"
    run_stage7e_isolation(config, source_dir, write_report=False)

    fine_alphas = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35)
    aggregate, decision = refine(
        source_dir / "raw_metrics.csv", _SMOKE_CONFIG, fine_alphas, tmp_path / "refined"
    )

    assert set(aggregate["alpha"].unique()) == set(fine_alphas)
    assert decision.status in ("PROCEED", "REASSESS")
