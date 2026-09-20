"""Diagnostic (not a gated charter) measuring how often the local-
permutation shuffle's neighbor pool is exhausted, for both the fixed
construction (`mintnet.mi.cmiknn._restricted_permutation`) and a
reconstruction of the pre-D-055-fix construction -- requested by peer
review to turn D-055's causal story ("the global fallback under local
exhaustion corrupts locality, and that's why |S| in {1,2} miscalibrated
while |S|=0 didn't") into something measured, not inferred. See
docs/decision_log.md D-055 and Stage 6d.

Deliberately cheap: skips `estimate_cmiknn` entirely -- only the
neighbor-matching/index bookkeeping is measured, since that's the part
under test, not the CMI estimate itself. Runs locally in well under a
minute; does not repeat the earlier mistake of running expensive
permutation *significance tests* (which do call `estimate_cmiknn`
hundreds of times each) outside GitHub Actions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage6c import K_PERM_LABELS, NULL_CONDITIONS, resolve_k_perm
from mintnet.mi.cmiknn import _standardize_columns, _z_neighbors
from scipy.spatial import cKDTree


def _legacy_z_neighbors(z_standardized: np.ndarray, k_perm: int) -> np.ndarray:
    """Reconstruction of the pre-D-055-fix neighbor query: excludes
    self, Euclidean (scipy default `p=2`) distance -- NOT used in
    production, diagnostic-only, to measure how often the OLD
    construction's global fallback actually triggered."""
    n = z_standardized.shape[0]
    tree = cKDTree(z_standardized)
    k = min(k_perm + 1, n)
    _, neighbor_idx = tree.query(z_standardized, k=k)
    return neighbor_idx[:, 1:]


def _legacy_permutation_with_fallback_count(
    neighbors: np.ndarray, n: int, rng: np.random.Generator
) -> tuple[np.ndarray, int]:
    """Reconstruction of the pre-D-055-fix `_local_permutation`'s own
    assignment loop, instrumented to count how many assignments took
    the global-fallback branch (every local candidate already used)."""
    order = rng.permutation(n)
    used = np.zeros(n, dtype=bool)
    perm = np.full(n, -1, dtype=int)
    fallback_count = 0
    for i in order:
        candidates = [int(j) for j in neighbors[i] if not used[j]]
        if candidates:
            j = candidates[int(rng.integers(len(candidates)))]
        else:
            fallback_count += 1
            leftover = np.flatnonzero(~used)
            j = int(leftover[int(rng.integers(len(leftover)))])
        perm[i] = j
        used[j] = True
    return perm, fallback_count


def _new_permutation_with_exhaustion_count(neighbors: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, int]:
    """Same loop as `mintnet.mi.cmiknn._restricted_permutation`,
    instrumented to count assignments that were forced to reuse an
    already-used neighbor (every local candidate exhausted)."""
    n, k = neighbors.shape
    shuffled = neighbors.copy()
    for row in shuffled:
        rng.shuffle(row)

    order = rng.permutation(n)
    used = np.zeros(n, dtype=bool)
    perm = np.empty(n, dtype=int)
    exhaustion_count = 0
    for i in order:
        m = 0
        use = int(shuffled[i, m])
        while used[use] and m < k - 1:
            m += 1
            use = int(shuffled[i, m])
        if used[use]:
            exhaustion_count += 1
        perm[i] = use
        used[use] = True
    return perm, exhaustion_count


def measure(
    sample_sizes: tuple[int, ...] = (150, 300, 750),
    k_perm_labels: tuple[str, ...] = K_PERM_LABELS,
    n_datasets: int = 20,
    n_permutations_per_dataset: int = 100,
    master_seed: int = 90001,
) -> pd.DataFrame:
    """|S|=0 excluded -- it never uses local neighbor matching (global
    permutation instead), so there is nothing to measure there. For
    each (condition, N, k_perm) cell: draw `n_datasets` independent
    datasets from that condition's own DGP, build each dataset's
    neighbor structure once (as the real code does), then run
    `n_permutations_per_dataset` permutation draws against both the
    new and reconstructed-legacy construction, counting how many of
    the resulting per-point assignments were forced by exhaustion
    (new) or triggered the global fallback (legacy)."""
    rows: list[dict[str, object]] = []
    for condition_index, condition in enumerate(NULL_CONDITIONS):
        label = str(condition["label"])
        s = int(condition["s"])
        if s == 0:
            continue
        sample = condition["sample"]
        z_cols = condition["z"]  # type: ignore[assignment]

        for n in sample_sizes:
            for k_perm_label in k_perm_labels:
                k_perm_index = K_PERM_LABELS.index(k_perm_label)
                k_perm = resolve_k_perm(k_perm_label, n)
                total_assignments = 0
                new_exhaustions = 0
                legacy_fallbacks = 0

                for dataset_index in range(n_datasets):
                    seed = int(
                        np.random.SeedSequence(
                            [master_seed, condition_index, n, k_perm_index, dataset_index]
                        ).generate_state(1)[0]
                    )
                    rng_data = np.random.default_rng(seed)
                    data = sample(n, rng_data)  # type: ignore[operator]
                    z = data[:, list(z_cols)]
                    z_s = _standardize_columns(z)

                    new_neighbors = _z_neighbors(z_s, k_perm)
                    legacy_neighbors = _legacy_z_neighbors(z_s, k_perm)

                    rng_perm = np.random.default_rng(seed + 1)
                    for _ in range(n_permutations_per_dataset):
                        _, exh = _new_permutation_with_exhaustion_count(new_neighbors, rng_perm)
                        new_exhaustions += exh
                        _, fb = _legacy_permutation_with_fallback_count(legacy_neighbors, n, rng_perm)
                        legacy_fallbacks += fb
                        total_assignments += n

                rows.append(
                    {
                        "label": label,
                        "s": s,
                        "n": n,
                        "k_perm_label": k_perm_label,
                        "k_perm_resolved": k_perm,
                        "n_datasets": n_datasets,
                        "n_permutations_per_dataset": n_permutations_per_dataset,
                        "total_assignments": total_assignments,
                        "new_exhaustion_rate": new_exhaustions / total_assignments,
                        "legacy_fallback_rate": legacy_fallbacks / total_assignments,
                    }
                )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = measure()
    output_dir = Path("results/generated/stage6d_exhaustion_diagnostic")
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / "exhaustion_rates.csv", index=False)
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(df.to_string(index=False))
