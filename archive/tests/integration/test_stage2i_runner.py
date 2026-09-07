import hashlib
import json
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage2i import BOOKEND_N, load_stage2i_config, run_stage2i


def _bookend_csv(tmp_path: Path) -> Path:
    """A tiny hand-crafted stand-in for Stage 2h's raw evidence with
    N=750/1500/other -- exercises the merge without depending on the real
    (git-ignored) generated evidence existing on disk."""
    columns = [
        "n", "replicate", "seed", "dpi_alpha", "chain_indirect_tpr", "fork_indirect_tpr",
        "overlap_indirect_tpr", "true_edge_prune_fpr", "screening_false_edge_rate",
        "final_false_edge_rate", "chain_is_triad", "fork_is_triad", "overlap_is_validated",
        "overlap_clean_clique", "elapsed_seconds", "status", "error",
    ]
    rows = []
    for n in (750, BOOKEND_N, 3000):  # 750 and 3000 must be dropped by the merge
        for replicate in (0, 1, 2, 3):  # covers the smoke config's dev [0,1] and val [2,3]
            rows.append(
                dict(
                    zip(
                        columns,
                        [
                            n, replicate, 1, 0.11, 0.85, 0.86, 0.76, 0.0, 0.0001, 0.0001,
                            1.0, 1.0, 1.0, 1.0, 0.001, "ok", "",
                        ],
                    )
                )
            )
    frame = pd.DataFrame(rows)
    path = tmp_path / "bookend_raw_metrics.csv"
    frame.to_csv(path, index=False)
    return path


def test_stage2i_merges_only_the_1500_bookend_from_the_source(tmp_path: Path) -> None:
    bookend_path = _bookend_csv(tmp_path)
    config = load_stage2i_config(Path("configs/stage2i_overlap_floor_p30_smoke.yaml"))

    raw = run_stage2i(config, bookend_path, tmp_path / "evidence")

    assert set(raw["n"].unique()) == {1600, BOOKEND_N}
    # 750 and 3000 from the bookend source must not leak in.
    assert 750 not in raw["n"].values
    assert 3000 not in raw["n"].values


def test_stage2i_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    bookend_path = _bookend_csv(tmp_path)
    config = load_stage2i_config(Path("configs/stage2i_overlap_floor_p30_smoke.yaml"))

    first = run_stage2i(config, bookend_path, tmp_path / "first")
    second = run_stage2i(config, bookend_path, tmp_path / "second")

    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds").sort_values(["n", "replicate"]).reset_index(drop=True),
        second.drop(columns="elapsed_seconds").sort_values(["n", "replicate"]).reset_index(drop=True),
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json", "stage2i_report.md"):
            assert (output / filename).is_file()


def test_stage2i_records_bookend_provenance(tmp_path: Path) -> None:
    bookend_path = _bookend_csv(tmp_path)
    config = load_stage2i_config(Path("configs/stage2i_overlap_floor_p30_smoke.yaml"))
    output = tmp_path / "evidence"

    run_stage2i(config, bookend_path, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["bookend_raw_evidence_path"] == str(bookend_path)
    assert metadata["bookend_raw_evidence_sha256"] == hashlib.sha256(bookend_path.read_bytes()).hexdigest()
