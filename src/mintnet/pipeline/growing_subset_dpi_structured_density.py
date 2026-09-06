"""Structured-density growing-subset DPI: identical search architecture
to `mintnet.pipeline.growing_subset_dpi`/`growing_subset_dpi_mi`
(validated on Fisher-z in Stage 6a/D-053, then on CMIknn in Stage 7),
substituting `mintnet.mi.structured_density.local_permutation_test` for
the per-subset conditional-independence test. See docs/stage7e_charter.md.

`degree=1` is the default per D-063's own calibration-transfer check:
calibrated on Stage 7's own real chain/fork null (unlike `degree=2`,
which failed that check), and the strongest performer among calibrated
survivors on the `strong` triangle's own hardest weak edge -- not an
assumption carried over from D-062's own different fixture family.

Additive -- neither `growing_subset_dpi` nor `growing_subset_dpi_mi`
is modified, and all three remain available for direct comparison.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

from mintnet.mi.structured_density import local_permutation_test
from mintnet.pipeline.compose import connected_components


@dataclass(frozen=True)
class StructuredDensityGrowingSubsetResult:
    adjacency: np.ndarray
    # Per candidate edge (i < j): the conditioning-set size that
    # determined its final retain/prune decision (0: isolated
    # two-node component, retained unconditionally).
    conditioning_size_used: dict[tuple[int, int], int]
    # Per candidate edge: True if the search-depth cap was reached
    # while the component still had untested larger subsets available.
    cap_reached: dict[tuple[int, int], bool]
    # Diagnostic, not present on growing_subset_dpi's own result: total
    # local_permutation_test calls actually made -- the primary driver
    # of this mechanism's own wall-clock cost.
    n_significance_tests: int


def _subset_seed(master_seed: int, replicate: int, i: int, j: int, subset: tuple[int, ...]) -> int:
    """Pure function of already-known, full-grid quantities (master
    seed, replicate, the pair, and the specific subset tested) -- not
    of search order or which shard runs it, so a sharded run's results
    are bit-identical to an unsharded run's for the same cell. Same
    construction as `growing_subset_dpi_mi`'s own."""
    sequence = np.random.SeedSequence([master_seed, replicate, i, j, *subset])
    return int(sequence.generate_state(1)[0])


def growing_subset_dpi_structured_density(
    data: np.ndarray,
    flagged: np.ndarray,
    alpha: float,
    *,
    master_seed: int,
    replicate: int,
    degree: int = 1,
    ridge_lambda: float = 1.0,
    cv_folds: int = 5,
    k_perm: int = 3,
    permutations: int = 199,
    symmetrize: bool = True,
    max_conditioning_size: int = 4,
) -> StructuredDensityGrowingSubsetResult:
    """Prune a candidate edge as soon as any tested conditioning subset
    (drawn from its own connected component, growing from size 1)
    fails to reject independence via the structured conditional-density
    estimator's own local-permutation test (D-063's own `degree=1`
    default); retain it only if every subset up to the cap rejects.
    `master_seed` and `replicate` key the per-subset permutation RNG
    deterministically (see `_subset_seed`) -- required since this test
    is itself randomized (both the permutation null and the
    cross-fitting fold assignment)."""
    p = flagged.shape[0]
    final = flagged.copy()
    sizes: dict[tuple[int, int], int] = {}
    cap_reached: dict[tuple[int, int], bool] = {}
    n_tests = 0

    node_to_component: dict[int, frozenset[int]] = {}
    for component in connected_components(flagged):
        for node in component:
            node_to_component[node] = component

    for i in range(p):
        for j in range(i + 1, p):
            if not flagged[i, j]:
                continue
            component = node_to_component.get(i, frozenset())
            pool = sorted(component - {i, j})

            if not pool:
                final[i, j] = final[j, i] = True
                sizes[(i, j)] = 0
                cap_reached[(i, j)] = False
                continue

            cap = min(len(pool), max_conditioning_size)
            pruned = False
            reached_size = 0
            for size in range(1, cap + 1):
                reached_size = size
                for subset in combinations(pool, size):
                    seed = _subset_seed(master_seed, replicate, i, j, subset)
                    rng = np.random.default_rng(seed)
                    x = data[:, i]
                    y = data[:, j]
                    z = data[:, list(subset)]
                    try:
                        result = local_permutation_test(
                            x, y, z, degree=degree, ridge_lambda=ridge_lambda, cv_folds=cv_folds,
                            k_perm=k_perm, permutations=permutations, symmetrize=symmetrize, rng=rng,
                        )
                        n_tests += 1
                    except ValueError:
                        # Degenerate conditioning set: inconclusive, not
                        # evidence of independence -- try the next subset.
                        continue
                    if result.p_value > alpha:
                        pruned = True
                        break
                if pruned:
                    break

            final[i, j] = final[j, i] = not pruned
            sizes[(i, j)] = reached_size
            cap_reached[(i, j)] = (not pruned) and (len(pool) > max_conditioning_size)

    return StructuredDensityGrowingSubsetResult(
        adjacency=final, conditioning_size_used=sizes, cap_reached=cap_reached, n_significance_tests=n_tests
    )
