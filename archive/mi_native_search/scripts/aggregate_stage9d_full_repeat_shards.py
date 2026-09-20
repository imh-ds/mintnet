"""Combines Stage 9d full-repeat cost shards (one per bootstrap resample,
see stage9d_full_repeat_cost_shard.py) into the same pi_final shape the
old unsharded measurement would have produced, plus both an honest real
parallel wall-clock figure (max across shards -- what a sharded dispatch
actually achieves) and a serial-equivalent figure (sum across shards --
what the old, cancelled unsharded run was actually attempting)."""

from __future__ import annotations

import argparse
import glob
import json

import numpy as np

QUALIFYING_PAIRS = [(6, 7), (6, 8), (7, 8), (8, 9), (8, 10), (9, 10)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards-glob", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    shards = []
    for path in sorted(glob.glob(args.shards_glob)):
        with open(path) as f:
            shards.append(json.load(f))
    shards.sort(key=lambda s: s["resample_index"])

    usable = [s for s in shards if not s["degenerate"]]
    counts: dict[tuple[int, int], int] = {pair: 0 for pair in QUALIFYING_PAIRS}
    for shard in usable:
        adjacency = np.array(shard["adjacency"])
        for i, j in QUALIFYING_PAIRS:
            if adjacency[i, j]:
                counts[(i, j)] += 1

    pi_final = {
        f"{i}_{j}": (counts[(i, j)] / len(usable) if usable else float("nan"))
        for i, j in QUALIFYING_PAIRS
    }

    out = {
        "mechanism": "full_repeat",
        "shards": len(shards),
        "usable_shards": len(usable),
        "per_shard_seconds": [s["elapsed_seconds"] for s in shards],
        "real_parallel_wall_clock_seconds": max((s["elapsed_seconds"] for s in shards), default=0.0),
        "serial_equivalent_seconds": sum(s["elapsed_seconds"] for s in shards),
        "pi_final": pi_final,
    }
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
