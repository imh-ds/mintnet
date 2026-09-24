"""Shared contracts for the reproducible CIN runner family."""

from __future__ import annotations

import csv
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import importlib.metadata as importlib_metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Mapping

# These assignments intentionally occur before importing NumPy.  The runner
# modules import this module before their numerical imports as well.
THREAD_ENVIRONMENT = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
for _name in THREAD_ENVIRONMENT:
    os.environ[_name] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from threadpoolctl import threadpool_info, threadpool_limits  # noqa: E402
import yaml  # noqa: E402


@dataclass(frozen=True)
class CINSeedBundle:
    """Independent random seeds for one full-grid dataset identity."""

    structure: int
    sample: int
    cin_fit: int
    comparator_fit: int
    stability: int


def derive_seed_bundle(
    master_seed: int,
    case_index: int,
    phase_index: int,
    replicate: int,
) -> CINSeedBundle:
    """Derive the fixed five-child seed bundle from full-grid coordinates."""

    root = np.random.SeedSequence(
        [int(master_seed), 9009, int(case_index), int(phase_index), int(replicate)]
    )
    children = root.spawn(5)
    values = [int(child.generate_state(1, dtype=np.uint32)[0]) for child in children]
    return CINSeedBundle(*values)


class IncrementalCsvWriter:
    """Append-and-flush CSV writer used to preserve partial shard evidence."""

    def __init__(self, path: Path, columns: tuple[str, ...]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.columns = tuple(columns)
        self._handle = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(
            self._handle,
            fieldnames=self.columns,
            extrasaction="raise",
            lineterminator="\n",
        )
        self._writer.writeheader()
        self._handle.flush()
        self._closed = False

    def append(self, row: Mapping[str, Any]) -> None:
        if self._closed:
            raise ValueError("cannot append to a closed CSV writer")
        self._writer.writerow({column: row.get(column, "") for column in self.columns})
        self._handle.flush()

    def flush(self) -> None:
        if not self._closed:
            self._handle.flush()

    def close(self) -> None:
        if not self._closed:
            self._handle.flush()
            self._handle.close()
            self._closed = True

    def __enter__(self) -> "IncrementalCsvWriter":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def thread_limits() -> AbstractContextManager[Any]:
    """Limit native numerical libraries to one thread for one fit."""

    return threadpool_limits(limits=1)


def _to_builtin(value: Any) -> Any:
    if is_dataclass(value):
        return _to_builtin(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_builtin(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_to_builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    """Load one mapping-valued YAML configuration."""

    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"configuration must be a mapping: {source}")
    return payload


def write_resolved_config(output_dir: Path, config_payload: Mapping[str, Any]) -> str:
    """Write stable full-grid YAML and return its exact byte hash."""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(
        _to_builtin(config_payload),
        sort_keys=True,
        default_flow_style=False,
    ).encode("utf-8")
    path = target_dir / "resolved_config.yaml"
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


def _package_versions() -> dict[str, str | None]:
    packages = ("numpy", "scipy", "scikit-learn", "pandas", "PyYAML", "threadpoolctl")
    result: dict[str, str | None] = {"python": sys.version.split()[0]}
    for package in packages:
        try:
            result[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            result[package] = None
    return result


def peak_rss_mb() -> float | None:
    """Return Linux process RSS in MB; Windows intentionally reports null."""

    if sys.platform != "linux":
        return None
    try:
        import resource

        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    except (ImportError, OSError):
        return None


def write_provenance(
    output_dir: Path,
    *,
    config_payload: Mapping[str, Any],
    source_path: Path,
    charter_path: Path | None,
    runtime_seconds: float,
    peak_rss_mb: float | None,
) -> None:
    """Write auditable shard metadata without participant-level observations."""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    environment = {name: os.environ.get(name) for name in THREAD_ENVIRONMENT}
    metadata = {
        "config": _to_builtin(config_payload),
        "config_sha256": sha256_file(Path(source_path)),
        "charter_sha256": sha256_file(Path(charter_path)) if charter_path else None,
        "git_commit": _git_revision(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": _package_versions(),
        "thread_settings": {
            "environment": environment,
            "threadpool_info": _to_builtin(threadpool_info()),
        },
        "cpu": platform.processor() or None,
        "runtime_seconds": float(runtime_seconds),
        "peak_rss_mb": peak_rss_mb,
    }
    (target_dir / "metadata.json").write_text(
        json.dumps(_to_builtin(metadata), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_pair_sidecar_name(
    case: str,
    phase: str,
    replicate: int,
    method: str,
    kind: str = "pairs",
) -> str:
    return f"{case}_{phase}_{int(replicate)}_{method}_{kind}.csv.gz"


def canonical_stability_sidecar_name(case: str, phase: str, replicate: int, method: str) -> str:
    return canonical_pair_sidecar_name(case, phase, replicate, method, "stability")


def write_gzip_frame(frame: pd.DataFrame, path: Path) -> int:
    """Write one sidecar and return its data-row count."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, compression="gzip", lineterminator="\n")
    return int(len(frame))


__all__ = [
    "CINSeedBundle",
    "IncrementalCsvWriter",
    "THREAD_ENVIRONMENT",
    "canonical_pair_sidecar_name",
    "canonical_stability_sidecar_name",
    "derive_seed_bundle",
    "load_yaml",
    "peak_rss_mb",
    "sha256_file",
    "thread_limits",
    "write_gzip_frame",
    "write_provenance",
    "write_resolved_config",
]
