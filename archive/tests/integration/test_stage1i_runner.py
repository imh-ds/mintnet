import hashlib
import json
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1i import load_stage1i_config, run_stage1i


def _bookend_csv(tmp_path: Path) -> Path:
    """A tiny hand-crafted stand-in for R2h's raw evidence with N=500/750/other."""
    rows = []
    for n in (100, 500, 750, 2000):  # 100 and 2000 must be dropped by the merge
        for alpha in (0.10, 0.14):
            rows.append(
                {
                    "motif": "chain",
                    "family": "gaussian",
                    "strength": 0.5,
                    "n": n,
                    "alpha": alpha,
                    "replicate": 0,
                    "seed": 1,
                    "retained_01": True,
                    "retained_02": False,
                    "retained_12": True,
                    "partial_r_01": 0.5,
                    "partial_r_02": 0.0,
                    "partial_r_12": 0.5,
                    "p_value_01": 0.001,
                    "p_value_02": 0.9,
                    "p_value_12": 0.001,
                    "confidence_01": 0.999,
                    "confidence_02": 0.1,
                    "confidence_12": 0.999,
                    "indirect_prune_tpr": 1.0,
                    "true_edge_prune_fpr": float("nan"),
                    "perfect_recovery": 1.0,
                    "elapsed_seconds": 0.001,
                    "status": "ok",
                    "error": "",
                }
            )
    frame = pd.DataFrame(rows)
    path = tmp_path / "bookend_raw_metrics.csv"
    frame.to_csv(path, index=False)
    return path


def test_stage1i_merges_only_n_500_and_750_from_the_bookend_source(tmp_path: Path) -> None:
    bookend_path = _bookend_csv(tmp_path)
    config = load_stage1i_config(Path("configs/stage1i_dpi_smoke.yaml"))

    raw = run_stage1i(config, bookend_path, tmp_path / "evidence")

    assert set(raw["n"].unique()) == {600, 500, 750}
    # 100 and 2000 from the bookend source must not leak in.
    assert 100 not in raw["n"].values
    assert 2000 not in raw["n"].values


def test_stage1i_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    bookend_path = _bookend_csv(tmp_path)
    config = load_stage1i_config(Path("configs/stage1i_dpi_smoke.yaml"))

    first = run_stage1i(config, bookend_path, tmp_path / "first")
    second = run_stage1i(config, bookend_path, tmp_path / "second")

    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds").sort_values(list(first.columns.drop("elapsed_seconds"))).reset_index(drop=True),
        second.drop(columns="elapsed_seconds").sort_values(list(second.columns.drop("elapsed_seconds"))).reset_index(drop=True),
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage1i_records_bookend_provenance(tmp_path: Path) -> None:
    bookend_path = _bookend_csv(tmp_path)
    config = load_stage1i_config(Path("configs/stage1i_dpi_smoke.yaml"))
    output = tmp_path / "evidence"

    run_stage1i(config, bookend_path, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["bookend_raw_evidence_path"] == str(bookend_path)
    assert metadata["bookend_raw_evidence_sha256"] == hashlib.sha256(bookend_path.read_bytes()).hexdigest()
