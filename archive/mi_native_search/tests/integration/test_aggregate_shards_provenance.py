import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from aggregate_shards import aggregate  # noqa: E402

from mintnet.experiments.stage7c_retune import all_conditions, load_config, run_stage7c

_SMOKE_CONFIG = Path("configs/stage7c_retune_smoke.yaml")


def test_aggregate_shards_writes_provenance_files(tmp_path: Path) -> None:
    """D-061 follow-up: aggregate_shards.py previously dropped every
    shard's own metadata.json/resolved_config.yaml -- the combined
    artifact had raw evidence and a report but no provenance at all.
    This exercises the fix directly, not just via a full-suite sharding
    test that happens not to check for these files."""
    config = load_config(_SMOKE_CONFIG)

    shards_dir = tmp_path / "shards"
    shard_index = 0
    for condition in all_conditions(config):
        for n in config.sample_sizes:
            for batch in (0, 1):
                run_stage7c(
                    config, shards_dir / f"shard_{shard_index}",
                    conditions=(condition,), sample_sizes=(n,), batches=(batch,), write_report=False,
                )
                shard_index += 1

    aggregated_dir = tmp_path / "aggregated"
    aggregate("mintnet.experiments.stage7c_retune", _SMOKE_CONFIG, shards_dir, aggregated_dir)

    resolved_config_path = aggregated_dir / "resolved_config.yaml"
    metadata_path = aggregated_dir / "metadata.json"
    assert resolved_config_path.is_file()
    assert metadata_path.is_file()

    one_shard_config = (shards_dir / "shard_0" / "resolved_config.yaml").read_text(encoding="utf-8")
    assert resolved_config_path.read_text(encoding="utf-8") == one_shard_config

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["shard_count"] == shard_index
    assert metadata["total_runtime_seconds"] > 0
    assert "git_commit" in metadata
    assert "note" in metadata
