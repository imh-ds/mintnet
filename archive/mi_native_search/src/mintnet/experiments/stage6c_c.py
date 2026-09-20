"""Sharding-friendly entry point for Stage 6c/6d's Stage C (power at
the calibrated setting) -- mirrors `mintnet.experiments.stage6c_b`'s
own role for Stage B. See docs/stage6c_charter.md, docs/stage6d_charter.md,
and .github/workflows/sharded_benchmark.yml's generic dispatch contract.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from mintnet.experiments.stage6c import ALT_CONDITIONS, StageCConfig, run_stage_c


def load_config(path: Path) -> StageCConfig:
    with path.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    block = values["stage_c"]
    return StageCConfig(
        k_cmi=int(block["k_cmi"]),
        k_perm_label=str(block["k_perm_label"]),
        sample_sizes=tuple(int(v) for v in block["sample_sizes"]),
        replicates=int(block["replicates"]),
        permutations=int(block["permutations"]),
        alphas=tuple(float(v) for v in block["alphas"]),
        master_seed=int(block["master_seed"]),
        source_path=path.resolve(),
    )


COMBINATION_COLUMNS: tuple[str, ...] = ("label", "n")


def expected_combinations(config: StageCConfig) -> set[tuple[str, int]]:
    return {(str(condition["label"]), n) for condition in ALT_CONDITIONS for n in config.sample_sizes}


def expected_row_count(config: StageCConfig) -> int:
    return len(expected_combinations(config)) * config.replicates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--labels", type=str, default=None,
        help="comma-separated subset of alt-condition labels to run (default: all)",
    )
    parser.add_argument(
        "--sample-sizes", type=str, default=None,
        help="comma-separated subset of N values to run (default: all)",
    )
    parser.add_argument(
        "--no-report", action="store_true", help="skip the descriptive-verdict report (use for CI shards)"
    )
    arguments = parser.parse_args()

    labels = tuple(arguments.labels.split(",")) if arguments.labels else None
    sample_sizes = (
        tuple(int(v) for v in arguments.sample_sizes.split(",")) if arguments.sample_sizes else None
    )

    run_stage_c(
        load_config(arguments.config),
        arguments.output,
        max_workers=arguments.workers,
        labels=labels,
        sample_sizes=sample_sizes,
        write_report=not arguments.no_report,
    )


if __name__ == "__main__":
    main()
