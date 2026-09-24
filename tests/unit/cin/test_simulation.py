from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest

from mintnet.simulation.cin_networks import (
    SimulatedDataset,
    _gaussian_structure,
    exact_cmi_from_joint,
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
