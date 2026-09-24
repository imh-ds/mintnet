from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from mintnet.cin.result import (
    PAIR_COLUMNS,
    NetworkFit,
    compute_fit_id,
    load_fit,
)
from mintnet.cin.views import make_view


def _sample_fit() -> NetworkFit:
    schema = {
        "alpha": {"kind": "continuous"},
        "beta": {"kind": "continuous"},
        "gamma": {"kind": "continuous"},
    }
    pairs = pd.DataFrame(
        [
            {
                "node_i": "alpha",
                "node_j": "beta",
                "gain_i_to_j": 0.20,
                "gain_j_to_i": 0.10,
                "weight_nats_raw": 0.15,
                "display_magnitude_nats": 0.15,
                "gaussian_equivalent_magnitude": 0.51,
                "orientation_gap": 0.10,
                "n_scored": 30,
                "folds_complete": 3,
                "status": "complete",
                "diagnostic_flags": "",
            },
            {
                "node_i": "alpha",
                "node_j": "gamma",
                "gain_i_to_j": -0.02,
                "gain_j_to_i": 0.03,
                "weight_nats_raw": 0.005,
                "display_magnitude_nats": 0.005,
                "gaussian_equivalent_magnitude": 0.10,
                "orientation_gap": 0.05,
                "n_scored": 30,
                "folds_complete": 3,
                "status": "complete",
                "diagnostic_flags": "",
            },
            {
                "node_i": "beta",
                "node_j": "gamma",
                "gain_i_to_j": np.nan,
                "gain_j_to_i": np.nan,
                "weight_nats_raw": np.nan,
                "display_magnitude_nats": np.nan,
                "gaussian_equivalent_magnitude": np.nan,
                "orientation_gap": np.nan,
                "n_scored": 0,
                "folds_complete": 1,
                "status": "budget_exceeded",
                "diagnostic_flags": "deadline",
            },
        ],
        columns=PAIR_COLUMNS,
    )
    metadata = {
        "config_hash": "config-digest",
        "schema": schema,
        "digests": {"data_digest": "data-digest"},
        "git_revision": "revision",
        "fit_id": compute_fit_id(
            "config-digest", schema, "data-digest", "revision"
        ),
        "complete": False,
        "data_diagnostics": {
            "few_unique_continuous": ["gamma"],
            "rare_levels": [],
            "p_ge_n": False,
            "q_estimate": 9,
            "q_limit": 1000,
        },
    }
    return NetworkFit(
        pairs=pairs,
        nodes=pd.DataFrame([{"node": name} for name in schema]),
        folds=pd.DataFrame([{"fold": 0, "status": "complete"}]),
        metadata=metadata,
    )


def _synthetic_fit(node_count: int) -> NetworkFit:
    schema = {f"node_{index:03d}": {"kind": "continuous"} for index in range(node_count)}
    records = []
    for left in range(node_count):
        for right in range(left + 1, node_count):
            records.append(
                {
                    "node_i": f"node_{left:03d}",
                    "node_j": f"node_{right:03d}",
                    "gain_i_to_j": 0.1,
                    "gain_j_to_i": 0.1,
                    "weight_nats_raw": 0.1,
                    "display_magnitude_nats": 0.1,
                    "gaussian_equivalent_magnitude": 0.4,
                    "orientation_gap": 0.0,
                    "n_scored": 30,
                    "folds_complete": 3,
                    "status": "complete",
                    "diagnostic_flags": "",
                }
            )
    fit_id = compute_fit_id("config", schema, "data", "revision")
    return NetworkFit(
        pairs=pd.DataFrame(records, columns=PAIR_COLUMNS),
        nodes=pd.DataFrame([{"node": name} for name in schema]),
        folds=pd.DataFrame([{"fold": 0}]),
        metadata={
            "config_hash": "config",
            "schema": schema,
            "digests": {"data_digest": "data"},
            "git_revision": "revision",
            "fit_id": fit_id,
        },
    )


