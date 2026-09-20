"""Stage 10a Step 2 (REQUIRED before any full evidence run) -- one
SHARD of the point-estimate search's own cost measurement on the new
organic_network DGP, N=750. Sharded by candidate-pair BATCH (a new
axis this charter's own text calls for), not by (dgp, N) grid cell --
learning directly from D-088's own disclosed sharding miss on Stage
9d's cost measurement.

`growing_subset_dpi_structured_density`'s own per-pair conditioning
pool is drawn from `connected_components(flagged)` -- the FULL
candidate graph's own connectivity, not a shard-local subset. Zeroing
out other shards' candidate pairs before computing components would
silently shrink every remaining pair's own conditioning pool and
change the search's answer. This script therefore computes screening
and the full component structure identically in every shard (cheap,
deterministic, seconds not hours) and only farms out the EXPENSIVE
inner search loop across a round-robin subset of the full flagged
pair list -- reproducing growing_subset_dpi_structured_density's own
per-pair logic exactly (mintnet.pipeline.growing_subset_dpi_
structured_density) rather than modifying that already-tested
function.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from itertools import combinations

import numpy as np

from mintnet.confidence.margin import edge_margin
from mintnet.experiments.stage5a import _DGP_REGISTRY
from mintnet.mi.structured_density import local_permutation_test
from mintnet.pipeline.compose import connected_components
from mintnet.pipeline.growing_subset_dpi_structured_density import _subset_seed
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

DGP = "organic_network"
N = 750
STRENGTH = 0.5
SEED = 7
SCREENING_ALPHA = 0.001
ALPHA = 0.14
MAX_CONDITIONING_SIZE = 4
MASTER_SEED = 1
REPLICATE = 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--num-shards", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    entry = _DGP_REGISTRY[DGP]
    data = entry["sample"](N, STRENGTH, np.random.default_rng(SEED))
    evidence = compute_pairwise_screening_evidence(data)
    flagged = screen_uncorrected(evidence, SCREENING_ALPHA)
    p = flagged.shape[0]

    node_to_component: dict[int, frozenset[int]] = {}
    for component in connected_components(flagged):
        for node in component:
            node_to_component[node] = component

    all_pairs = [(i, j) for i in range(p) for j in range(i + 1, p) if flagged[i, j]]
    shard_pairs = all_pairs[args.shard_index :: args.num_shards]

    started = time.perf_counter()
    n_tests = 0
    per_pair: dict[str, dict] = {}
    for i, j in shard_pairs:
        component = node_to_component.get(i, frozenset())
        pool = sorted(component - {i, j})
        if not pool:
            per_pair[f"{i}_{j}"] = {
                "retained": True, "conditioning_size_used": 0,
                "decisive_p_value": None, "decisive_conditioning_set": [],
            }
            continue

        cap = min(len(pool), MAX_CONDITIONING_SIZE)
        pruned = False
        reached_size = 0
        triggering_p_value = math.nan
        triggering_subset: tuple[int, ...] = ()
        max_p_value = math.nan
        max_p_value_subset: tuple[int, ...] = ()
        for size in range(1, cap + 1):
            reached_size = size
            for subset in combinations(pool, size):
                seed = _subset_seed(MASTER_SEED, REPLICATE, i, j, subset)
                rng = np.random.default_rng(seed)
                try:
                    result = local_permutation_test(
                        data[:, i], data[:, j], data[:, list(subset)],
                        degree=1, ridge_lambda=1.0, cv_folds=5, k_perm=3, permutations=199,
                        symmetrize=True, rng=rng,
                    )
                    n_tests += 1
                except ValueError:
                    continue
                if math.isnan(max_p_value) or result.p_value > max_p_value:
                    max_p_value = result.p_value
                    max_p_value_subset = subset
                if result.p_value > ALPHA:
                    pruned = True
                    triggering_p_value = result.p_value
                    triggering_subset = subset
                    break
            if pruned:
                break

        resolved_p_value = triggering_p_value if pruned else max_p_value
        per_pair[f"{i}_{j}"] = {
            "retained": not pruned,
            "conditioning_size_used": reached_size,
            "decisive_p_value": None if math.isnan(resolved_p_value) else resolved_p_value,
            "decisive_conditioning_set": list(triggering_subset if pruned else max_p_value_subset),
        }
    elapsed = time.perf_counter() - started

    out = {
        "shard_index": args.shard_index,
        "num_shards": args.num_shards,
        "pairs_handled": len(shard_pairs),
        "n_significance_tests": n_tests,
        "elapsed_seconds": elapsed,
        "per_pair": per_pair,
    }
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(f"shard {args.shard_index}/{args.num_shards}: {len(shard_pairs)} pairs, {elapsed:.1f}s, {n_tests} tests")


if __name__ == "__main__":
    main()
