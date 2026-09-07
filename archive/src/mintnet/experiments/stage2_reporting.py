"""Per-N gate evaluation and evidence rendering for the Stage 2 screening experiment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage2 import Stage2Config

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


@dataclass(frozen=True)
class NDecision:
    """The immutable R3 decision for a single sample size."""

    n: int
    status: str
    selected_rule_kind: str | None
    selected_threshold: float | None
    validation_recall: float | None
    validation_fdr: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_n: tuple[NDecision, ...]


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _rule_metrics(rows: pd.DataFrame, n: int, rule_kind: str, threshold: float) -> tuple[float, float] | None:
    """Pooled recall and pooled FDR across replicates, per the charter's frozen
    definition ("fraction of all flagged pairs, across all 96+9 possible pairs,
    that are actually null") -- sum of counts across replicates, not a mean of
    per-replicate ratios. The two differ whenever replicates have unequal
    numbers of flagged pairs (e.g. a replicate with zero flagged pairs
    contributes a 0.0 ratio to a mean, but should contribute nothing to a
    pooled fraction)."""
    subset = rows.loc[(rows["n"] == n) & (rows["rule_kind"] == rule_kind) & (rows["threshold"] == threshold)]
    count_columns = ["true_positives", "false_positives", "total_flagged", "true_pair_count"]
    if subset.empty or not np.isfinite(subset[count_columns]).all().all():
        return None
    total_true_positives = float(subset["true_positives"].sum())
    total_false_positives = float(subset["false_positives"].sum())
    total_flagged = float(subset["total_flagged"].sum())
    total_true_pairs = float(subset["true_pair_count"].sum())
    recall = total_true_positives / total_true_pairs
    fdr = (total_false_positives / total_flagged) if total_flagged > 0 else 0.0
    return recall, fdr


def _rule_candidates(config: Stage2Config) -> list[tuple[str, float]]:
    rules = [("uncorrected", a) for a in sorted(config.uncorrected_alphas)]
    rules += [("bh", q) for q in sorted(config.bh_q_values)]
    return rules


def select_rule(raw: pd.DataFrame, n: int, config: Stage2Config) -> tuple[str, float] | None:
    """Select the simplest eligible rule: smallest uncorrected alpha, else smallest BH q."""
    development = _partition(raw, config.development_replicates)
    eligible: list[tuple[str, float]] = []
    for rule_kind, threshold in _rule_candidates(config):
        metrics = _rule_metrics(development, n, rule_kind, threshold)
        if metrics is None:
            continue
        recall, fdr = metrics
        if recall >= config.minimum_recall and fdr <= config.maximum_fdr:
            eligible.append((rule_kind, threshold))
    if not eligible:
        return None
    uncorrected = [rule for rule in eligible if rule[0] == "uncorrected"]
    if uncorrected:
        return min(uncorrected, key=lambda rule: rule[1])
    return min(eligible, key=lambda rule: rule[1])


def evaluate_n(raw: pd.DataFrame, n: int, config: Stage2Config) -> NDecision:
    n_raw = raw.loc[raw["n"] == n]
    failures: list[str] = []
    if n_raw.empty or not n_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        return NDecision(n, "REASSESS", None, None, None, None, tuple(failures))

    selected = select_rule(n_raw, n, config)
    if selected is None:
        failures.append("no eligible development rule")
        return NDecision(n, "REASSESS", None, None, None, None, tuple(failures))

    rule_kind, threshold = selected
    validation = _partition(n_raw.loc[n_raw["status"] == "ok"], config.validation_replicates)
    metrics = _rule_metrics(validation, n, rule_kind, threshold)
    if metrics is None:
        failures.append("missing validation evidence")
        return NDecision(n, "REASSESS", rule_kind, threshold, None, None, tuple(failures))

    recall, fdr = metrics
    if recall < config.minimum_recall:
        failures.append(f"validation recall {recall:.4f} below required {config.minimum_recall:.4f}")
    if fdr > config.maximum_fdr:
        failures.append(f"validation FDR {fdr:.4f} above allowed {config.maximum_fdr:.4f}")
    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(n, status, rule_kind, threshold, recall, fdr, tuple(failures))


def evaluate_stage2_gate(raw: pd.DataFrame, config: Stage2Config) -> GateDecision:
    return GateDecision(tuple(evaluate_n(raw, n, config) for n in config.sample_sizes))


def _pooled_recall_and_fdr(rows: pd.DataFrame) -> pd.Series:
    """Pooled (sum-of-counts), matching `_rule_metrics` -- see its docstring."""
    ok = rows.loc[rows["status"] == "ok"]
    if ok.empty or not np.isfinite(ok[["true_positives", "false_positives", "total_flagged", "true_pair_count"]]).all().all():
        return pd.Series({"recall": np.nan, "false_discovery_rate": np.nan})
    total_flagged = float(ok["total_flagged"].sum())
    return pd.Series(
        {
            "recall": float(ok["true_positives"].sum()) / float(ok["true_pair_count"].sum()),
            "false_discovery_rate": (float(ok["false_positives"].sum()) / total_flagged)
            if total_flagged > 0
            else 0.0,
        }
    )


def aggregate_stage2(raw: pd.DataFrame) -> pd.DataFrame:
    grouped = raw.groupby(["n", "rule_kind", "threshold"], as_index=False)
    counts = grouped.agg(
        replicates=("replicate", "size"),
        successful_replicates=("status", lambda values: int(values.eq("ok").sum())),
        per_edge_fpr=("per_edge_fpr", "mean"),
        family_wise_any_false_edge_rate=("any_false_edge", "mean"),
    )
    pooled = (
        raw.groupby(["n", "rule_kind", "threshold"])
        .apply(_pooled_recall_and_fdr, include_groups=False)
        .reset_index()
    )
    return (
        counts.merge(pooled, on=["n", "rule_kind", "threshold"])
        .sort_values(["n", "rule_kind", "threshold"])
        .reset_index(drop=True)
    )


def _plot_operating_curve(aggregate: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots()
    for (n, rule_kind), values in aggregate.groupby(["n", "rule_kind"]):
        values = values.sort_values("false_discovery_rate")
        axis.plot(
            values["false_discovery_rate"], values["recall"], marker="o", label=f"N={n}, {rule_kind}"
        )
    axis.set_xlabel("False discovery rate")
    axis.set_ylabel("Recall")
    axis.legend(fontsize="xx-small", ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage2_report(raw: pd.DataFrame, config: Stage2Config, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate = aggregate_stage2(raw)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)
    decision = evaluate_stage2_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_n": [asdict(d) for d in decision.by_n]}, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_operating_curve(aggregate, output_dir / "screening_operating_curve.png")

    rows = [
        "| N | status | rule | threshold | validation recall | validation FDR | failures |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_n:
        rule = "None" if d.selected_rule_kind is None else d.selected_rule_kind
        threshold = "None" if d.selected_threshold is None else f"{d.selected_threshold:.4f}"
        recall = "None" if d.validation_recall is None else f"{d.validation_recall:.4f}"
        fdr = "None" if d.validation_fdr is None else f"{d.validation_fdr:.4f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(f"| {d.n} | {d.status} | {rule} | {threshold} | {recall} | {fdr} | {failures} |")
    table = "\n".join(rows)
    (output_dir / "stage2_report.md").write_text(
        "# Stage 2 Candidate-Edge Screening Report\n\n"
        f"{table}\n\n"
        "See `aggregate_metrics.csv`, `raw_metrics.csv`, `decision.json`, and "
        "`screening_operating_curve.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
