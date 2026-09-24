from __future__ import annotations

import numpy as np
import pandas as pd

from mintnet.cin.result import PAIR_COLUMNS, NetworkFit, compute_fit_id
from mintnet.cin.stability import (
    STABILITY_COLUMNS,
    StabilityResult,
    _repeat_seeds,
    _sample_indices,
    load_stability,
)


def _schema() -> dict[str, dict[str, str]]:
    return {
        "a": {"kind": "continuous"},
        "b": {"kind": "continuous"},
        "c": {"kind": "continuous"},
    }


def _fit() -> NetworkFit:
    schema = _schema()
    pair_rows = []
    for left, right, weight in (("a", "b", 0.2), ("a", "c", 0.1), ("b", "c", 0.05)):
        pair_rows.append(
            {
                "node_i": left,
                "node_j": right,
                "gain_i_to_j": weight,
                "gain_j_to_i": weight,
                "weight_nats_raw": weight,
                "display_magnitude_nats": weight,
                "gaussian_equivalent_magnitude": 0.4,
                "orientation_gap": 0.0,
                "n_scored": 80,
                "folds_complete": 3,
                "status": "complete",
                "diagnostic_flags": "",
            }
        )
    fit_id = compute_fit_id("config-hash", schema, "data-digest", "revision")
    return NetworkFit(
        pairs=pd.DataFrame(pair_rows, columns=PAIR_COLUMNS),
        nodes=pd.DataFrame([{"node": name} for name in schema]),
        folds=pd.DataFrame([{"fold": 0}]),
        metadata={
            "config_hash": "config-hash",
            "schema": schema,
            "digests": {
                "data_digest": "data-digest",
                "row_identity_digest": "row-digest",
            },
            "git_revision": "revision",
            "fit_id": fit_id,
            "config": {"seed": 17},
            "retained_count": 80,
            "runtime": {"elapsed_seconds": 0.1},
        },
    )


def _sample_stability_result() -> StabilityResult:
    fit = _fit()
    rows = []
    for repeat_id, repeat_seed in enumerate(_repeat_seeds(17, 2)):
        for record in fit.pairs.to_dict(orient="records"):
            rows.append(
                {
                    "fit_id": fit.metadata["fit_id"],
                    "repeat_id": repeat_id,
                    "repeat_seed": repeat_seed,
                    "node_i": record["node_i"],
                    "node_j": record["node_j"],
                    "gain_i_to_j": record["gain_i_to_j"],
                    "gain_j_to_i": record["gain_j_to_i"],
                    "weight_nats_raw": record["weight_nats_raw"],
                    "status": record["status"],
                }
            )
    metadata = {
        "fit_id": fit.metadata["fit_id"],
        "config_hash": fit.metadata["config_hash"],
        "digests": fit.metadata["digests"],
        "schema": fit.metadata["schema"],
        "seed": 17,
        "stability_tag": 0xC17,
        "repeats_requested": 2,
        "B": 2,
        "fraction": 0.8,
        "sample_size": 64,
        "repeat_seeds": list(_repeat_seeds(17, 2)),
        "completed_repeat_ids": [0, 1],
        "repeats_completed": 2,
        "status": "complete",
        "preflight": {
            "elapsed_estimate": 0.1,
            "estimated_seconds": 0.3,
            "max_seconds": 10.0,
        },
    }
    return StabilityResult(pd.DataFrame(rows, columns=STABILITY_COLUMNS), metadata)


def test_repeat_seeds_are_deterministic_and_fit_seed_sensitive() -> None:
    left = _repeat_seeds(17, 4)
    again = _repeat_seeds(17, 4)
    other = _repeat_seeds(18, 4)

    assert left == again
    assert left != other
    assert len(left) == 4
    assert len(set(left)) == 4


def test_sample_indices_are_sorted_unique_and_exact_size() -> None:
    indices = _sample_indices(80, 64, 17, 2)

    assert len(indices) == 64
    assert np.array_equal(indices, np.unique(indices))
    assert np.all(indices[:-1] < indices[1:])


def test_stability_result_round_trips_records_and_metadata(tmp_path) -> None:
    result = _sample_stability_result()

    result.save(tmp_path)
    restored = load_stability(tmp_path)

    pd.testing.assert_frame_equal(restored.records, result.records)
    assert restored.metadata == result.metadata
    assert restored.fit_id == result.fit_id
    assert (tmp_path / "stability_records.csv").exists()
    assert (tmp_path / "metadata.json").exists()


def test_stability_result_supports_compressed_records(tmp_path) -> None:
    result = _sample_stability_result()

    result.save(tmp_path, compressed=True)
    restored = load_stability(tmp_path)

    assert (tmp_path / "stability_records.csv.gz").exists()
    pd.testing.assert_frame_equal(restored.records, result.records)
