"""Sharding-friendly entry point for Stage 6c's Stage B (the expensive
null-calibration sweep) -- see docs/stage6c_charter.md and
.github/workflows/sharded_benchmark.yml's own generic dispatch
contract. `mintnet.experiments.stage6c`'s own `main()` keeps the local
`--stage a/b/c` CLI for ad hoc use; this module exists only so
`scripts/aggregate_shards.py` and the workflow's `runner_module` input
have a single-config, single-purpose target to point at for Stage B
specifically, the one stage expensive enough to need CI sharding.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from mintnet.experiments.stage6c import NULL_CONDITIONS, StageBConfig, run_stage_b


def load_config(path: Path) -> StageBConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    block = values["stage_b"]
    return StageBConfig(
        k_cmi=int(block["k_cmi"]),
        k_perm_labels=tuple(str(v) for v in block["k_perm_labels"]),
        sample_sizes=tuple(int(v) for v in block["sample_sizes"]),
        replicates=int(block["replicates"]),
        permutations=int(block["permutations"]),
        alphas=tuple(float(v) for v in block["alphas"]),
        master_seed=int(block["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("k_perm_label", "label", "n")


def expected_combinations(config: StageBConfig) -> set[tuple[str, str, int]]:
    combos: set[tuple[str, str, int]] = set()
    for condition in NULL_CONDITIONS:
        label = str(condition["label"])
        s = int(condition["s"])
        k_perm_labels = ("kperm5",) if s == 0 else config.k_perm_labels
        for k_perm_label in k_perm_labels:
            for n in config.sample_sizes:
                combos.add((k_perm_label, label, n))
    return combos


def expected_row_count(config: StageBConfig) -> int:
    return len(expected_combinations(config)) * config.replicates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--k-perm-labels", type=str, default=None,
        help="comma-separated subset of k_perm labels to run (default: all)",
    )
    parser.add_argument(
        "--labels", type=str, default=None,
        help="comma-separated subset of null-condition labels to run (default: all)",
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None,
        help="comma-separated subset of N values to run (default: all)",
    )
    parser.add_argument(
        "--no-report", action="store_true", help="skip the descriptive-verdict report (use for CI shards)"
    )
    arguments = parser.parse_args()

    k_perm_labels = tuple(arguments.k_perm_labels.split(",")) if arguments.k_perm_labels else None
    labels = tuple(arguments.labels.split(",")) if arguments.labels else None
    sample_sizes = (
        tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    )

    run_stage_b(
        load_config(arguments.config),
        arguments.output,
        max_workers=arguments.workers,
        k_perm_labels=k_perm_labels,
        labels=labels,
        sample_sizes=sample_sizes,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
