r"""Generic combiner for multiple SEPARATE sharded-benchmark dispatches
of the same experiment. See D-058: GitHub Actions caps a single matrix
dispatch at 256 jobs, which a full one-replicate-per-shard sweep can
exceed well before reaching a real charter's own needed replicate
count. The fix is multiple dispatches -- each with its own distinct
`master_seed` and its own complete, self-consistent replicate range
(so each dispatch's own built-in `aggregate` job, via
`aggregate_shards.py`, succeeds on its own) -- combined post-hoc by
this script into one evidence set spanning all of them.

Works on any module already opted into the generic shard-aggregation
contract (`load_config`, `expected_row_count`, `expected_combinations`,
`COMBINATION_COLUMNS`, a `<module>_reporting` companion) -- the same
contract `aggregate_shards.py` uses -- not just
`mintnet.experiments.stage7_isolation_timing`, its first user.

Each dispatch is specified as a paired `--dispatch-config <path>
--dispatch-dir <dir>` -- the same config file used to `gh workflow run`
that dispatch, and the local directory `gh run download <run id> -n
aggregated-benchmark` saved that dispatch's own already-aggregated
`raw_metrics.csv` into. (Not a single colon-joined string: Windows
paths already contain a drive-letter colon, e.g. `C:\...`, which would
collide with a `:`-delimited spec.) Repeat both flags once per
dispatch, in matching order. Order matters: replicate numbers are
remapped so dispatch N's own local replicates `[0, config.replicates)`
become global replicates `[offset_N, offset_N + config.replicates)`,
offsets assigned in the order dispatches are given on the command
line -- not by `master_seed` or any other implicit ordering.

All dispatches must share an identical design (every config field
except `master_seed`, `replicates`, and the config file's own path) --
checked explicitly; a real mismatch (e.g. accidentally combining two
different `alpha` settings) is refused, not silently averaged over.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
from pathlib import Path
from types import ModuleType

import pandas as pd


def _load_module(module_path: str) -> tuple[ModuleType, ModuleType]:
    runner = importlib.import_module(module_path)
    reporting = importlib.import_module(f"{module_path}_reporting")
    return runner, reporting


def _assert_same_design(configs: list[object], config_paths: list[Path]) -> None:
    exempt = {"master_seed", "replicates", "source_path"}
    reference = configs[0]
    reference_fields = {f.name: getattr(reference, f.name) for f in dataclasses.fields(reference) if f.name not in exempt}
    for config, path in zip(configs[1:], config_paths[1:]):
        for name, value in reference_fields.items():
            other = getattr(config, name)
            if other != value:
                raise SystemExit(
                    f"dispatch configs disagree on field '{name}': {config_paths[0]}={value!r} vs {path}={other!r} "
                    "-- refusing to combine dispatches with a different design"
                )


def combine(module_path: str, config_paths: list[Path], artifact_dirs: list[Path], output_dir: Path) -> pd.DataFrame:
    if len(config_paths) != len(artifact_dirs):
        raise SystemExit(
            f"got {len(config_paths)} --dispatch-config value(s) but {len(artifact_dirs)} --dispatch-dir "
            "value(s) -- these must be paired one-to-one, in matching order"
        )
    if not config_paths:
        raise SystemExit("at least one --dispatch-config/--dispatch-dir pair is required")
    runner, reporting = _load_module(module_path)
    configs = [runner.load_config(config_path) for config_path in config_paths]
    _assert_same_design(configs, config_paths)

    combination_columns = list(runner.COMBINATION_COLUMNS)
    if "replicate" not in combination_columns:
        raise SystemExit(
            f"{module_path}'s own COMBINATION_COLUMNS ({combination_columns}) has no 'replicate' column -- "
            "this combiner assumes replicate identity is part of the module's own combination key"
        )

    manifest: list[dict[str, object]] = []
    frames: list[pd.DataFrame] = []
    offset = 0
    for config, config_path, artifact_dir in zip(configs, config_paths, artifact_dirs):
        raw_path = artifact_dir / "raw_metrics.csv"
        if not raw_path.is_file():
            raise SystemExit(f"no raw_metrics.csv found under {artifact_dir}")
        raw = pd.read_csv(raw_path)

        expected_rows = runner.expected_row_count(config)
        if len(raw) != expected_rows:
            raise SystemExit(
                f"dispatch at {artifact_dir} has {len(raw)} rows, expected {expected_rows} for its own config "
                f"({config_path}) -- this dispatch's own coverage is incomplete, combine only complete dispatches"
            )
        combos = set(raw[combination_columns].itertuples(index=False, name=None))
        expected_combos = runner.expected_combinations(config)
        if combos != expected_combos:
            raise SystemExit(f"dispatch at {artifact_dir} does not cover its own expected combinations")

        raw = raw.copy()
        raw["replicate"] = raw["replicate"] + offset
        manifest.append(
            {
                "config_path": str(config_path),
                "artifact_dir": str(artifact_dir),
                "master_seed": config.master_seed,
                "local_replicates": config.replicates,
                "global_replicate_start": offset,
                "global_replicate_end": offset + config.replicates,
            }
        )
        frames.append(raw)
        offset += config.replicates

    combined_raw = pd.concat(frames, ignore_index=True)
    combined_config = dataclasses.replace(configs[0], replicates=offset)

    expected_rows = runner.expected_row_count(combined_config)
    if len(combined_raw) != expected_rows:
        raise SystemExit(
            f"combined {len(combined_raw)} rows across {len(configs)} dispatch(es), expected {expected_rows} "
            "for the combined replicate count -- a dispatch is missing or duplicated"
        )
    combos = set(combined_raw[combination_columns].itertuples(index=False, name=None))
    expected_combos = runner.expected_combinations(combined_config)
    if combos != expected_combos:
        missing = expected_combos - combos
        raise SystemExit(f"combined dispatches do not cover every combination -- missing: {missing}")
    dedup_columns = combination_columns
    duplicate_keys = combined_raw.duplicated(subset=dedup_columns)
    if duplicate_keys.any():
        raise SystemExit(f"{int(duplicate_keys.sum())} duplicate rows across combined dispatches (key: {dedup_columns})")

    output_dir.mkdir(parents=True, exist_ok=True)
    combined_raw.to_csv(output_dir / "raw_metrics.csv", index=False)
    (output_dir / "combined_manifest.json").write_text(
        json.dumps({"module": module_path, "total_replicates": offset, "dispatches": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    reporting.write_report(combined_raw, combined_config, output_dir)
    return combined_raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--module", required=True,
        help="import path of the shardable runner module, e.g. mintnet.experiments.stage7_isolation_timing",
    )
    parser.add_argument(
        "--dispatch-config", required=True, action="append", type=Path,
        help="config file used for one dispatch; repeat once per dispatch, paired in order with --dispatch-dir",
    )
    parser.add_argument(
        "--dispatch-dir", required=True, action="append", type=Path,
        help="downloaded 'aggregated-benchmark' artifact directory for the matching --dispatch-config",
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    combine(arguments.module, arguments.dispatch_config, arguments.dispatch_dir, arguments.output)


if __name__ == "__main__":
    main()
