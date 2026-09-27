"""Validate and combine CIN pair/stability sidecars."""

from __future__ import annotations

import argparse
from pathlib import Path
import hashlib
import itertools
import json
from decimal import Decimal, InvalidOperation
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


def _assert_identity_columns(
    table: pd.DataFrame, identity: tuple[Any, ...], columns: tuple[str, ...]
) -> pd.DataFrame:
    """Reject sidecar rows that claim a different raw identity, filling omitted fields."""
    result = table.copy()
    for column, value in zip(columns, identity):
        if column in result:
            if result[column].isna().any() or result[column].astype(str).ne(str(value)).any():
                raise ValueError(f"sidecar identity mismatch for {column}: expected {value!r}")
        else:
            result.insert(0, column, value)
    return result


def _json_list(value: Any, label: str) -> list[Any]:
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {label} metadata") from exc
    if not isinstance(decoded, list):
        raise ValueError(f"invalid {label} metadata")
    return decoded


def _exact_integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid {label}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {label}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"invalid {label}")
    return int(number)


def _validate_pairs(table: pd.DataFrame, raw_row: pd.Series, identity: tuple[Any, ...]) -> pd.DataFrame:
    expected_count = int(raw_row["p"]) * (int(raw_row["p"]) - 1) // 2
    if len(table) != expected_count:
        raise ValueError(f"pair row count mismatch for {identity}: expected {expected_count}, got {len(table)}")
    if not {"node_i", "node_j"} <= set(table.columns):
        raise ValueError(f"pair sidecar is missing pair identity columns for {identity}")
    observed = list(zip(table["node_i"].astype(str), table["node_j"].astype(str)))
    if len(set(observed)) != len(observed):
        raise ValueError(f"duplicate pair identity in sidecar for {identity}")
    if "node_order_json" not in raw_row or pd.isna(raw_row.get("node_order_json")):
        raise ValueError(f"canonical node order metadata is missing for {identity}")
    node_order = _json_list(raw_row["node_order_json"], "node order")
    if len(node_order) != int(raw_row["p"]) or len(set(map(str, node_order))) != len(node_order):
        raise ValueError(f"invalid canonical node order for {identity}")
    expected = {
        (str(left), str(right))
        for left, right in itertools.combinations(map(str, node_order), 2)
    }
    if set(observed) != expected:
        raise ValueError(f"pair identities do not match canonical node pairs for {identity}")
    identity_columns = IDENTITY_COLUMNS if "case" in raw_row else ("cell", "repeat", "method")
    return _assert_identity_columns(table, identity, identity_columns)


