"""Stage 9d Step 2 -- re-measures the EXISTING full-repeat bootstrap-
rescue mechanism's real cost on the same real `overlap` conditions
that motivated docs/stage9d_charter.md, dispatched via GitHub Actions
per this project's own standing requirement that time-consuming runs
never execute locally (a requirement this project's own earlier local
dispatch of this exact measurement violated -- see D-088's disclosure
and the corrected re-run this script performs).

Fixed dataset/parameters, identical to the local run being replaced:
`overlap`, `N=750`, `strength=0.5`, `seed=7`, `screening_alpha=0.001`,
`alpha=0.14`, `max_conditioning_size=4`, `bootstraps=2`,
`master_seed=1`, `replicate=0`, `bootstrap_rng` seed `2`. The one
deliberate correction from the earlier local run: `n_jobs="auto"`
(the charter's own specified setting), not `n_jobs=1`.

Writes a single JSON result to the given `--output` path rather than
raw_metrics.csv, since this is a one-off head-to-head timing
measurement, not a gridded evidence-generation run -- it does not use
the generic sharded_benchmark.yml matrix contract.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from mintnet.experiments.stage5a import _DGP_REGISTRY
from mintnet.pipeline.stability_rescue import growing_subset_dpi_structured_density_with_stability_rescue
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

DGP = "overlap"
N = 750
STRENGTH = 0.5
SEED = 7
SCREENING_ALPHA = 0.001
ALPHA = 0.14
MAX_CONDITIONING_SIZE = 4
BOOTSTRAPS = 2
MASTER_SEED = 1
REPLICATE = 0
BOOTSTRAP_RNG_SEED = 2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    entry = _DGP_REGISTRY[DGP]
    data = entry["sample"](N, STRENGTH, np.random.default_rng(SEED))
    evidence = compute_pairwise_screening_evidence(data)
    flagged = screen_uncorrected(evidence, SCREENING_ALPHA)

    started = time.perf_counter()
    result = growing_subset_dpi_structured_density_with_stability_rescue(
        data, flagged, ALPHA,
        max_conditioning_size=MAX_CONDITIONING_SIZE,
        screening_alpha=SCREENING_ALPHA,
        bootstraps=BOOTSTRAPS,
        pi_min=0.5,
        master_seed=MASTER_SEED,
        replicate=REPLICATE,
        n_jobs="auto",
        bootstrap_rng=np.random.default_rng(BOOTSTRAP_RNG_SEED),
    )
    elapsed = time.perf_counter() - started

    out = {
        "mechanism": "full_repeat",
        "dgp": DGP,
        "n": N,
        "bootstraps": BOOTSTRAPS,
        "n_jobs": "auto",
        "elapsed_seconds": elapsed,
        "bootstrapped": result.bootstrapped,
        "pi_final": {f"{i}_{j}": v for (i, j), v in result.pi_final.items()},
    }
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(f"full-repeat total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
