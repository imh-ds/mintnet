"""Conditional-independence pruning via CMIknn/local-permutation, the
MI-based analog of `mintnet.dpi.conditional`'s own closed-form partial-
correlation test. See docs/stage7_charter.md.

For a 3-column motif, every pair's only possible conditioning set is
the remaining third column (pool size 1) -- there is no combinatorial
search here, unlike `mintnet.pipeline.growing_subset_dpi_mi`'s own
general multi-node case. Each pair's CMI and p-value are therefore
computed exactly once per replicate, regardless of how many `alpha`
values are later swept against it -- mirroring
`mintnet.dpi.conditional.compute_conditional_independence_evidence`'s
own "compute once, threshold many times" structure, which matters here
specifically because a single CMI significance test costs real
wall-clock seconds, unlike the closed-form Fisher-z test it replaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from mintnet.mi.cmiknn import local_permutation_test


@dataclass(frozen=True)
class CMIConditionalIndependenceEvidence:
    """CMI-based conditional-independence test evidence for a
    three-column sample -- same shape/contract as
    `mintnet.dpi.conditional.ConditionalIndependenceEvidence`."""

    cmi: np.ndarray
    p_value: np.ndarray


def _validate_data(data: np.ndarray) -> np.ndarray:
    values = np.asarray(data, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("data must be a two-dimensional array with three columns")
    if not np.isfinite(values).all():
        raise ValueError("data must contain only finite values")
    return values


def compute_cmi_conditional_independence_evidence(
    data: np.ndarray,
    *,
    seed_context: tuple[int, ...],
    k_cmi: int = 40,
    k_perm: int = 3,
    permutations: int = 199,
) -> CMIConditionalIndependenceEvidence:
    """Test each pair for independence conditional on the remaining
    third column, via the calibrated CMIknn/local-permutation test
    (D-056/D-057's own `k_cmi=40`/`k_perm=3` defaults).

    `seed_context` seeds each pair's own permutation RNG
    deterministically -- pass whatever already-known, full-grid
    quantities identify this replicate (e.g. `(master_seed, motif_index,
    sample_index, strength_index, replicate)`); the pair `(i, j)` is
    appended internally so the three pairs of the same replicate don't
    share a seed.
    """
    values = _validate_data(data)
    n = values.shape[0]

    cmi = np.zeros((3, 3))
    p_value = np.ones((3, 3))
    for i, j in combinations(range(3), 2):
        (k,) = {0, 1, 2} - {i, j}
        sequence = np.random.SeedSequence([*seed_context, i, j])
        rng = np.random.default_rng(int(sequence.generate_state(1)[0]))
        result = local_permutation_test(
            values[:, i], values[:, j], values[:, k], k=k_cmi, k_perm=k_perm, permutations=permutations, rng=rng
        )
        cmi[i, j] = cmi[j, i] = result.statistic
        p_value[i, j] = p_value[j, i] = result.p_value
    return CMIConditionalIndependenceEvidence(cmi, p_value)


def prune_cmi_conditional_independence(evidence: CMIConditionalIndependenceEvidence, alpha: float) -> np.ndarray:
    """Retain an edge only when its CMI significance test rejects
    independence at `alpha` -- pure thresholding of already-computed
    evidence, zero additional significance-test cost per `alpha`."""
    if not np.isscalar(alpha):
        raise ValueError("alpha must be a scalar")
    alpha_value = float(alpha)
    if not np.isfinite(alpha_value) or not 0.0 < alpha_value < 1.0:
        raise ValueError("alpha must satisfy 0 < alpha < 1")

    adjacency = evidence.p_value <= alpha_value
    np.fill_diagonal(adjacency, False)
    return adjacency
