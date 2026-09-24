"""Known-truth simulation data generators."""

from .cin_networks import (
    SimulatedDataset,
    exact_cmi_from_joint,
    gaussian_truth,
    generate_case,
    generate_cost_input,
    is_connected,
    population_signal_summary,
)
from .motifs import (
    ORGANIC_NETWORK_TRUE_EDGES,
    sample_chain,
    sample_hub,
    sample_measured_fork,
    sample_monotonic_curvature_triangle,
    sample_organic_network,
    sample_overlapping_triangles,
    sample_precision_triangle,
    sample_ushape_triangle,
    sample_weak_edge_triangle,
    triangle_precisions,
)

__all__ = [
    "ORGANIC_NETWORK_TRUE_EDGES",
    "SimulatedDataset",
    "exact_cmi_from_joint",
    "gaussian_truth",
    "generate_case",
    "generate_cost_input",
    "is_connected",
    "population_signal_summary",
    "sample_chain",
    "sample_hub",
    "sample_measured_fork",
    "sample_monotonic_curvature_triangle",
    "sample_organic_network",
    "sample_overlapping_triangles",
    "sample_precision_triangle",
    "sample_ushape_triangle",
    "sample_weak_edge_triangle",
    "triangle_precisions",
]
