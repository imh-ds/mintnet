"""Gate evaluation and evidence rendering for the Stage 7 isolation-
tier evidence run. Delegates the actual gate/aggregation/calibration
logic to `mintnet.experiments.stage1b_reporting`'s own already-
validated functions -- `Stage7IsolationConfig` deliberately carries
every field name those functions read (`sample_sizes`, `strengths`,
`alphas`, `development_replicates`, `validation_replicates`,
`minimum_indirect_prune_tpr`, `maximum_triangle_true_edge_prune_fpr`),
and this runner's own raw-evidence columns match Stage 1b's schema
wherever those functions read a column (`motif`, `n`, `strength`,
`alpha`, `replicate`, `status`, `indirect_prune_tpr`,
`true_edge_prune_fpr`, `perfect_recovery`, `elapsed_seconds`,
`confidence_01`/`02`/`12`) -- so the identical, already-tested gate
logic applies without re-implementing or re-testing it here. See
docs/stage7_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1b_reporting import aggregate_stage1b, compute_calibration, evaluate_stage1b_gate
from mintnet.experiments.stage7_isolation import Stage7IsolationConfig


def write_report(raw: pd.DataFrame, config: Stage7IsolationConfig, output_dir: Path) -> object:
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage1b(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage1b_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps(asdict(decision), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )

    calibration = compute_calibration(raw, config)
    calibration.to_csv(output_dir / "calibration_summary.csv", index=False)

    selected = "None" if decision.selected_alpha_pair is None else ", ".join(map(str, decision.selected_alpha_pair))
    failures = "None" if not decision.failures else ", ".join(decision.failures)
    (output_dir / "stage7_isolation_report.md").write_text(
        "# Stage 7 Isolation-Tier Evidence Report (mi-native)\n\n"
        f"Decision: **{decision.status}**\n\n"
        f"Selected development alpha pair: `{selected}`\n\n"
        f"Failed criteria: {failures}\n\n"
        f"k_CMI={config.k_cmi}, k_perm={config.k_perm}, permutations={config.permutations} "
        "(D-056/D-057's own calibrated setting).\n\n"
        "Gate logic delegated to `mintnet.experiments.stage1b_reporting`'s own already-"
        "validated functions -- see `docs/stage7_charter.md`'s own selection-and-gate "
        "section for the frozen criteria (identical to Stage 1's own: chain/fork indirect-"
        "edge pruning TPR >= 0.80, triangle true-edge retention FPR <= 0.10).\n\n"
        "See `aggregate_metrics.csv`, `decision.json`, and `calibration_summary.csv` "
        "for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
