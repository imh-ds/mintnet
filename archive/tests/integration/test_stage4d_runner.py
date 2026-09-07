import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage4b import SHAPES
from mintnet.experiments.stage4d import BOOKEND_N, load_stage4d_config, run_stage4d


def _bookend_csv(tmp_path: Path) -> Path:
    """Hand-crafted synthetic bookend, per test_stage1i_runner.py's own
    precedent -- never depend on the real, git-ignored results/generated/
    files existing on disk."""
    rows = []
    for shape in SHAPES:
        for alpha in (0.05, 0.15):
            for replicate in range(4):
                rows.append(
                    {
                        "shape": shape,
                        "n": BOOKEND_N,
                        "alpha": alpha,
                        "replicate": replicate,
                        "seed": 1,
                        "indirect_prune_tpr": 0.9,
                        "true_edge_prune_fpr": 0.0,
                        "conditionally_tested_pairs": 1,
                        "confirmed_pairs": 2,
                        "elapsed_seconds": 0.0001,
                        "status": "ok",
                        "error": "",
                    }
                )
    path = tmp_path / "bookend_raw_metrics.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_stage4d_smoke_runner_is_deterministic(tmp_path: Path) -> None:
    config = load_stage4d_config(Path("configs/stage4d_floor_search_smoke.yaml"))
    bookend = _bookend_csv(tmp_path)

    first = run_stage4d(config, bookend, tmp_path / "first")
    second = run_stage4d(config, bookend, tmp_path / "second")

    expected_new_rows = len(SHAPES) * len(config.sample_sizes) * len(config.alphas) * config.replicates
    expected_bookend_rows = len(SHAPES) * 2 * 4  # 2 alphas x 4 replicates, from the fixture
    assert len(first) == expected_new_rows + expected_bookend_rows
    pd.testing.assert_frame_equal(
        first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds")
    )
    for output in (tmp_path / "first", tmp_path / "second"):
        for filename in ("raw_metrics.csv", "resolved_config.yaml", "metadata.json"):
            assert (output / filename).is_file()


def test_stage4d_never_resimulates_the_bookend_n(tmp_path: Path) -> None:
    config = load_stage4d_config(Path("configs/stage4d_floor_search_smoke.yaml"))
    bookend = _bookend_csv(tmp_path)

    raw = run_stage4d(config, bookend, tmp_path / "evidence")

    bookend_rows = raw.loc[raw["n"] == BOOKEND_N]
    # Every bookend row must be exactly one of the fixture's hand-set values,
    # not a freshly simulated one (which would have status derived from a
    # real DGP run and a different tpr/fpr distribution).
    assert (bookend_rows["indirect_prune_tpr"] == 0.9).all()
    assert (bookend_rows["true_edge_prune_fpr"] == 0.0).all()


def test_stage4d_provenance_records_bookend_hash(tmp_path: Path, monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    config = load_stage4d_config((repository_root / "configs/stage4d_floor_search_smoke.yaml").resolve())
    bookend = _bookend_csv(tmp_path)
    output = (tmp_path / "evidence").resolve()
    expected_hash = hashlib.sha256((repository_root / "docs/stage4d_charter.md").read_bytes()).hexdigest()
    expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository_root, text=True).strip()
    expected_bookend_hash = hashlib.sha256(bookend.read_bytes()).hexdigest()

    monkeypatch.chdir(tmp_path)
    run_stage4d(config, bookend, output)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["charter_sha256"] == expected_hash
    assert metadata["git_commit"] == expected_commit
    assert metadata["bookend_raw_evidence_sha256"] == expected_bookend_hash
