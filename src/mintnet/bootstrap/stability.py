"""Bootstrap resampling and edge-stability estimation for the composed
screen-then-prune pipeline. See docs/stage3_charter.md.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from itertools import repeat

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


def _run_one_compose(
    resample: np.ndarray, screening_alpha: float, dpi_alpha: float
) -> tuple[np.ndarray, np.ndarray] | None:
    """One resample's worth of `compute_edge_stability`'s own per-iteration
    work, factored out so it can run in a worker process. Returns `None`
    for a degenerate (near-zero-variance) resample, matching the
    exclude-don't-count-as-absent handling `StabilityResult` documents.
    """
    try:
        evidence = compute_pairwise_screening_evidence(resample)
        screened = screen_uncorrected(evidence, screening_alpha)
        final, _ = compose_screen_then_prune(resample, screened, dpi_alpha)
    except ValueError:
        return None
    return screened, final


def _run_one_growing_subset(
    resample: np.ndarray, screening_alpha: float, dpi_alpha: float, max_conditioning_size: int
) -> tuple[np.ndarray, np.ndarray] | None:
    """`_run_one_compose`'s own `growing_subset_dpi` analogue."""
    try:
        evidence = compute_pairwise_screening_evidence(resample)
        screened = screen_uncorrected(evidence, screening_alpha)
        result = growing_subset_dpi(
            resample, screened, dpi_alpha, max_conditioning_size=max_conditioning_size, motif_family=None
        )
    except ValueError:
        return None
    return screened, result.adjacency


def _aggregate(p: int, outcomes) -> StabilityResult:
    candidate_counts = np.zeros((p, p))
    final_counts = np.zeros((p, p))
    successful = 0
    failed = 0
    for outcome in outcomes:
        if outcome is None:
            failed += 1
            continue
        screened, final = outcome
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


def compute_edge_stability(
    data: np.ndarray,
    screening_alpha: float,
    dpi_alpha: float,
    bootstraps: int,
    rng: np.random.Generator,
    *,
    n_jobs: int = 1,
) -> StabilityResult:
    """Run `bootstraps` row-bootstrap resamples of `data` through the frozen
    screen-then-prune pipeline (screening at `screening_alpha`, DPI at
    `dpi_alpha` -- both fixed; only the data varies across resamples) and
    tabulate per-pair candidate/final edge frequency.

    `n_jobs` (default `1`, sequential) distributes the per-resample compute
    -- the expensive part -- across `n_jobs` worker processes via
    `ProcessPoolExecutor`. All `bootstraps` resamples are still drawn
    sequentially from `rng` first, in the same order regardless of
    `n_jobs`, so results are bit-for-bit identical to the `n_jobs=1` case;
    only wall-clock time changes.
    """
    if bootstraps < 1:
        raise ValueError("bootstraps must be at least 1")
    if n_jobs < 1:
        raise ValueError("n_jobs must be at least 1")
    p = data.shape[1]
    resamples = [bootstrap_resample(data, rng) for _ in range(bootstraps)]
    if n_jobs == 1:
        outcomes = (_run_one_compose(resample, screening_alpha, dpi_alpha) for resample in resamples)
        return _aggregate(p, outcomes)
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        outcomes = list(executor.map(_run_one_compose, resamples, repeat(screening_alpha), repeat(dpi_alpha)))
    return _aggregate(p, outcomes)


def compute_edge_stability_growing_subset(
    data: np.ndarray,
    screening_alpha: float,
    dpi_alpha: float,
    max_conditioning_size: int,
    bootstraps: int,
    rng: np.random.Generator,
    *,
    n_jobs: int = 1,
) -> StabilityResult:
    """The `growing_subset_dpi` analogue of `compute_edge_stability`
    (docs/stage9a_charter.md) -- same resampling and degenerate-resample
    handling, `growing_subset_dpi` (`motif_family=None`, matching
    `stage8c_composed_calibration.py`'s own usage) in place of
    `compose_screen_then_prune` per resample. Purely additive: does not
    modify `compute_edge_stability` or any of its own already-validated
    Stage 3/3b behavior.

    `n_jobs` (default `1`) has the same meaning and same bit-for-bit-
    identical-to-sequential guarantee as `compute_edge_stability`'s own.
    """
    if bootstraps < 1:
        raise ValueError("bootstraps must be at least 1")
    if n_jobs < 1:
        raise ValueError("n_jobs must be at least 1")
    p = data.shape[1]
    resamples = [bootstrap_resample(data, rng) for _ in range(bootstraps)]
    if n_jobs == 1:
        outcomes = (
            _run_one_growing_subset(resample, screening_alpha, dpi_alpha, max_conditioning_size)
            for resample in resamples
        )
        return _aggregate(p, outcomes)
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        outcomes = list(
            executor.map(
                _run_one_growing_subset,
                resamples,
                repeat(screening_alpha),
                repeat(dpi_alpha),
                repeat(max_conditioning_size),
            )
        )
    return _aggregate(p, outcomes)