def test_network_fit_save_load_round_trip_preserves_tables_and_metadata(tmp_path) -> None:
    fit = _sample_fit()

    fit.save(tmp_path)
    restored = load_fit(tmp_path)

    assert {
        "pairs.csv",
        "nodes.csv",
        "folds.csv",
        "matrix_weight.csv",
        "matrix_display.csv",
        "metadata.json",
    } == {path.name for path in tmp_path.iterdir()}
    pd.testing.assert_frame_equal(restored.pairs, fit.pairs)
    pd.testing.assert_frame_equal(restored.nodes, fit.nodes)
    pd.testing.assert_frame_equal(restored.folds, fit.folds)
    assert restored.metadata == fit.metadata


def test_network_fit_persists_incomplete_pairs_as_nan_not_zero(tmp_path) -> None:
    fit = _sample_fit()

    fit.save(tmp_path)
    matrix = pd.read_csv(tmp_path / "matrix_weight.csv", index_col=0)

    assert np.isnan(matrix.loc["beta", "gamma"])
    assert np.isnan(matrix.loc["gamma", "beta"])
    assert matrix.loc["alpha", "beta"] == pytest.approx(0.15)


def test_network_fit_load_rejects_corrupt_pair_table(tmp_path) -> None:
    _sample_fit().save(tmp_path)
    pairs = pd.read_csv(tmp_path / "pairs.csv", keep_default_na=False)
    pairs = pairs.iloc[:-1]
    pairs.to_csv(tmp_path / "pairs.csv", index=False)

    with pytest.raises(ValueError, match="pair"):
        load_fit(tmp_path)


def test_network_fit_metadata_json_is_not_raw_data() -> None:
    fit = _sample_fit()

    payload = json.loads(json.dumps(fit.metadata))

    assert "raw_data" not in payload
    assert "data_digest" in payload["digests"]


def test_make_view_applies_effect_then_agreement_filters_without_mutating_fit() -> None:
    fit = _sample_fit()
    before = fit.pairs.copy(deep=True)

    landscape = make_view(fit)
    effect = make_view(fit, min_effect=0.005)
    agreement = make_view(fit, require_both_positive=True)

    assert list(landscape.edges[["node_i", "node_j"]].itertuples(index=False, name=None)) == [
        ("alpha", "beta"),
        ("alpha", "gamma"),
    ]
    assert list(effect.edges["node_j"]) == ["beta", "gamma"]
    assert list(agreement.edges[["node_i", "node_j"]].itertuples(index=False, name=None)) == [
        ("alpha", "beta")
    ]
    assert landscape.label == "Landscape"
    assert effect.label == "Effect-filtered"
    assert agreement.label == "Agreement-filtered"
    pd.testing.assert_frame_equal(fit.pairs, before)


