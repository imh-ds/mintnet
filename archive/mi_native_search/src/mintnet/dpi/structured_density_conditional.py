"""Conditional-independence pruning via the structured conditional-
density MI/CMI estimator (`mintnet.mi.structured_density`) -- the
Stage 7d candidate alternative to `mintnet.dpi.cmi_conditional`'s own
CMIknn-based test. See docs/stage7d_charter.md.

Same shape and "compute once, threshold many times" structure as
`mintnet.dpi.cmi_conditional`: for a 3-column motif, every pair's only
possible conditioning set is the remaining third column, so each
pair's CMI/p-value is computed exactly once per replicate regardless
of how many `alpha` values are later swept against it.

**One disclosed difference from `cmi_conditional`'s own contract**:
CMIknn's point estimate is a deterministic function of the data alone,
so only `p_value` depends on `seed_context` there. This estimator's own
`cmi` also depends on `seed_context`, since it seeds the cross-fitting
fold assignment (see `mintnet.mi.structured_density.local_permutation_test`'s
own docstring) -- a different `seed_context` can therefore shift both
`cmi` and `p_value`, not `p_value` alone. This is expected, not a
regression in determinism: the same `seed_context` still reproduces
identical evidence exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from mintnet.mi.structured_density import local_permutation_test


@dataclass(frozen=True)
class StructuredDensityConditionalIndependenceEvidence:
    """Structured-density CMI test evidence for a three-column sample --
    same shape/contract as
    `mintnet.dpi.cmi_conditional.CMIConditionalIndependenceEvidence`."""

    cmi: np.ndarray
    p_value: np.ndarray


def _validate_data(data: np.ndarray) -> np.ndarray:
    values = np.asarray(data, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("data must be a two-dimensional array with three columns")
    if not np.isfinite(values).all():
        raise ValueError("data must contain only finite values")
    return values


def compute_structured_density_conditional_independence_evidence(
    data: np.ndarray,
    *,
    seed_context: tuple[int, ...],
    degree: int = 2,
    ridge_lambda: float = 1.0,
    cv_folds: int = 5,
    k_perm: int = 3,
    permutations: int = 199,
    symmetrize: bool = True,
) -> StructuredDensityConditionalIndependenceEvidence:
    """Test each pair for independence conditional on the remaining
    third column, via `mintnet.mi.structured_density.local_permutation_test`.

    `seed_context` seeds each pair's own permutation RNG
    deterministically -- pass whatever already-known, full-grid
    quantities identify this replicate (e.g. `(master_seed, motif_index,
    sample_index, condition_index, replicate)`); the pair `(i, j)` is
    appended internally so the three pairs of the same replicate don't
    share a seed. Same convention as
    `mintnet.dpi.cmi_conditional.compute_cmi_conditional_independence_evidence`.
    """
    values = _validate_data(data)

    cmi = np.zeros((3, 3))
    p_value = np.ones((3, 3))
    for i, j in combinations(range(3), 2):
        (k,) = {0, 1, 2} - {i, j}
        sequence = np.random.SeedSequence([*seed_context, i, j])
        rng = np.random.default_rng(int(sequence.generate_state(1)[0]))
        result = local_permutation_test(
            values[:, i], values[:, j], values[:, k],
            degree=degree, ridge_lambda=ridge_lambda, cv_folds=cv_folds,
            k_perm=k_perm, permutations=permutations, symmetrize=symmetrize, rng=rng,
        )
        cmi[i, j] = cmi[j, i] = result.statistic
        p_value[i, j] = p_value[j, i] = result.p_value
    return StructuredDensityConditionalIndependenceEvidence(cmi, p_value)


def prune_structured_density_conditional_independence(
    evidence: StructuredDensityConditionalIndependenceEvidence, alpha: float
) -> np.ndarray:
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
