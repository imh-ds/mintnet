from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest

from mintnet.simulation.cin_networks import (
    SimulatedDataset,
    _gaussian_structure,
    exact_cmi_from_joint,
    generate_cost_input,
    generate_case,
    gaussian_truth,
    is_connected,
    population_signal_summary,
)


def test_exact_cmi_matches_bruteforce_and_preserves_zero_nonedge() -> None:
    joint = np.zeros((2, 2, 2), dtype=float)
    joint[0, 0, 0] = 0.05
    joint[0, 0, 1] = 0.05
    joint[0, 1, 0] = 0.10
    joint[0, 1, 1] = 0.10
    joint[1, 0, 0] = 0.15
    joint[1, 0, 1] = 0.15
    joint[1, 1, 0] = 0.20
    joint[1, 1, 1] = 0.20

    observed = exact_cmi_from_joint(joint)

    assert set(observed) == {(0, 1), (0, 2), (1, 2)}
    assert observed[(0, 1)] > 0.0
    assert observed[(0, 2)] == pytest.approx(0.0, abs=1e-12)


def test_gaussian_truth_returns_support_and_all_pair_cmi() -> None:
    omega = np.array(
        [[1.0, -0.4, 0.0], [-0.4, 1.0, -0.2], [0.0, -0.2, 1.0]]
    )

    truth, cmi = gaussian_truth(omega)

    assert truth == frozenset({(0, 1), (1, 2)})
    assert set(cmi) == {(0, 1), (0, 2), (1, 2)}
    assert cmi[(0, 2)] == pytest.approx(0.0, abs=1e-12)


def test_population_signal_summary_is_explicit_for_available_and_unavailable_cmi() -> None:
    edges = frozenset({("V00", "V01"), ("V00", "V02")})
    available = population_signal_summary(
        {("V00", "V01"): 0.02, ("V00", "V02"): 0.005}, edges
    )
    unavailable = population_signal_summary(
        None,
        edges,
        signal_proxy={("V00", "V01"): 2.0, ("V00", "V02"): 0.5},
    )

    assert available["cmi_available"] is True
    assert available["strong_edge_count"] == 1
    assert unavailable["cmi_available"] is False
    assert unavailable["cmi_q50"] is None
    assert unavailable["proxy_available"] is True


@pytest.mark.parametrize(
    ("edges", "p", "expected"),
    [
        ([(0, 1), (1, 2)], 3, True),
        ([(0, 1)], 3, False),
    ],
)
def test_is_connected_reports_graph_connectivity(edges, p: int, expected: bool) -> None:
    assert is_connected(edges, p) is expected


def test_is_connected_rejects_invalid_graph_dimensions() -> None:
    with pytest.raises(ValueError, match="vertex"):
        is_connected([(0, 3)], 3)
    with pytest.raises(ValueError, match="p"):
        is_connected([], 0)


def test_simulated_dataset_is_frozen() -> None:
    result = SimulatedDataset(
        frame=None,
        schema={},
        truth_edges=frozenset(),
        population_cmi=None,
        meta={},
    )

    with pytest.raises(FrozenInstanceError):
        result.schema = {"V00": {"kind": "continuous"}}


@pytest.mark.parametrize("case", ["A", "B", "C"])
def test_gaussian_structure_is_positive_definite_connected_and_scaled(case: str) -> None:
    for seed in range(20):
        omega, meta = _gaussian_structure(case, seed)
        np.linalg.cholesky(omega)
        assert meta["min_eigenvalue"] >= 0.19
        assert is_connected(meta["edges"], omega.shape[0])


def test_case_b_and_d_share_structure_and_transform_only_alternating_columns() -> None:
    b = generate_case("B", structure_seed=17, sample_seed=23)
    d = generate_case("D", structure_seed=17, sample_seed=23)

    assert d.truth_edges == b.truth_edges
    assert d.population_cmi == b.population_cmi
    assert d.meta["structure_digest"] == b.meta["structure_digest"]
    transformed = tuple(range(0, b.frame.shape[1], 2))
    for column in range(b.frame.shape[1]):
        if column in transformed:
            np.testing.assert_array_equal(
                d.frame.iloc[:, column].to_numpy(),
                np.sinh(0.5 * b.frame.iloc[:, column].to_numpy()),
            )
        else:
            np.testing.assert_array_equal(
                d.frame.iloc[:, column].to_numpy(),
                b.frame.iloc[:, column].to_numpy(),
            )


