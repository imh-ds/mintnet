"""Gate evaluation and evidence rendering for the Stage 4h composed-
pipeline-with-noise experiment (sequential engine, p=15). See
docs/stage4h_charter.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage2d import OVERLAP_INDIRECT
from mintnet.experiments.stage4h import Stage4hConfig, _pair_label

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_SHARED_NODE = 8
_PAIR_LABELS = tuple(_pair_label(i, j) for i, j in OVERLAP_INDIRECT)


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _overlap_decomposition(rows: pd.DataFrame) -> tuple[float | None, float | None]:
    """Pooled candidacy rate and conditional accuracy across the 4 overlap
    cross-branch pairs -- Stage 4e/4g's own corrected metric, applied here
    so a PROCEED/REASSESS is never read through D-032's non-detection lens."""
    total_candidates = 0
    total_correct = 0
    for label in _PAIR_LABELS:
        candidate_column = rows[f"candidate_{label}"]
        if candidate_column.isna().any():
            return None, None
        correct_column = rows[f"correctly_pruned_{label}"]
        total_candidates += int(candidate_column.astype(bool).sum())
        total_correct += int(correct_column.fillna(False).astype(bool).sum())
    candidacy_rate = total_candidates / (len(_PAIR_LABELS) * len(rows))
    conditional_accuracy = (total_correct / total_candidates) if total_candidates > 0 else None
    return candidacy_rate, conditional_accuracy


def _contamination_rate(rows: pd.DataFrame) -> float | None:
    """Among wrongly-retained overlap cross-branch pairs, the fraction whose
    tested neighbor set did NOT include the true shared node (8) -- an
    extension of Stage 4c's contamination diagnostic into a realistic,
    larger candidate pool."""
    wrong_with_non_shared_neighbor = 0
    wrong_total = 0
    for i, j in OVERLAP_INDIRECT:
        label = _pair_label(i, j)
        candidate = rows[f"candidate_{label}"].astype(object)
        correct = rows[f"correctly_pruned_{label}"]
        tested = rows[f"tested_neighbors_{label}"]
        wrong = (candidate == True) & (correct == False)  # noqa: E712
        wrong_total += int(wrong.sum())
        for value in tested.loc[wrong]:
            neighbors = {int(k) for k in value.split(",") if k}
            if neighbors and _SHARED_NODE not in neighbors:
                wrong_with_non_shared_neighbor += 1
    if wrong_total == 0:
        return None
    return wrong_with_non_shared_neighbor / wrong_total


