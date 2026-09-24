from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from mintnet.simulation.cin_networks import (
    SimulatedDataset,
    exact_cmi_from_joint,
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
