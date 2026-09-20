"""Gate evaluation and evidence rendering for the Stage 7e isolation-
tier evidence run. Delegates the actual gate/aggregation/calibration
logic to `mintnet.experiments.stage1b_reporting`'s own already-
validated functions -- identical delegation to
`mintnet.experiments.stage7_isolation_reporting`'s own, since
`Stage7eIsolationConfig` carries every field name those functions read
and this runner's own raw-evidence schema is unchanged from Stage 7's
own. See docs/stage7e_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from mintnet.experiments.stage1b_reporting import aggregate_stage1b, compute_calibration, evaluate_stage1b_gate
from mintnet.experiments.stage7e_isolation import Stage7eIsolationConfig


def write_report(raw: pd.DataFrame, config: Stage7eIsolationConfig, output_dir: Path) -> object:
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
    (output_dir / "stage7e_isolation_report.md").write_text(
        "# Stage 7e Isolation-Tier Evidence Report (mi-native)\n\n"
        f"Decision: **{decision.status}**\n\n"
        f"Selected development alpha pair: `{selected}`\n\n"
        f"Failed criteria: {failures}\n\n"
        f"degree={config.degree}, ridge_lambda={config.ridge_lambda}, cv_folds={config.cv_folds}, "
        f"k_perm={config.k_perm}, permutations={config.permutations} "
        "(D-063's own calibration-transfer-confirmed setting).\n\n"
        "Gate logic delegated to `mintnet.experiments.stage1b_reporting`'s own already-"
        "validated functions -- see `docs/stage7e_charter.md`'s own selection-and-gate "
        "section for the frozen criteria (identical to Stage 7's own: chain/fork indirect-"
        "edge pruning TPR >= 0.80, triangle true-edge retention FPR <= 0.10).\n\n"
        "See `aggregate_metrics.csv`, `decision.json`, and `calibration_summary.csv` "
        "for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
