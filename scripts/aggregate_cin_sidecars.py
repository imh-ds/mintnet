"""Validate and combine CIN pair/stability sidecars."""

from __future__ import annotations

import argparse
from pathlib import Path
import hashlib
from typing import Any

import pandas as pd


IDENTITY_COLUMNS = ("case", "phase", "replicate", "method")
MANIFEST_COLUMNS = ("file", "case", "cell", "phase", "replicate", "repeat", "method", "kind", "n_rows", "sha256")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _roots(shards_dir: Path) -> list[Path]:
    root = Path(shards_dir)
    if (root / "raw_metrics.csv").exists():
        return [root]
    result = sorted(path for path in root.iterdir() if path.is_dir() and (path / "raw_metrics.csv").exists())
    if not result:
        raise FileNotFoundError(f"no raw_metrics.csv found below {root}")
    return result


def _identity_from_raw(row: pd.Series) -> tuple[Any, ...]:
    if "case" in row:
        return (str(row["case"]), str(row["phase"]), int(row["replicate"]), str(row["method"]))
    return (str(row["cell"]), int(row["repeat"]), str(row.get("method", "cin")))


def _identity_from_manifest(row: pd.Series) -> tuple[Any, ...]:
    if pd.notna(row.get("case")):
        return (str(row["case"]), str(row["phase"]), int(row["replicate"]), str(row["method"]))
    return (str(row["cell"]), int(row["repeat"]), str(row["method"]))


def _sidecar_path(root: Path, file_value: str) -> Path:
    path = Path(str(file_value))
    candidate = root / path if path.parts and path.parts[0] == "sidecars" else root / "sidecars" / path.name
    return candidate


def _raw_promises(raw: pd.DataFrame) -> dict[tuple[Any, ...], dict[str, tuple[str, pd.Series]]]:
    promises: dict[tuple[Any, ...], dict[str, tuple[str, pd.Series]]] = {}
    for _, row in raw.iterrows():
        identity = _identity_from_raw(row)
        entry: dict[str, tuple[str, pd.Series]] = {}
        for column, kind in (("pair_sidecar_file", "pairs"), ("stability_sidecar_file", "stability")):
            if column in raw.columns and pd.notna(row.get(column)) and str(row[column]).strip():
                entry[kind] = (str(row[column]), row)
        promises[identity] = entry
    return promises


def aggregate_sidecars(shards_dir: Path, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate all promised sidecars, then write combined pair/stability tables."""

    roots = _roots(Path(shards_dir))
    target = Path(output_dir)
    (target / "sidecars").mkdir(parents=True, exist_ok=True)
    all_pairs: list[pd.DataFrame] = []
    all_stability: list[pd.DataFrame] = []
    combined_manifest: list[dict[str, Any]] = []
    seen_manifest: set[tuple[Any, ...]] = set()
    seen_promises: set[tuple[Any, ...]] = set()
    for root in roots:
        raw = pd.read_csv(root / "raw_metrics.csv")
        promises = _raw_promises(raw)
        manifest_path = root / "sidecar_manifest.csv"
        if not manifest_path.exists():
            if any(promises.values()):
                raise FileNotFoundError(f"missing sidecar_manifest.csv in {root}")
            continue
        manifest = pd.read_csv(manifest_path)
        listed_files: set[str] = set()
        for _, manifest_row in manifest.iterrows():
            file_name = Path(str(manifest_row["file"])).name
            listed_files.add(file_name)
            kind = str(manifest_row["kind"])
            identity = _identity_from_manifest(manifest_row)
            key = (*identity, kind)
            if key in seen_manifest:
                raise ValueError(f"duplicate sidecar identity: {key}")
            seen_manifest.add(key)
            sidecar_path = _sidecar_path(root, file_name)
            if not sidecar_path.exists():
                raise FileNotFoundError(f"missing sidecar {file_name} for {identity}")
            expected_hash = str(manifest_row["sha256"])
            actual_hash = _sha256(sidecar_path)
            if actual_hash != expected_hash:
                raise ValueError(f"sha256 mismatch for sidecar {file_name}")
            table = pd.read_csv(sidecar_path, compression="gzip")
            declared_rows = int(manifest_row["n_rows"])
            if len(table) != declared_rows:
                raise ValueError(f"row count mismatch for sidecar {file_name}")
            if identity not in promises:
                raise ValueError(f"sidecar {file_name} has no matching raw identity {identity}")
            promise = promises[identity].get(kind)
            if promise is None:
                raise ValueError(f"sidecar {file_name} is not promised by raw identity {identity}")
            if Path(promise[0]).name != file_name:
                raise ValueError(f"sidecar filename mismatch for raw identity {identity}")
            seen_promises.add(key)
            raw_row = promise[1]
            if kind == "pairs":
                expected_pairs = int(raw_row["p"]) * (int(raw_row["p"]) - 1) // 2
                if len(table) != expected_pairs:
                    raise ValueError(f"pair row count mismatch for {identity}: expected {expected_pairs}, got {len(table)}")
                for column, value in zip(("case", "phase", "replicate", "method"), identity if "case" in raw_row else (None, None, None, None)):
                    if value is not None and column not in table:
                        table.insert(0, column, value)
                all_pairs.append(table)
            else:
                if "repeat_id" in table and len(table["repeat_id"].unique()) * (int(raw_row["p"]) * (int(raw_row["p"]) - 1) // 2) != len(table):
                    raise ValueError(f"stability row count mismatch for {identity}")
                if "case" in raw_row:
                    for column, value in zip(IDENTITY_COLUMNS, identity):
                        if column not in table:
                            table.insert(0, column, value)
                all_stability.append(table)
            combined_manifest.append({**{column: manifest_row.get(column) for column in MANIFEST_COLUMNS}, "file": file_name})
        actual_files = {path.name for path in (root / "sidecars").glob("*.csv.gz")} if (root / "sidecars").exists() else set()
        orphaned = actual_files - listed_files
        if orphaned:
            raise ValueError(f"orphan sidecar files in {root}: {sorted(orphaned)}")
        expected_promises = {(*identity, kind) for identity, entry in promises.items() for kind in entry}
        missing_promises = expected_promises - seen_promises
        if missing_promises:
            raise FileNotFoundError(f"promised sidecars missing: {sorted(missing_promises)}")

    pairs = pd.concat(all_pairs, ignore_index=True) if all_pairs else pd.DataFrame()
    stability = pd.concat(all_stability, ignore_index=True) if all_stability else pd.DataFrame()
    if not pairs.empty:
        pairs.to_csv(target / "sidecars" / "pairs_all.csv.gz", index=False, compression="gzip", lineterminator="\n")
    if not stability.empty:
        stability.to_csv(target / "sidecars" / "stability_all.csv.gz", index=False, compression="gzip", lineterminator="\n")
    pd.DataFrame(combined_manifest).to_csv(target / "sidecars" / "sidecar_manifest.csv", index=False, lineterminator="\n")
    return pairs, stability


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    aggregate_sidecars(args.shards_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
