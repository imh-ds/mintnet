"""Known-truth simulation data generators."""

from .motifs import (
    sample_chain,
    sample_hub,
    sample_measured_fork,
    sample_monotonic_curvature_triangle,
    sample_overlapping_triangles,
    sample_precision_triangle,
    sample_ushape_triangle,
    sample_weak_edge_triangle,
    triangle_precisions,
)

__all__ = [
    "sample_chain",
    "sample_hub",
    "sample_measured_fork",
    "sample_monotonic_curvature_triangle",
    "sample_overlapping_triangles",
    "sample_precision_triangle",
    "sample_ushape_triangle",
    "sample_weak_edge_triangle",
    "triangle_precisions",
]
