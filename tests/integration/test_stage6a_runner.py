from pathlib import Path

import pandas as pd

from mintnet.experiments.stage6a import (
    COMPOSED_SHAPES,
    ISOLATION_SHAPES,
    METHODS,
    load_stage6a_config,
    run_stage6a,
)


def test_stage6a_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage6a_config(Path("configs/stage6a_conditioning_architecture_smoke.yaml"))

    first = run_stage6a(config, tmp_path / "first", max_workers=1)
    second = run_stage6a(config, tmp_path / "second", max_workers=1)

    expected_rows = (
        len(ISOLATION_SHAPES) * len(config.isolation_sample_sizes)
        + len(COMPOSED_SHAPES) * len(config.composed_sample_sizes)
    ) * config.replicates * len(METHODS)
    assert len(first) == expected_rows
    pd.testing.assert_frame_equal(first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds"))
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "conditioning_sizes.csv", "resolved_config.yaml", "metadata.json", "stage6a_report.md"):
            assert (output / filename).is_file()


def test_stage6a_covers_every_tier_shape_n_method_combination(tmp_path: Path) -> None:
    config = load_stage6a_config(Path("configs/stage6a_conditioning_architecture_smoke.yaml"))

    raw = run_stage6a(config, tmp_path / "evidence", max_workers=1)

    isolation = raw.loc[raw["tier"] == "isolation"]
    composed = raw.loc[raw["tier"] == "composed"]
    assert set(zip(isolation["shape"], isolation["n"], isolation["method"])) == {
        (s, n, m) for s in ISOLATION_SHAPES for n in config.isolation_sample_sizes for m in METHODS
    }
    assert set(zip(composed["shape"], composed["n"], composed["method"])) == {
        (s, n, m) for s in COMPOSED_SHAPES for n in config.composed_sample_sizes for m in METHODS
    }


def test_stage6a_triangle_shapes_never_exceed_conditioning_size_one(tmp_path: Path) -> None:
    """A 3-node component has only one other member -- growing-subset
    search can never test a larger conditioning set there, and must
    exactly reproduce full-component DPI's own numbers."""
    config = load_stage6a_config(Path("configs/stage6a_conditioning_architecture_smoke.yaml"))

    run_stage6a(config, tmp_path / "evidence", max_workers=1)
    sizes = pd.read_csv(tmp_path / "evidence" / "conditioning_sizes.csv")

    triangle_sizes = sizes.loc[sizes["shape"].str.startswith("triangle_")]
    assert (triangle_sizes["conditioning_size"] <= 1).all()


def test_stage6a_both_methods_see_identical_underlying_draw(tmp_path: Path) -> None:
    config = load_stage6a_config(Path("configs/stage6a_conditioning_architecture_smoke.yaml"))

    raw = run_stage6a(config, tmp_path / "evidence", max_workers=1)

    for tier, shapes, ns in (
        ("isolation", ISOLATION_SHAPES, config.isolation_sample_sizes),
        ("composed", COMPOSED_SHAPES, config.composed_sample_sizes),
    ):
        for shape in shapes:
            for n in ns:
                cell = raw.loc[(raw["tier"] == tier) & (raw["shape"] == shape) & (raw["n"] == n)]
                seeds_by_method = cell.groupby("method")["seed"].apply(lambda s: tuple(sorted(s)))
                assert seeds_by_method.nunique() == 1
