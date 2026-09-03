"""Reporting companion for `mintnet.experiments.stage6c_c`, required by
the generic shard-aggregation contract. Delegates to
`mintnet.experiments.stage6c_reporting.write_stage_c_report`.
"""

from __future__ import annotations

from mintnet.experiments.stage6c_reporting import write_stage_c_report as write_report

__all__ = ["write_report"]
