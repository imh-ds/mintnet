"""Known-truth simulation data generators."""

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
