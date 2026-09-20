"""Combines Stage 10a Step 2 cost shards (one per candidate-pair batch,
see stage10a_cost_shard.py) into a single cost report: real parallel
wall-clock (max across shards -- what sharded dispatch actually
achieves), serial-equivalent (sum across shards -- what an unsharded
single job would have had to pay, the category of mistake D-088
disclosed), and a recall/removal spot-check against the DGP's own
known true edges (informative for Step 1 sanity-checking; the real
calibrated Step 3/4 validation is separate, later work, not this
charter's own Step 2 cost gate)."""

from __future__ import annotations

import argparse
import glob
import json

from mintnet.experiments.stage5a import _DGP_REGISTRY

TRUE_EDGES = _DGP_REGISTRY["organic_network"]["true_edges"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards-glob", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    shards = []
    for path in sorted(glob.glob(args.shards_glob)):
        with open(path) as f:
            shards.append(json.load(f))
    shards.sort(key=lambda s: s["shard_index"])

    per_pair: dict[str, dict] = {}
    for shard in shards:
        per_pair.update(shard["per_pair"])

    retained_pairs = {tuple(int(x) for x in k.split("_")) for k, v in per_pair.items() if v["retained"]}
    true_retained = sum(1 for e in TRUE_EDGES if e in retained_pairs)
    false_candidates = [k for k, v in per_pair.items() if tuple(int(x) for x in k.split("_")) not in TRUE_EDGES]
    false_removed = sum(1 for k in false_candidates if not per_pair[k]["retained"])

    recall = true_retained / len(TRUE_EDGES) if TRUE_EDGES else float("nan")
    removal = false_removed / len(false_candidates) if false_candidates else float("nan")

    out = {
        "dgp": "organic_network",
        "n": 750,
        "total_candidate_pairs": len(per_pair),
        "total_significance_tests": sum(s["n_significance_tests"] for s in shards),
        "per_shard_seconds": [s["elapsed_seconds"] for s in shards],
        "real_parallel_wall_clock_seconds": max((s["elapsed_seconds"] for s in shards), default=0.0),
        "serial_equivalent_seconds": sum(s["elapsed_seconds"] for s in shards),
        "spot_check_true_edges_flagged": len(TRUE_EDGES & {tuple(int(x) for x in k.split("_")) for k in per_pair}),
        "spot_check_true_edges_total": len(TRUE_EDGES),
        "spot_check_recall_among_flagged": recall,
        "spot_check_removal": removal,
        "per_pair": per_pair,
    }
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != "per_pair"}, indent=2))


if __name__ == "__main__":
    main()