def test_gaussian_seeds_separate_structure_from_observations() -> None:
    first = generate_case("A", structure_seed=17, sample_seed=23)
    same = generate_case("A", structure_seed=17, sample_seed=23)
    different_sample = generate_case("A", structure_seed=17, sample_seed=24)
    different_structure = generate_case("A", structure_seed=18, sample_seed=23)

    pd.testing.assert_frame_equal(first.frame, same.frame)
    assert first.meta == same.meta
    assert first.truth_edges == different_sample.truth_edges
    assert first.meta["structure_digest"] == different_sample.meta["structure_digest"]
    assert not np.array_equal(first.frame.to_numpy(), different_sample.frame.to_numpy())
    assert first.meta["structure_digest"] != different_structure.meta["structure_digest"]


@pytest.mark.parametrize(
    ("case", "expected_rows", "expected_columns"),
    [("A", 100, 8), ("B", 200, 30), ("C", 150, 100), ("D", 200, 30)],
)
def test_gaussian_cases_have_stable_dimensions_and_signal(case: str, expected_rows: int, expected_columns: int) -> None:
    result = generate_case(case, structure_seed=31, sample_seed=37)

    assert result.frame.shape == (expected_rows, expected_columns)
    assert tuple(result.frame.columns) == tuple(f"V{index:02d}" for index in range(expected_columns))
    assert len(result.truth_edges) > 0
    assert result.meta["population_signal_summary"]["cmi_available"] is True


def test_gaussian_case_density_targets_are_recorded() -> None:
    case_a = generate_case("A", structure_seed=41, sample_seed=43)
    case_b = generate_case("B", structure_seed=41, sample_seed=43)

    assert len(case_a.truth_edges) == 9
    assert 0.24 <= case_b.meta["edge_density"] <= 0.26


def test_case_e_is_a_depth_limited_tree_with_real_even_dependence() -> None:
    result = generate_case("E", structure_seed=11, sample_seed=13, n=4000)

    parents = result.meta["parents"]
    depths = result.meta["depths"]
    assert len(result.truth_edges) == 24
    assert max(depths) <= 3
    assert all(
        parent is None or depths[node] == depths[parent] + 1
        for node, parent in enumerate(parents)
    )
    assert {
        kind for kind in result.meta["function_types"].values() if kind != "root"
    } == {"linear", "tanh", "even"}
    assert result.meta["population_signal_summary"]["cmi_available"] is False
    assert result.meta["population_signal_summary"]["proxy_available"] is True

    even_child = next(
        node for node, kind in result.meta["function_types"].items()
        if kind == "even"
    )
    even_parent = result.meta["parents"][even_child]
    assert abs(np.corrcoef(result.frame.iloc[:, [even_parent, even_child]].to_numpy().T)[0, 1]) < 0.25


@pytest.mark.parametrize("case", ["F", "G"])
def test_exact_categorical_case_matches_joint_cmi_and_observed_support(case: str) -> None:
    result = generate_case(case, structure_seed=5, sample_seed=7)
    joint = np.asarray(result.meta["joint_tensor"], dtype=float)
    exact = exact_cmi_from_joint(joint)
    names = list(result.frame.columns)

    for (left, right), value in result.population_cmi.items():
        i, j = names.index(left), names.index(right)
        assert value == pytest.approx(exact[(i, j)], abs=1e-12)
    assert result.truth_edges == {
        (names[i], names[j])
        for (i, j), value in exact.items()
        if value >= result.meta["edge_cmi_floor"]
    }
    assert all(
        value <= 1e-12
        for pair, value in result.population_cmi.items()
        if pair not in result.truth_edges
    )


