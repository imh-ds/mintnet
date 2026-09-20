"""Stage 9d Step 2, corrected: one SHARD of the full-repeat mechanism's
cost re-measurement (see docs/decision_log.md D-088's own disclosure --
the first attempt at this measurement ran unsharded and was cancelled
by GitHub Actions' 6-hour job limit before finishing).

`compute_edge_stability_growing_subset_structured_density` (src/mintnet/
bootstrap/stability.py) draws all `bootstraps` resamples up front from a
single stateful RNG, then processes each one completely independently
(its own full re-screen, its own full growing-subset search) --
embarrassingly parallel across resamples. This script reproduces that
exact resample-drawing order for ONE resample index (redrawing and
discarding the earlier ones, which is negligible cost -- row sampling,
not the expensive part), so a shard's own result is bit-identical to
what the same resample position would produce inside a real serial run,
while the actual expensive step (re-screen + full search) runs in its
own isolated job instead of stacking serially with every other resample.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from mintnet.bootstrap.stability import bootstrap_resample
from mintnet.experiments.stage5a import _DGP_REGISTRY
from mintnet.pipeline.growing_subset_dpi_structured_density import growing_subset_dpi_structured_density
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

DGP = "overlap"
N = 750
STRENGTH = 0.5
SEED = 7
SCREENING_ALPHA = 0.001
ALPHA = 0.14
MAX_CONDITIONING_SIZE = 4
MASTER_SEED = 1
BOOTSTRAP_RNG_SEED = 2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resample-index", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    entry = _DGP_REGISTRY[DGP]
    data = entry["sample"](N, STRENGTH, np.random.default_rng(SEED))

    rng = np.random.default_rng(BOOTSTRAP_RNG_SEED)
    resample = None
    for _ in range(args.resample_index + 1):
        resample = bootstrap_resample(data, rng)

    started = time.perf_counter()
    try:
        evidence = compute_pairwise_screening_evidence(resample)
        screened = screen_uncorrected(evidence, SCREENING_ALPHA)
        result = growing_subset_dpi_structured_density(
            resample, screened, ALPHA, master_seed=MASTER_SEED, replicate=args.resample_index,
            degree=1, ridge_lambda=1.0, cv_folds=5, k_perm=3, permutations=199,
            max_conditioning_size=MAX_CONDITIONING_SIZE,
        )
        elapsed = time.perf_counter() - started
        out = {
            "resample_index": args.resample_index,
            "elapsed_seconds": elapsed,
            "degenerate": False,
            "screened": screened.tolist(),
            "adjacency": result.adjacency.tolist(),
        }
    except ValueError:
        elapsed = time.perf_counter() - started
        out = {
            "resample_index": args.resample_index,
            "elapsed_seconds": elapsed,
            "degenerate": True,
        }

    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(f"resample {args.resample_index}: {elapsed:.1f}s, degenerate={out['degenerate']}")


if __name__ == "__main__":
    main()
