from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.aggregate_shards import _write_provenance


def _write_shard(root: Path, *, git_commit: str = "abc123") -> Path:
    root.mkdir(parents=True)
    resolved = root / "resolved_config.yaml"
    resolved.write_text("name: fixture\n", encoding="utf-8")
    resolved_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
    metadata = {
        "config": {"name": "fixture", "charter": "charter.md"},
        "config_sha256": resolved_hash,
        "source_config_sha256": "source-config-hash",
        "charter_sha256": "charter-hash",
        "git_commit": git_commit,
        "python": "3.12.14",
        "platform": "fixture-platform",
        "package_versions": {"numpy": "2.0"},
        "thread_settings": {"environment": {"OMP_NUM_THREADS": "1"}, "threadpool_info": []},
        "cpu": "fixture-cpu",
        "runtime_seconds": 2.0,
        "peak_rss_mb": 100.0,
    }
    (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    pd.DataFrame([{"charter_sha256": "charter-hash"}]).to_csv(
        root / "raw_metrics.csv", index=False
    )
    return root / "raw_metrics.csv"


def test_provenance_rejects_shards_from_different_revisions(tmp_path: Path) -> None:
    first = _write_shard(tmp_path / "shard-a")
    second = _write_shard(tmp_path / "shard-b", git_commit="def456")

    with pytest.raises(ValueError, match="git_commit"):
        _write_provenance(
            [first, second],
            tmp_path / "aggregate",
            expected_source_config_sha256="source-config-hash",
        )


def test_provenance_requires_every_shard_metadata_file(tmp_path: Path) -> None:
    shard = _write_shard(tmp_path / "shard")
    (shard.parent / "metadata.json").unlink()

    with pytest.raises(FileNotFoundError, match="metadata"):
        _write_provenance(
            [shard],
            tmp_path / "aggregate",
            expected_source_config_sha256="source-config-hash",
        )


def test_aggregate_provenance_preserves_per_shard_environment_and_hashes(tmp_path: Path) -> None:
    shard = _write_shard(tmp_path / "shard")
    output = tmp_path / "aggregate"
    output.mkdir()
    raw_path = output / "raw_metrics.csv"
    raw_path.write_text("charter_sha256\ncharter-hash\n", encoding="utf-8")

    _write_provenance(
        [shard],
        output,
        expected_source_config_sha256="source-config-hash",
    )

    aggregate = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert aggregate["provenance_validated"] is True
    assert aggregate["aggregated_raw_metrics_sha256"] == hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert aggregate["shards"][0]["package_versions"] == {"numpy": "2.0"}
    assert aggregate["shards"][0]["thread_settings"]["environment"]["OMP_NUM_THREADS"] == "1"
    assert aggregate["shards"][0]["cpu"] == "fixture-cpu"
    assert aggregate["shards"][0]["peak_rss_mb"] == 100.0
