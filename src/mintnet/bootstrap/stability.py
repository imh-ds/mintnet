"""Bootstrap resampling and edge-stability estimation for the composed
screen-then-prune pipeline. See docs/stage3_charter.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mintnet.pipeline import compose_screen_then_prune
from mintnet.pipeline.growing_subset_dpi import growing_subset_dpi
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected


@dataclass(frozen=True)
class StabilityResult:
    """Bootstrap edge-stability estimate for one dataset.

    `pi_candidate`/`pi_final` are p x p float matrices: the fraction of
    *successful* bootstrap resamples in which each pair was, respectively,
    a screening candidate edge and a final (post-DPI) edge. A resample
    whose pipeline run raises (a degenerate, near-zero-variance resample
    -- see docs/stage3_charter.md's "why now" note on the zero-variance
    guards this depends on) is excluded from both the numerator and the
    denominator, not counted as edge-absent -- that distinction is the
    entire point of the guards this module relies on. How many resamples
    were excluded is recorded in `failed_bootstraps`, not silently
    dropped.
    """

    pi_candidate: np.ndarray
    pi_final: np.ndarray
    successful_bootstraps: int
    failed_bootstraps: int


def bootstrap_resample(data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Draw one nonparametric row bootstrap resample of `data` (same row count, with replacement)."""
    n = data.shape[0]
    indices = rng.integers(0, n, size=n)
    return data[indices]


def compute_edge_stability(
    data: np.ndarray,
    screening_alpha: float,
    dpi_alpha: float,
    bootstraps: int,
    rng: np.random.Generator,
) -> StabilityResult:
    """Run `bootstraps` row-bootstrap resamples of `data` through the frozen
    screen-then-prune pipeline (screening at `screening_alpha`, DPI at
    `dpi_alpha` -- both fixed; only the data varies across resamples) and
    tabulate per-pair candidate/final edge frequency.
    """
    if bootstraps < 1:
        raise ValueError("bootstraps must be at least 1")
    p = data.shape[1]
    candidate_counts = np.zeros((p, p))
    final_counts = np.zeros((p, p))
    successful = 0
    failed = 0
    for _ in range(bootstraps):
        resample = bootstrap_resample(data, rng)
        try:
            evidence = compute_pairwise_screening_evidence(resample)
            screened = screen_uncorrected(evidence, screening_alpha)
            final, _ = compose_screen_then_prune(resample, screened, dpi_alpha)
        except ValueError:
            failed += 1
            continue
        candidate_counts += screened
        final_counts += final
        successful += 1
    if successful == 0:
        raise RuntimeError("every bootstrap resample was degenerate; cannot compute edge stability")
    return StabilityResult(
        pi_candidate=candidate_counts / successful,
        pi_final=final_counts / successful,
        successful_bootstraps=successful,
        failed_bootstraps=failed,
    )


def compute_edge_stability_growing_subset(
    data: np.ndarray,
    screening_alpha: float,
    dpi_alpha: float,
    max_conditioning_size: int,
    bootstraps: int,
    rng: np.random.Generator,
) -> StabilityResult:
    """The `growing_subset_dpi` analogue of `compute_edge_stability`
    (docs/stage9a_charter.md) -- same resampling and degenerate-resample
    handling, `growing_subset_dpi` (`motif_family=None`, matching
    `stage8c_composed_calibration.py`'s own usage) in place of
    `compose_screen_then_prune` per resample. Purely additive: does not
    modify `compute_edge_stability` or any of its own already-validated
    Stage 3/3b behavior.
    """
    if bootstraps < 1:
        raise ValueError("bootstraps must be at least 1")
    p = data.shape[1]
    candidate_counts = np.zeros((p, p))
    final_counts = np.zeros((p, p))
    successful = 0
    failed = 0
    for _ in range(bootstraps):
        resample = bootstrap_resample(data, rng)
        try:
            evidence = compute_pairwise_screening_evidence(resample)
            screened = screen_uncorrected(evidence, screening_alpha)
            result = growing_subset_dpi(
                resample, screened, dpi_alpha, max_conditioning_size=max_conditioning_size, motif_family=None
            )
        except ValueError:
            failed += 1
            continue
        candidate_counts += screened
        final_counts += result.adjacency
        successful += 1
    if successful == 0:
        raise RuntimeError("every bootstrap resample was degenerate; cannot compute edge stability")
    return StabilityResult(
        pi_candidate=candidate_counts / successful,
        pi_final=final_counts / successful,
        successful_bootstraps=successful,
        failed_bootstraps=failed,
    )