@dataclass(frozen=True)
class NDecision:
    n: int
    status: str
    alpha: float | None
    chain_indirect_tpr: float | None
    fork_indirect_tpr: float | None
    overlap_indirect_tpr: float | None
    true_edge_prune_fpr: float | None
    screening_false_edge_rate: float | None
    final_false_edge_rate: float | None
    overlap_candidacy_rate: float | None
    overlap_conditional_accuracy: float | None
    overlap_contamination_rate: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage4hConfig) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        alpha = float(n_raw["alpha"].iloc[0]) if not n_raw.empty else None
        failures.append("estimator or DGP errors")
        return NDecision(n, "REASSESS", alpha, None, None, None, None, None, None, None, None, None, tuple(failures))

    alpha = float(n_raw["alpha"].iloc[0])
    validation = _partition(n_raw, config.validation_replicates)

    chain_tpr = float(validation["chain_indirect_tpr"].mean())
    fork_tpr = float(validation["fork_indirect_tpr"].mean())
    overlap_tpr = float(validation["overlap_indirect_tpr"].mean())
    true_edge_fpr = float(validation["true_edge_prune_fpr"].mean())
    screening_rate = float(validation["screening_false_edge_rate"].mean())
    final_rate = float(validation["final_false_edge_rate"].mean())
    candidacy_rate, conditional_accuracy = _overlap_decomposition(validation)
    contamination_rate = _contamination_rate(validation)

    for label, tpr in (("chain", chain_tpr), ("fork", fork_tpr), ("overlap", overlap_tpr)):
        if tpr < config.minimum_indirect_prune_tpr:
            failures.append(f"{label} indirect TPR {tpr:.4f} below required {config.minimum_indirect_prune_tpr:.4f}")
    if true_edge_fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {true_edge_fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if final_rate > screening_rate + config.false_edge_rate_tolerance:
        failures.append(
            f"final false-edge rate {final_rate:.4f} exceeds screening baseline "
            f"{screening_rate:.4f} + tolerance {config.false_edge_rate_tolerance:.4f}"
        )

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(
        n, status, alpha, chain_tpr, fork_tpr, overlap_tpr, true_edge_fpr, screening_rate, final_rate,
        candidacy_rate, conditional_accuracy, contamination_rate, tuple(failures),
    )


def evaluate_stage4h_gate(raw: pd.DataFrame, config: Stage4hConfig) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _repository_root(config: Stage4hConfig) -> Path:
    if config.source_path is not None:
        return config.source_path.parent.parent
    return Path(__file__).resolve().parents[3]


def _load_d018_baseline(config: Stage4hConfig, n: int) -> float | None:
    path = _repository_root(config) / "results/generated/stage2d_composition/raw_metrics.csv"
    if not path.is_file():
        return None
    baseline = pd.read_csv(path)
    subset = baseline.loc[(baseline["n"] == n) & baseline["replicate"].between(1000, 1999)]
    if subset.empty or not np.isfinite(subset["overlap_indirect_tpr"]).all():
        return None
    return float(subset["overlap_indirect_tpr"].mean())


def _plot_tpr_by_n(decision: GateDecision, config: Stage4hConfig, path: Path) -> None:
    figure, axis = plt.subplots()
    cells = sorted(decision.by_n, key=lambda d: d.n)
    ns = [d.n for d in cells]
    axis.plot(ns, [d.overlap_indirect_tpr for d in cells], marker="o", label="sequential (composed, p=15)")
    d018 = [_load_d018_baseline(config, n) for n in ns]
    if any(v is not None for v in d018):
        axis.plot(ns, d018, marker="x", linestyle="--", label="D-018 conservative baseline")
    axis.axhline(0.80, color="gray", linestyle=":", linewidth=0.8, label="TPR gate (.80)")
    axis.set_xlabel("N")
    axis.set_ylabel("Overlap indirect-edge TPR")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4h_report(raw: pd.DataFrame, config: Stage4hConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4h_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    _plot_tpr_by_n(decision, config, output_dir / "overlap_tpr_by_n.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| N | status | alpha | chain TPR | fork TPR | overlap TPR | true-edge FPR | final FER | "
        "candidacy rate | conditional accuracy | contamination rate | D-018 baseline | failures |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d in sorted(decision.by_n, key=lambda c: c.n):
        d018 = _load_d018_baseline(config, d.n)
        failures = "None" if not d.failures else ", ".join(d.failures)
        alpha = "None" if d.alpha is None else f"{d.alpha:.4f}"
        rows.append(
            f"| {d.n} | {d.status} | {alpha} | {fmt(d.chain_indirect_tpr)} | {fmt(d.fork_indirect_tpr)} | "
            f"{fmt(d.overlap_indirect_tpr)} | {fmt(d.true_edge_prune_fpr)} | {fmt(d.final_false_edge_rate)} | "
            f"{fmt(d.overlap_candidacy_rate)} | {fmt(d.overlap_conditional_accuracy)} | "
            f"{fmt(d.overlap_contamination_rate)} | {fmt(d018)} | {failures} |"
        )
    table = "\n".join(rows)

    (output_dir / "stage4h_report.md").write_text(
        "# Stage 4h Composed Pipeline with Noise Report (Sequential Engine, p=15)\n\n"
        f"{table}\n\n"
        "`candidacy rate` / `conditional accuracy` (descriptive, Stage 4e/4g's corrected metric): "
        "fraction of the 4 overlap cross-branch pairs that clear screening at all, and pruning "
        "correctness among those that do. `contamination rate`: among wrongly-retained cross-branch "
        "pairs, the fraction tested against a node other than the true shared node 8 -- Stage 4c's "
        "contamination check, extended into this p=15 network's larger, more realistic candidate pool. "
        "`D-018 baseline`: the conservative engine's own composed-pipeline overlap TPR at the same N "
        "(`results/generated/stage2d_composition`), for direct comparison -- D-018 REASSESSed at "
        "N=750 (TPR ~.569) and PROCEEDed at N=1500 (not tested here; outside Stage 4g's validated "
        "[300,750] alpha(N) range).\n\n"
        "See `raw_metrics.csv`, `decision.json`, and `overlap_tpr_by_n.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
