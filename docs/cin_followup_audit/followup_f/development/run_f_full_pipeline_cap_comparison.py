"""Run the predeclared paired F candidate comparison at caps 500 and 1,000."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn

from mintnet.experiments.cin_baseline import CASE_ORDER, load_config, run_baseline
from mintnet.experiments.cin_common import derive_seed_bundle
from mintnet.simulation import generate_case


ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "configs/cin_f_cap_full_pipeline_dev_20261004.yaml"
OUT_ROOT = ROOT / "docs/cin_followup_audit/followup_f/development/full_pipeline_cap_comparison_20261004"
REPLICATES = tuple(range(5000, 5100))
CAPS = (500, 1000)
FLOOR = 0.005
STRONG_EDGE_THRESHOLD = 0.01


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty result: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _characteristics(cap: int, config) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for replicate in REPLICATES:
        seeds = derive_seed_bundle(
            config.master_seed,
            CASE_ORDER.index("F"),
            0,
            replicate,
        )
        try:
            generated = generate_case(
                "F",
                structure_seed=seeds.structure,
                sample_seed=seeds.sample,
                n=config.n_overrides["F"],
                max_tries=cap,
            )
        except Exception as exc:  # preserve generator errors identity-by-identity.
            rows.append(
                {
                    "cap": cap,
                    "replicate": replicate,
                    "structure_seed": seeds.structure,
                    "sample_seed": seeds.sample,
                    "generation_status": "error",
                    "generator_attempts": getattr(exc, "attempts", ""),
                    "error_type": type(exc).__name__,
                    "frame_sha256": "",
                    "truth_edge_count": "",
                    "true_edge_cmi_min": "",
                    "true_edge_cmi_median": "",
                    "true_edge_cmi_max": "",
                    "strong_edge_count_0_01": "",
                    "node_level_count_min": "",
                    "node_level_count_max": "",
                    "node_level_cell_count_min": "",
                }
            )
            continue

        frame_values = generated.frame.astype(object).where(pd.notna(generated.frame), None)
        canonical_frame = json.dumps(
            {"columns": list(generated.frame.columns), "data": frame_values.values.tolist()},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        true_edge_cmi = np.asarray(
            [float(generated.population_cmi[edge]) for edge in sorted(generated.truth_edges)],
            dtype=np.float64,
        )
        if len(true_edge_cmi) != 10 or float(true_edge_cmi.min()) < FLOOR:
            raise AssertionError(
                f"accepted F/{replicate} violated the predeclared truth-edge contract"
            )
        level_counts = [
            generated.frame[column].value_counts(dropna=False).astype(int).tolist()
            for column in generated.frame.columns
        ]
        node_levels = [len(counts) for counts in level_counts]
        rows.append(
            {
                "cap": cap,
                "replicate": replicate,
                "structure_seed": seeds.structure,
                "sample_seed": seeds.sample,
                "generation_status": "complete",
                "generator_attempts": int(generated.meta["rejection_tries"]),
                "error_type": "",
                "frame_sha256": _sha256_bytes(canonical_frame),
                "truth_edge_count": len(generated.truth_edges),
                "true_edge_cmi_min": float(true_edge_cmi.min()),
                "true_edge_cmi_median": float(np.median(true_edge_cmi)),
                "true_edge_cmi_max": float(true_edge_cmi.max()),
                "strong_edge_count_0_01": int(np.sum(true_edge_cmi >= STRONG_EDGE_THRESHOLD)),
                "node_level_count_min": min(node_levels),
                "node_level_count_max": max(node_levels),
                "node_level_cell_count_min": min(min(counts) for counts in level_counts),
            }
        )
    return rows


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    config = load_config(CONFIG_PATH)
    if config.development_replicates != REPLICATES or config.master_seed != 20261004:
        raise AssertionError("the checked-in config differs from the predeclared cohort")

    config_bytes = CONFIG_PATH.read_bytes()
    source_revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    source_files = (
        ROOT / "src/mintnet/simulation/cin_networks.py",
        ROOT / "src/mintnet/experiments/cin_baseline.py",
        ROOT / "src/mintnet/experiments/cin_common.py",
        Path(__file__),
    )
    source_hashes = {
        str(path.relative_to(ROOT)).replace("\\", "/"): _sha256_bytes(path.read_bytes())
        for path in source_files
    }

    raw_by_cap: dict[int, pd.DataFrame] = {}
    characteristics_by_cap: dict[int, list[dict[str, object]]] = {}
    for cap in CAPS:
        run_dir = OUT_ROOT / f"cap-{cap}"
        expected_run_files = (
            run_dir / "raw_metrics.csv",
            run_dir / "metadata.json",
            run_dir / "resolved_config.yaml",
        )
        if run_dir.exists():
            missing = [path.name for path in expected_run_files if not path.is_file()]
            if missing:
                raise FileExistsError(
                    f"incomplete existing cap-{cap} run; refusing overwrite, missing {missing}"
                )
            raw_by_cap[cap] = pd.read_csv(run_dir / "raw_metrics.csv")
            resolved_text = (run_dir / "resolved_config.yaml").read_text(encoding="utf-8")
            if f"f_max_tries: {cap}" not in resolved_text:
                raise ValueError(f"existing cap-{cap} output has an unexpected resolved config")
        else:
            raw_by_cap[cap] = run_baseline(
                config,
                run_dir,
                cases=("F",),
                replicate_batches=("dev0",),
                write_report=True,
                f_max_tries=cap,
                support_aware_inner_splits=True,
            )
        frame = raw_by_cap[cap]
        if len(frame) != len(REPLICATES):
            raise AssertionError(f"cap {cap}: expected {len(REPLICATES)} rows, found {len(frame)}")
        if frame["replicate"].astype(int).tolist() != list(REPLICATES):
            raise AssertionError(f"cap {cap}: output identities differ from frozen development cohort")
        characteristics_path = OUT_ROOT / f"data_characteristics_cap_{cap}.csv"
        if characteristics_path.is_file():
            characteristics_by_cap[cap] = pd.read_csv(characteristics_path).to_dict("records")
        else:
            characteristics_by_cap[cap] = _characteristics(cap, config)
            _write_csv(characteristics_path, characteristics_by_cap[cap])

    paired: list[dict[str, object]] = []
    char_by_cap = {
        cap: {int(row["replicate"]): row for row in characteristics_by_cap[cap]}
        for cap in CAPS
    }
    for position, replicate in enumerate(REPLICATES):
        row_500 = raw_by_cap[500].iloc[position]
        row_1000 = raw_by_cap[1000].iloc[position]
        data_500 = char_by_cap[500][replicate]
        data_1000 = char_by_cap[1000][replicate]
        if data_500["generation_status"] == "complete":
            if data_1000["generation_status"] != "complete":
                raise AssertionError(f"cap 1,000 rejected identity accepted by cap 500: F/{replicate}")
            if data_500["frame_sha256"] != data_1000["frame_sha256"]:
                raise AssertionError(f"accepted data changed across caps for F/{replicate}")
            if data_500["generator_attempts"] != data_1000["generator_attempts"]:
                raise AssertionError(f"generator attempt count changed across caps for F/{replicate}")
        paired.append(
            {
                "replicate": replicate,
                "status_cap_500": row_500["status"],
                "status_cap_1000": row_1000["status"],
                "generation_status_cap_500": data_500["generation_status"],
                "generation_status_cap_1000": data_1000["generation_status"],
                "generator_attempts_cap_500": data_500["generator_attempts"],
                "generator_attempts_cap_1000": data_1000["generator_attempts"],
                "same_frame_when_accepted_by_both": (
                    data_500["frame_sha256"] == data_1000["frame_sha256"]
                    if data_500["generation_status"] == "complete"
                    and data_1000["generation_status"] == "complete"
                    else ""
                ),
                "elapsed_seconds_cap_500": row_500["elapsed_seconds"],
                "elapsed_seconds_cap_1000": row_1000["elapsed_seconds"],
                "point_fit_seconds_cap_500": row_500["point_fit_seconds"],
                "point_fit_seconds_cap_1000": row_1000["point_fit_seconds"],
                "n_pairs_complete_cap_500": row_500["n_pairs_complete"],
                "n_pairs_complete_cap_1000": row_1000["n_pairs_complete"],
                "n_pairs_total_cap_500": row_500["n_pairs_total"],
                "n_pairs_total_cap_1000": row_1000["n_pairs_total"],
            }
        )
    _write_csv(OUT_ROOT / "paired_cap_comparison.csv", paired)

    metadata = {
        "protocol": "cin-f-cap-full-pipeline-dev-20261004",
        "source_revision": source_revision,
        "config_sha256": _sha256_bytes(config_bytes),
        "source_sha256": source_hashes,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit-learn": sklearn.__version__,
            "PyYAML": importlib.metadata.version("PyYAML"),
            "threadpoolctl": importlib.metadata.version("threadpoolctl"),
        },
        "master_seed": config.master_seed,
        "case": "F",
        "phase": "development",
        "replicates": [REPLICATES[0], REPLICATES[-1]],
        "n_identities": len(REPLICATES),
        "caps": list(CAPS),
        "support_aware_inner_splits": True,
        "validation_batch_dispatched": False,
        "summary": {},
    }
    for cap in CAPS:
        frame = raw_by_cap[cap]
        status_counts = frame["status"].value_counts(dropna=False).to_dict()
        characteristics = characteristics_by_cap[cap]
        complete_data = [row for row in characteristics if row["generation_status"] == "complete"]
        run_metadata = json.loads((OUT_ROOT / f"cap-{cap}" / "metadata.json").read_text(encoding="utf-8"))
        metadata["summary"][str(cap)] = {
            "run_git_commit": run_metadata.get("git_commit"),
            "status_counts": {str(key): int(value) for key, value in status_counts.items()},
            "generated_identities": len(complete_data),
            "generator_attempt_total": int(sum(int(row["generator_attempts"]) for row in complete_data)),
            "attempts_consumed_total_including_errors": int(
                pd.to_numeric(frame["generator_attempts"], errors="coerce").fillna(0).sum()
            ),
            "median_generator_attempts": float(np.median([int(row["generator_attempts"]) for row in complete_data])) if complete_data else None,
            "median_elapsed_seconds": float(frame["elapsed_seconds"].median()),
            "median_point_fit_seconds": float(frame["point_fit_seconds"].median()),
            "median_true_edge_cmi": float(np.median([float(row["true_edge_cmi_median"]) for row in complete_data])) if complete_data else None,
            "total_runtime_seconds": run_metadata.get("total_runtime_seconds", run_metadata.get("runtime_seconds")),
        }
    metadata["paired_status_counts"] = (
        raw_by_cap[500]["status"].astype(str) + "->" + raw_by_cap[1000]["status"].astype(str)
    ).value_counts().to_dict()
    metadata["shared_successful_frames_identical"] = all(
        row["same_frame_when_accepted_by_both"] is True for row in paired
        if row["generation_status_cap_500"] == "complete"
    )
    (OUT_ROOT / "run_manifest.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
