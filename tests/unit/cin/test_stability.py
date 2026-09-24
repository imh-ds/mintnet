from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

import mintnet.cin.stability as stability
from mintnet.cin import fit_network
from mintnet.cin.config import CINConfig
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


def _fit_and_frame(n: int = 80) -> tuple[NetworkFit, pd.DataFrame, dict, CINConfig]:
    rows = np.arange(n, dtype=np.float64)
    frame = pd.DataFrame(
        {
            "a": np.sin(rows / 4.0) + rows / 100.0,
            "b": np.cos(rows / 5.0) - rows / 90.0,
            "c": (rows % 11.0) + rows / 80.0,
        }
    )
    schema = _schema()
    config = CINConfig(seed=17, lambda_grid=(0.1, 1.0), pair_batch_size=1)
    return fit_network(frame, schema, config), frame, schema, config


def _fake_repeat_fit(complete: bool = True) -> NetworkFit:
    fit = _fit()
    metadata = copy.deepcopy(fit.metadata)
    metadata["complete"] = complete
    metadata["runtime"] = {"status": "complete" if complete else "incomplete"}
    return NetworkFit(fit.pairs, fit.nodes, fit.folds, metadata)


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


def test_identity_guard_runs_before_repeat_runner(monkeypatch) -> None:
    fit, frame, _, _ = _fit_and_frame()
    changed = frame.copy()
    changed.iloc[0, 0] += 1.0
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("repeat runner should not be called")

    monkeypatch.setattr(stability, "_run_repeat", fail_if_called, raising=False)

    with pytest.raises(ValueError, match="data_digest|row_identity_digest"):
        stability.estimate_stability(fit, changed, elapsed_estimate=0.1)
    assert not called


def test_small_fraction_returns_unsupported_without_fitting(monkeypatch) -> None:
    fit, frame, _, _ = _fit_and_frame(n=40)
    monkeypatch.setattr(
        stability,
        "_run_repeat",
        lambda *args, **kwargs: pytest.fail("must not fit"),
        raising=False,
    )

    result = stability.estimate_stability(fit, frame, fraction=0.5, elapsed_estimate=0.1)

    assert result.status == "unsupported_repeat_request"
    assert result.repeats_requested == 10
    assert result.repeats_completed == 0
    assert result.records.empty


def test_budget_preflight_does_not_silently_reduce_requested_repeats(monkeypatch) -> None:
    fit, frame, _, _ = _fit_and_frame()
    monkeypatch.setattr(
        stability,
        "_run_repeat",
        lambda *args, **kwargs: pytest.fail("must not fit"),
        raising=False,
    )

    result = stability.estimate_stability(
        fit,
        frame,
        repeats=4,
        fraction=0.8,
        max_seconds=1.0,
        elapsed_estimate=1.0,
    )

    assert result.status == "budget_not_started"
    assert result.repeats_requested == 4
    assert result.metadata["preflight"]["estimated_seconds"] == pytest.approx(6.0)


def test_sampling_runner_receives_sorted_unique_subsamples(monkeypatch) -> None:
    fit, frame, _, _ = _fit_and_frame()
    sampled = []

    def runner(subsample, schema, config, *, repeat_seed, deadline):
        sampled.append(subsample.index.to_numpy())
        return _fake_repeat_fit()

    monkeypatch.setattr(stability, "_run_repeat", runner)

    result = stability.estimate_stability(
        fit, frame, repeats=4, fraction=0.8, max_seconds=1.0, elapsed_estimate=0.01
    )

    assert result.status == "complete"
    assert len(sampled) == 4
    for indices in sampled:
        assert len(indices) == 64
        assert np.array_equal(indices, np.unique(indices))
        assert np.all(indices[:-1] < indices[1:])


def test_interrupted_repeat_rows_cannot_be_complete_or_pass(monkeypatch) -> None:
    fit, frame, _, _ = _fit_and_frame()
    calls = 0

    def runner(subsample, schema, config, *, repeat_seed, deadline):
        nonlocal calls
        calls += 1
        return _fake_repeat_fit(complete=calls == 1)

    monkeypatch.setattr(stability, "_run_repeat", runner)

    result = stability.estimate_stability(
        fit, frame, repeats=4, fraction=0.8, max_seconds=1.0, elapsed_estimate=0.01
    )

    interrupted = result.records.loc[result.records["repeat_id"] == 1]
    assert result.status == "interrupted"
    assert result.repeats_completed == 1
    assert set(interrupted["status"]) == {"interrupted"}
    assert interrupted[["gain_i_to_j", "gain_j_to_i", "weight_nats_raw"]].isna().all().all()


def test_resume_matches_uninterrupted_records(monkeypatch) -> None:
    fit, frame, _, _ = _fit_and_frame()

    monkeypatch.setattr(stability, "_run_repeat", lambda *args, **kwargs: _fake_repeat_fit())
    full = stability.estimate_stability(
        fit, frame, repeats=4, fraction=0.8, max_seconds=1.0, elapsed_estimate=0.01
    )

    calls = 0

    def interrupting_runner(subsample, schema, config, *, repeat_seed, deadline):
        nonlocal calls
        calls += 1
        return _fake_repeat_fit(complete=calls == 1)

    monkeypatch.setattr(stability, "_run_repeat", interrupting_runner)
    partial = stability.estimate_stability(
        fit, frame, repeats=4, fraction=0.8, max_seconds=1.0, elapsed_estimate=0.01
    )
    assert partial.status == "interrupted"

    monkeypatch.setattr(stability, "_run_repeat", lambda *args, **kwargs: _fake_repeat_fit())
    resumed = stability.estimate_stability(
        fit,
        frame,
        repeats=4,
        fraction=0.8,
        max_seconds=1.0,
        resume=partial,
        elapsed_estimate=0.01,
    )

    assert resumed.status == "complete"
    pd.testing.assert_frame_equal(
        resumed.records.sort_values(list(STABILITY_COLUMNS)).reset_index(drop=True),
        full.records.sort_values(list(STABILITY_COLUMNS)).reset_index(drop=True),
    )


def test_resume_loads_from_directory_and_rejects_fraction_mismatch(monkeypatch, tmp_path) -> None:
    fit, frame, _, _ = _fit_and_frame()
    monkeypatch.setattr(stability, "_run_repeat", lambda *args, **kwargs: _fake_repeat_fit())
    result = stability.estimate_stability(
        fit, frame, repeats=2, fraction=0.8, max_seconds=1.0, elapsed_estimate=0.01
    )
    result.save(tmp_path)

    monkeypatch.setattr(
        stability,
        "_run_repeat",
        lambda *args, **kwargs: pytest.fail("completed resume should not refit"),
    )
    restored = stability.estimate_stability(
        fit,
        frame,
        repeats=2,
        fraction=0.8,
        max_seconds=1.0,
        resume=tmp_path,
        elapsed_estimate=0.01,
    )
    assert restored.status == "complete"

    with pytest.raises(ValueError, match="fraction"):
        stability.estimate_stability(
            fit,
            frame,
            repeats=2,
            fraction=0.7,
            max_seconds=1.0,
            resume=result,
            elapsed_estimate=0.01,
        )
