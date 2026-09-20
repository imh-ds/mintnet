"""Diagnostic (not a gated charter) measuring real wall-clock speedup
from `growing_subset_dpi_with_stability_rescue`'s own `n_jobs`
parameter (see `mintnet.bootstrap.stability._resolve_n_jobs`) on this
machine, at `bootstraps=500` -- the same `B` Stage 9b's own PROCEED
finding (D-080) used.

Uses the EXACT same DGP, sample size, fitted `alpha`, and RNG seeds as
two real qualifying replicates pulled directly from Stage 9b's own
downloaded raw evidence (`chain_fork_hub` n=1750 replicate=15,
`overlap` n=1750 replicate=0 -- both `dataset_bootstrapped=True`), not
a synthetic toy case, so the timing reflects an actual qualifying
network rather than a best/worst-case construction.

Results are proven bit-for-bit identical across every `n_jobs` value
(see `tests/unit/test_bootstrap_stability.py`'s own equivalence tests)
-- this script measures only wall-clock time, never correctness.

Measured once on a 20-logical-core Windows machine (unthrottled, no
`OMP_NUM_THREADS` cap, unlike Stage 9a/9b's own GitHub Actions
evidence):

    === chain_fork_hub, n=1750 ===
    n_jobs= 1:    85.7s
    n_jobs= 4:    23.9s  (3.6x)
    n_jobs= 8:    15.4s  (5.6x)
    n_jobs=16:    18.4s  (4.7x -- WORSE than n_jobs=8)

    === overlap, n=1750 ===
    n_jobs= 1:   101.6s
    n_jobs= 4:    30.7s  (3.3x)
    n_jobs= 8:    20.1s  (5.1x)
    n_jobs=16:    22.6s  (4.5x -- WORSE than n_jobs=8)

Speedup keeps improving through `n_jobs=8` (~5x here), then gets worse
at `n_jobs=16`: at this per-resample workload size, process-spawn/IPC
overhead outweighs the added parallelism past roughly half this
machine's logical cores. This motivated `_AUTO_N_JOBS_CAP = 8`, not the
host's full core count, as `n_jobs="auto"`'s own ceiling. Re-run this
script on a different machine before trusting these exact numbers
elsewhere -- only the qualitative shape (diminishing, then negative,
returns past some point well short of every core) is expected to
transfer, not the specific `8`.
"""

from __future__ import annotations

import time

import numpy as np

from mintnet.experiments.stage5a import _DGP_REGISTRY
from mintnet.pipeline.stability_rescue import growing_subset_dpi_with_stability_rescue
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

# (dgp, n, alpha, base_seed, bootstrap_seed) -- alpha and base_seed read
# directly off Stage 9b's own raw_metrics.csv for these two rows;
# bootstrap_seed=1 is an arbitrary fixed seed for this diagnostic only
# (Stage 9b's own actual bootstrap_seed is not needed here -- only a
# reproducible one for this script's own repeated timing runs).
CASES = [
    ("chain_fork_hub", 1750, 0.099644, 49923560, 1),
    ("overlap", 1750, 0.099644, 1943519363, 1),
]

N_JOBS_VALUES: tuple[int, ...] = (1, 4, 8, 16)


def main() -> None:
    for dgp, n, alpha, seed, bootstrap_seed in CASES:
        entry = _DGP_REGISTRY[dgp]
        data = entry["sample"](n, 0.5, np.random.default_rng(seed))
        evidence = compute_pairwise_screening_evidence(data)
        flagged = screen_uncorrected(evidence, 0.001)

        print(f"\n=== {dgp}, n={n} ===")
        for n_jobs in N_JOBS_VALUES:
            started = time.perf_counter()
            result = growing_subset_dpi_with_stability_rescue(
                data, flagged, alpha, max_conditioning_size=4, motif_family=None,
                screening_alpha=0.001, bootstraps=500, pi_min=0.90,
                rng=np.random.default_rng(bootstrap_seed), n_jobs=n_jobs,
            )
            elapsed = time.perf_counter() - started
            print(f"n_jobs={n_jobs:>2}: {elapsed:7.1f}s  bootstrapped={result.bootstrapped}")


if __name__ == "__main__":
    main()
