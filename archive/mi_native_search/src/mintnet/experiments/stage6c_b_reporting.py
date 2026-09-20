"""Reporting companion for `mintnet.experiments.stage6c_b`, required by
the generic shard-aggregation contract (`scripts/aggregate_shards.py`
imports `<module>_reporting` alongside `<module>`). Delegates to
`mintnet.experiments.stage6c_reporting.write_stage_b_report`, the same
report a local `--stage b` run produces.
"""

from __future__ import annotations

from mintnet.experiments.stage6c_reporting import write_stage_b_report as write_report

__all__ = ["write_report"]