@pytest.mark.parametrize("case", ["F", "G"])
def test_categorical_sample_tracks_the_exact_joint_smoke(case: str) -> None:
    result = generate_case(case, structure_seed=17, sample_seed=19, n=4096)
    codes = result.frame.to_numpy(dtype=int)
    levels = [len(spec["levels"]) for spec in result.schema.values()]
    flat = np.ravel_multi_index(codes.T, dims=tuple(levels))
    observed = np.bincount(flat, minlength=int(np.prod(levels))) / len(codes)
    expected = np.asarray(result.meta["joint_tensor"], dtype=float).ravel()

    assert np.max(np.abs(observed - expected)) < 0.04


def test_case_h_is_a_mixed_star_with_conditional_child_independence() -> None:
    result = generate_case("H", structure_seed=3, sample_seed=4)

    assert result.frame.shape == (150, 8)
    assert result.schema["V00"] == {"kind": "categorical", "levels": [0, 1]}
    assert all(result.schema[f"V{index:02d}"]["kind"] == "continuous" for index in range(1, 8))
    assert result.truth_edges == frozenset(("V00", f"V{index:02d}") for index in range(1, 5))
    assert result.meta["hub_index"] == 0
    assert result.meta["child_indices"] == [1, 2, 3, 4]
    assert result.meta["population_signal_summary"]["cmi_available"] is False
    assert result.meta["population_signal_summary"]["proxy_available"] is True

    conditional_covariance = np.asarray(result.meta["conditional_child_covariance"], dtype=float)
    np.testing.assert_allclose(conditional_covariance, np.eye(4), atol=1e-12)


def test_case_i_is_a_mixed_independent_null() -> None:
    result = generate_case("I", structure_seed=3, sample_seed=4)

    assert result.frame.shape == (60, 30)
    assert result.truth_edges == frozenset()
    assert all(value == 0.0 for value in result.population_cmi.values())
    assert [spec["kind"] for spec in result.schema.values()].count("continuous") == 15
    assert [spec["kind"] for spec in result.schema.values()].count("categorical") == 15


@pytest.mark.parametrize("kind", ["dense_continuous", "categorical5", "categorical10", "mixed"])
def test_cost_input_contract_is_deterministic_and_has_no_truth(kind: str) -> None:
    p = 10 if kind == "mixed" else 7
    first_frame, first_schema = generate_cost_input(kind, p, 512, seed=17)
    second_frame, second_schema = generate_cost_input(kind, p, 512, seed=17)

    pd.testing.assert_frame_equal(first_frame, second_frame)
    assert first_schema == second_schema
    assert first_frame.shape == (512, p)
    assert np.isfinite(first_frame.select_dtypes(include=[np.number]).to_numpy()).all()
    assert set(first_frame.columns) == set(first_schema)
    assert all("truth_edges" not in spec for spec in first_schema.values())

    expected_levels = {"categorical5": 5, "categorical10": 10}
    if kind in expected_levels:
        assert all(spec["kind"] == "categorical" for spec in first_schema.values())
        assert all(spec["levels"] == list(range(expected_levels[kind])) for spec in first_schema.values())
    elif kind == "mixed":
        assert [spec["kind"] for spec in first_schema.values()] == [
            "continuous"
        ] * 5 + ["categorical"] * 5
        assert all(spec["levels"] == [0, 1, 2, 3, 4] for spec in list(first_schema.values())[5:])
    else:
        assert all(spec["kind"] == "continuous" for spec in first_schema.values())


def test_cost_input_rejects_invalid_requests() -> None:
    with pytest.raises(ValueError, match="kind"):
        generate_cost_input("unknown", 4, 10, seed=1)
    with pytest.raises(ValueError, match="even"):
        generate_cost_input("mixed", 5, 10, seed=1)
    with pytest.raises(ValueError, match="p"):
        generate_cost_input("dense_continuous", 0, 10, seed=1)
    with pytest.raises(ValueError, match="n"):
        generate_cost_input("dense_continuous", 4, 0, seed=1)
