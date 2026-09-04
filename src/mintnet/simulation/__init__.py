"""Known-truth simulation data generators."""

from .motifs import (
    sample_chain,
    sample_hub,
    sample_measured_fork,
    sample_overlapping_triangles,
    sample_precision_triangle,
    sample_weak_edge_triangle,
    triangle_precisions,
)
from .screening_network import TRUE_PAIR_INDICES, sample_screening_network

__all__ = [
    "sample_chain",
    "sample_hub",
    "sample_measured_fork",
    "sample_overlapping_triangles",
    "sample_precision_triangle",
    "sample_weak_edge_triangle",
    "triangle_precisions",
    "sample_screening_network",
    "TRUE_PAIR_INDICES",
]