def test_make_view_presentation_limits_are_explicit_and_deterministic() -> None:
    fit = _sample_fit()

    limited = make_view(fit, max_edges=1)
    fractional = make_view(fit, top_fraction=0.5)

    assert list(limited.edges["node_j"]) == ["beta"]
    assert list(fractional.edges["node_j"]) == ["beta"]
    assert limited.settings["presentation_limit"] is True
    assert limited.settings["edges_cut"] == 1
    assert "+ Presentation limit" in limited.label
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_view(fit, max_edges=1, top_fraction=0.5)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"min_effect": -0.1}, "min_effect"),
        ({"max_edges": 0}, "max_edges"),
        ({"top_fraction": 0.0}, "top_fraction"),
        ({"top_fraction": 1.1}, "top_fraction"),
        ({"min_stability": 0.5}, "stability"),
    ],
)
def test_make_view_rejects_invalid_filter_settings(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        make_view(_sample_fit(), **kwargs)


def test_view_matrix_and_edge_list_preserve_incomplete_and_non_displayed_pairs() -> None:
    view = make_view(_sample_fit(), min_effect=0.01)

    matrix = view.to_matrix()
    edge_list = view.to_edge_list()

    assert matrix.loc["alpha", "beta"] == pytest.approx(0.15)
    assert matrix.loc["alpha", "gamma"] == 0.0
    assert np.isnan(matrix.loc["beta", "gamma"])
    assert list(edge_list.columns) == ["node_i", "node_j", "weight"]
    assert list(edge_list[["node_i", "node_j"]].itertuples(index=False, name=None)) == [
        ("alpha", "beta")
    ]


def test_view_save_writes_documented_artifacts(tmp_path) -> None:
    view = make_view(_sample_fit())

    view.save(tmp_path, plots=False)

    assert {
        "edges.csv",
        "edge_list.csv",
        "matrix.csv",
        "view.json",
        "methods.txt",
    } <= {path.name for path in tmp_path.iterdir()}
    assert list(pd.read_csv(tmp_path / "edge_list.csv").columns) == [
        "node_i",
        "node_j",
        "weight",
    ]
    payload = json.loads((tmp_path / "view.json").read_text(encoding="utf-8"))
    assert payload["fit_id"] == view.fit_id


def test_methods_text_reports_model_configuration_filters_and_limitations() -> None:
    fit = _sample_fit()
    metadata = dict(fit.metadata)
    metadata.update(
        {
            "config": {
                "outer_folds": 3,
                "inner_folds": 2,
                "lambda_grid": [0.1, 1.0],
                "missing": "complete_case",
            },
            "retained_count": 30,
            "excluded_count": 2,
        }
    )
    fit = NetworkFit(fit.pairs, fit.nodes, fit.folds, metadata)
    text = make_view(fit, min_effect=0.01, require_both_positive=True).methods_text()

    for phrase in (
        "conditional predictive information",
        "nats per observation",
        "undirected average",
        "all other included variables",
        "linear",
        "LSPC-type",
        "K=3",
        "J=2",
        "0.1, 1",
        "complete_case",
        "retained N=30",
        "training partitions only",
        "exact omission",
        "not a significance test",
        "not true CMI",
        "variance-only",
        "XOR",
        "Gaussian",
        "independent rows",
        "causal interpretation",
        "confidence interval",
        "p-value",
        "unvalidated delta",
    ):
        assert phrase in text, phrase
    assert "significant" not in text


def test_methods_text_lists_triggered_diagnostic_warnings() -> None:
    fit = _sample_fit()
    metadata = dict(fit.metadata)
    metadata.update(
        {
            "retained_count": 12,
            "data_diagnostics": {
                "few_unique_continuous": ["alpha"],
                "rare_levels": [["group", "rare", 2]],
                "p_ge_n": True,
                "q_estimate": 20,
                "q_limit": 10,
            },
        }
    )
    nodes = fit.nodes.copy()
    nodes["variance_floor_hits"] = [1, 0, 0]
    fit = NetworkFit(fit.pairs, nodes, fit.folds, metadata)

    text = make_view(fit).methods_text()

    assert "Warnings:" in text
    assert "low retained N" in text
    assert "p >= N" in text
    assert "rare categorical levels" in text
    assert "variance-floor hits" in text
    assert "incomplete pairs" in text


@pytest.mark.parametrize("node_count", [2, 8, 100])
def test_view_plots_have_one_line_collection_per_displayed_edge(node_count: int) -> None:
    matplotlib = pytest.importorskip("matplotlib")
    from matplotlib.collections import LineCollection

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    view = make_view(_synthetic_fit(node_count))
    figure = view.plot()
    matrix_figure = view.plot("matrix")

    assert sum(isinstance(collection, LineCollection) for collection in figure.axes[0].collections) == len(
        view.edges
    )
    assert len(matrix_figure.axes) == 2
    plt.close(figure)
    plt.close(matrix_figure)
