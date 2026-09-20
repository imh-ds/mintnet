"""Fine-grained alpha re-analysis of Stage 7e's own already-collected
isolation-tier evidence (D-064). See docs/decision_log.md's own D-064
entry and docs/stage7e_charter.md.

`compute_structured_density_conditional_independence_evidence` is
computed ONCE per replicate and re-thresholded across every alpha in
Stage 1b's own frozen 9-value grid -- meaning every replicate's own
`p_value_01`/`02`/`12` are IDENTICAL across all 9 alpha rows already
in `raw_metrics.csv` (verified directly: `nunique() == 1` for every
replicate group). D-064 found chain/fork's own indirect-edge pruning
TPR and the `strong` triangle's own true-edge pruning FPR cross almost
on top of each other somewhere between the grid's own `.10` and `.20`
points, at `N=1500` -- but the frozen grid has no point in between to
test directly.

**This script needs no new evidence collection and no new charter**:
it deduplicates the already-collected per-replicate p-values (one row
per replicate, not nine) and re-thresholds them at a much finer alpha
grid, then re-runs Stage 7e's own already-validated, unmodified gate
logic (`mintnet.experiments.stage1b_reporting.evaluate_stage1b_gate`)
against that finer grid. The development/validation replicate split
this depends on to avoid p-hacking was frozen in Stage 7e's own
charter before any of this evidence existed -- searching a finer grid
on development, then confirming on the same held-out validation
replicates, preserves that discipline exactly, it does not weaken it.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage1b_reporting import aggregate_stage1b, evaluate_stage1b_gate
from mintnet.experiments.stage7e_isolation import Stage7eIsolationConfig, load_config
from mintnet.metrics import score_motif

_DEDUP_COLUMNS = ["motif", "family", "strength_index", "strength", "n", "replicate", "seed", "status", "error"]
_P_VALUE_COLUMNS = ["p_value_01", "p_value_02", "p_value_12"]


def _deduplicate_replicates(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (motif, strength_index, n, replicate) -- the p-values
    are identical across every alpha row in the source data (this is
    exactly what "compute once, threshold many times" means), so this
    keeps the first alpha's own row and discards the other eight
    duplicates, which carry no additional information."""
    ok = raw.loc[raw["status"] == "ok"]
    deduplicated = ok.drop_duplicates(subset=["motif", "strength_index", "n", "replicate"], keep="first")
    return deduplicated[_DEDUP_COLUMNS + _P_VALUE_COLUMNS].reset_index(drop=True)


def _rethreshold(deduplicated: pd.DataFrame, alphas: tuple[float, ...]) -> pd.DataFrame:
    """Recompute retain/prune decisions and score_motif's own metrics at
    each new alpha, purely from the already-stored p-values -- zero new
    significance tests, zero new randomness."""
    rows: list[dict[str, object]] = []
    for _, source in deduplicated.iterrows():
        p01, p02, p12 = source["p_value_01"], source["p_value_02"], source["p_value_12"]
        for alpha in alphas:
            adjacency = np.zeros((3, 3), dtype=bool)
            adjacency[0, 1] = adjacency[1, 0] = p01 <= alpha
            adjacency[0, 2] = adjacency[2, 0] = p02 <= alpha
            adjacency[1, 2] = adjacency[2, 1] = p12 <= alpha
            metrics = score_motif(adjacency, source["motif"])
            rows.append(
                {
                    "motif": source["motif"], "family": source["family"],
                    "strength_index": source["strength_index"], "strength": source["strength"],
                    "n": source["n"], "alpha": alpha, "replicate": source["replicate"],
                    "status": "ok", "elapsed_seconds": 0.0,
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def refine(
    raw_path: Path, source_config_path: Path, alphas: tuple[float, ...], output_dir: Path
) -> tuple[pd.DataFrame, object]:
    raw = pd.read_csv(raw_path)
    deduplicated = _deduplicate_replicates(raw)
    refined_raw = _rethreshold(deduplicated, alphas)

    source_config = load_config(source_config_path)
    refined_config: Stage7eIsolationConfig = replace(source_config, alphas=alphas)

    output_dir.mkdir(parents=True, exist_ok=True)
    refined_raw.to_csv(output_dir / "refined_raw_metrics.csv", index=False)
    aggregate = aggregate_stage1b(refined_raw)
    aggregate.to_csv(output_dir / "refined_aggregate_metrics.csv", index=False)
    decision = evaluate_stage1b_gate(refined_raw, refined_config)
    (output_dir / "refined_decision.json").write_text(
        json.dumps(asdict(decision), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return aggregate, decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path, help="path to Stage 7e's own raw_metrics.csv")
    parser.add_argument(
        "--source-config", required=True, type=Path,
        help="Stage 7e's own config.yaml (for development/validation split and TPR/FPR floors)",
    )
    parser.add_argument(
        "--alpha-min", type=float, default=0.05, help="fine grid lower bound (default: 0.05)"
    )
    parser.add_argument(
        "--alpha-max", type=float, default=0.35, help="fine grid upper bound (default: 0.35)"
    )
    parser.add_argument(
        "--alpha-step", type=float, default=0.01, help="fine grid step (default: 0.01)"
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    alphas = tuple(round(a, 4) for a in np.arange(arguments.alpha_min, arguments.alpha_max + 1e-9, arguments.alpha_step))
    aggregate, decision = refine(arguments.raw, arguments.source_config, alphas, arguments.output)
    print(f"Decision: {decision.status}")
    print(f"Selected alpha pair: {decision.selected_alpha_pair}")
    print(f"Failures: {decision.failures}")


if __name__ == "__main__":
    main()
