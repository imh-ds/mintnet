import hashlib
import json
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1d import load_stage1d_config, run_stage1d


def test_stage1d_reuses_source_raw_evidence_without_resimulating(tmp_path: Path) -> None:
    """R2d must reuse R2c's raw evidence verbatim, not regenerate it."""
    source = tmp_path / "source_raw_metrics.csv"
    frame = pd.DataFrame(
        {
            "motif": ["chain"],
            "family": ["gaussian"],
            "strength": [0.5],
            "n": [750],
            "alpha": [0.05],
            "replicate": [0],
            "seed": [1],
            "retained_01": [True],
            "retained_02": [False],
            "retained_12": [True],
            "partial_r_01": [0.5],
            "partial_r_02": [0.0],
            "partial_r_12": [0.5],
            "p_value_01": [0.001],
            "p_value_02": [0.9],
            "p_value_12": [0.001],
            "confidence_01": [0.999],
            "confidence_02": [0.1],
            "confidence_12": [0.999],
            "indirect_prune_tpr": [1.0],
            "true_edge_prune_fpr": [0.0],
            "perfect_recovery": [1.0],
            "elapsed_seconds": [0.001],
            "status": ["ok"],
            "error": [""],
        }
    )
    frame.to_csv(source, index=False)
    config = load_stage1d_config(Path("configs/stage1d_dpi.yaml"))
    output = tmp_path / "evidence"

    raw = run_stage1d(config, source, output)

    pd.testing.assert_frame_equal(raw, pd.read_csv(source))
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["source_raw_metrics_path"] == str(source)
    assert metadata["source_raw_metrics_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (output / "raw_metrics.csv").is_file()