def _validate_stability(
    table: pd.DataFrame, raw_row: pd.Series, identity: tuple[Any, ...]
) -> pd.DataFrame:
    required = {
        "stability_repeats_requested", "stability_repeat_seeds_json",
        "stability_completed_repeat_ids_json", "stability_node_order_json", "stability_status",
    }
    if not required <= set(raw_row.index) or any(pd.isna(raw_row.get(column)) for column in required):
        raise ValueError(f"stability request metadata is missing for {identity}")
    requested = int(raw_row["stability_repeats_requested"])
    seeds = [_exact_integer(value, "stability seed") for value in _json_list(raw_row["stability_repeat_seeds_json"], "stability seeds")]
    completed_values = [_exact_integer(value, "completed stability repeat id") for value in _json_list(raw_row["stability_completed_repeat_ids_json"], "completed stability repeats")]
    node_order = [str(value) for value in _json_list(raw_row["stability_node_order_json"], "stability node order")]
    raw_node_order = [str(value) for value in _json_list(raw_row.get("node_order_json"), "node order")]
    status = str(raw_row["stability_status"])
    if requested < 1 or len(seeds) != requested or len(set(completed_values)) != len(completed_values):
        raise ValueError(f"invalid stability repeat request metadata for {identity}")
    if any(value < 0 or value >= requested for value in completed_values):
        raise ValueError(f"invalid completed stability repeat id for {identity}")
    if node_order != raw_node_order or len(node_order) != int(raw_row["p"]):
        raise ValueError(f"stability canonical node order mismatch for {identity}")
    expected_pairs = {
        (left, right) for left, right in itertools.combinations(node_order, 2)
    }
    needed = {"repeat_id", "repeat_seed", "node_i", "node_j", "status"}
    if not needed <= set(table.columns):
        raise ValueError(f"stability sidecar is missing identity columns for {identity}")
    keys: set[tuple[int, str, str]] = set()
    observed_by_repeat: dict[int, set[tuple[str, str]]] = {}
    interrupted_by_repeat: set[int] = set()
    for record in table.loc[:, ["repeat_id", "repeat_seed", "node_i", "node_j", "status"]].to_dict(orient="records"):
        repeat_id = _exact_integer(record["repeat_id"], "stability repeat id")
        repeat_seed = _exact_integer(record["repeat_seed"], "stability repeat seed")
        if repeat_id < 0 or repeat_id >= requested or repeat_seed != seeds[repeat_id]:
            raise ValueError(f"stability repeat identity or seed mismatch for {identity}")
        pair = (str(record["node_i"]), str(record["node_j"]))
        if pair not in expected_pairs:
            raise ValueError(f"stability pair identity is not canonical for {identity}")
        key = (repeat_id, *pair)
        if key in keys:
            raise ValueError(f"duplicate stability repeat/pair identity for {identity}")
        keys.add(key)
        observed_by_repeat.setdefault(repeat_id, set()).add(pair)
        if str(record["status"]) == "interrupted":
            interrupted_by_repeat.add(repeat_id)
    completed = set(completed_values)
    for repeat_id in completed:
        if observed_by_repeat.get(repeat_id) != expected_pairs or repeat_id in interrupted_by_repeat:
            raise ValueError(f"completed stability repeat coverage disagrees with sidecar for {identity}")
    for repeat_id, pairs in observed_by_repeat.items():
        if repeat_id not in completed and pairs == expected_pairs and repeat_id not in interrupted_by_repeat:
            raise ValueError(f"stability repeat coverage disagrees with completion metadata for {identity}")
    all_requested = set(range(requested))
    if status == "complete":
        if completed != all_requested:
            raise ValueError(f"complete stability status lacks requested repeats for {identity}")
    elif status not in {"interrupted", "budget_not_started", "unsupported_repeat_request"} or completed == all_requested:
        raise ValueError(f"stability partial status disagrees with completed repeats for {identity}")
    identity_columns = IDENTITY_COLUMNS if "case" in raw_row else ("cell", "repeat", "method")
    return _assert_identity_columns(table, identity, identity_columns)


def _raw_promises(raw: pd.DataFrame) -> dict[tuple[Any, ...], dict[str, tuple[str, pd.Series]]]:
    promises: dict[tuple[Any, ...], dict[str, tuple[str, pd.Series]]] = {}
    for _, row in raw.iterrows():
        identity = _identity_from_raw(row)
        if identity in promises:
            raise ValueError(f"duplicate raw identity: {identity}")
        entry: dict[str, tuple[str, pd.Series]] = {}
        for column, kind in (("pair_sidecar_file", "pairs"), ("stability_sidecar_file", "stability")):
            if column in raw.columns and pd.notna(row.get(column)) and str(row[column]).strip():
                entry[kind] = (str(row[column]), row)
        promises[identity] = entry
    return promises


def aggregate_sidecars(
    shards_dir: Path,
    output_dir: Path,
    *,
    phase: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate all promised sidecars, then write combined pair/stability tables."""

    if phase not in {None, "development", "validation"}:
        raise ValueError(f"unknown phase: {phase}")
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
        if phase is not None:
            if "phase" not in raw.columns:
                raise ValueError(f"raw metrics in {root} do not identify a phase")
            raw = raw.loc[raw["phase"] == phase]
            if raw.empty:
                raise ValueError(f"no {phase} raw rows in {root}")
        promises = _raw_promises(raw)
        manifest_path = root / "sidecar_manifest.csv"
        if not manifest_path.exists():
            actual_files = {path.name for path in (root / "sidecars").glob("*.csv.gz")} if (root / "sidecars").exists() else set()
            if actual_files:
                raise ValueError(f"orphan sidecar files in {root}: {sorted(actual_files)}")
            if any(promises.values()):
                raise FileNotFoundError(f"missing sidecar_manifest.csv in {root}")
            continue
        manifest = pd.read_csv(manifest_path)
        listed_files: set[str] = set()
        for _, manifest_row in manifest.iterrows():
            file_name = Path(str(manifest_row["file"])).name
            listed_files.add(file_name)
            if phase is not None and str(manifest_row.get("phase")) != phase:
                continue
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
                table = _validate_pairs(table, raw_row, identity)
                all_pairs.append(table)
            else:
                table = _validate_stability(table, raw_row, identity)
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
    parser.add_argument("--phase", choices=("development", "validation"))
    args = parser.parse_args(argv)
    aggregate_sidecars(args.shards_dir, args.output, phase=args.phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
