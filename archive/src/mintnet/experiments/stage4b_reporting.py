"""Gate evaluation and evidence rendering for the Stage 4b sequential/
greedy conditioning engine experiment (hub and shared-node overlap
components). See docs/stage4b_charter.md.

Unlike Stage 4a, this charter needs its own alpha-selection logic (D-012's
alpha(N) formula does not apply to this engine's single fused alpha) and
its own gate evaluation (select the *largest* development-eligible alpha,
not the smallest adjacent pair) -- both new here, following Stage 1k/1L's
own margin-based validation check once an alpha is selected.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from mintnet.experiments.stage4b import SHAPES, Stage4bConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


def _cell_metrics(rows: pd.DataFrame, shape: str, n: int, alpha: float) -> tuple[float, float] | None:
    subset = rows.loc[(rows["shape"] == shape) & (rows["n"] == n) & (rows["alpha"] == alpha)]
    columns = ["indirect_prune_tpr", "true_edge_prune_fpr"]
    if subset.empty or not np.isfinite(subset[columns]).all().all():
        return None
    return float(subset["indirect_prune_tpr"].mean()), float(subset["true_edge_prune_fpr"].mean())


def select_alpha(raw: pd.DataFrame, shape: str, n: int, config: Stage4bConfig) -> float | None:
    """Largest development-eligible alpha (most permissive threshold that
    still comfortably clears both margins) -- the opposite tiebreak from
    Stage 1b/4a's smallest-adjacent-pair rule, per docs/stage4b_charter.md.
    """
    if raw.empty or not raw["status"].eq("ok").all():
        return None
    development = _partition(raw, config.development_replicates)
    eligible: list[float] = []
    for alpha in config.alphas:
        metrics = _cell_metrics(development, shape, n, alpha)
        if metrics is None:
            continue
        tpr, fpr = metrics
        tpr_margin = tpr - config.minimum_indirect_prune_tpr
        fpr_margin = config.maximum_true_edge_prune_fpr - fpr
        if tpr_margin >= config.required_margin and fpr_margin >= config.required_margin:
            eligible.append(alpha)
    return max(eligible) if eligible else None


@dataclass(frozen=True)
class NDecision:
    shape: str
    n: int
    status: str
    selected_alpha: float | None
    indirect_prune_tpr: float | None
    true_edge_prune_fpr: float | None
    margin: float | None
    failures: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    by_cell: tuple[NDecision, ...]


def evaluate_cell(raw: pd.DataFrame, shape: str, n: int, config: Stage4bConfig) -> NDecision:
    cell_raw = raw.loc[(raw["shape"] == shape) & (raw["n"] == n)]
    failures: list[str] = []
    if cell_raw.empty or not cell_raw["status"].eq("ok").all():
        failures.append("estimator or DGP errors")
        return NDecision(shape, n, "REASSESS", None, None, None, None, tuple(failures))

    selected = select_alpha(raw, shape, n, config)
    if selected is None:
        failures.append("no eligible development alpha")
        return NDecision(shape, n, "REASSESS", None, None, None, None, tuple(failures))

    validation = _partition(cell_raw, config.validation_replicates)
    metrics = _cell_metrics(validation, shape, n, selected)
    if metrics is None:
        failures.append("missing validation evidence")
        return NDecision(shape, n, "REASSESS", selected, None, None, None, tuple(failures))

    tpr, fpr = metrics
    tpr_margin = tpr - config.minimum_indirect_prune_tpr
    fpr_margin = config.maximum_true_edge_prune_fpr - fpr
    margin = min(tpr_margin, fpr_margin)

    if tpr < config.minimum_indirect_prune_tpr:
        failures.append(f"indirect TPR {tpr:.4f} below required {config.minimum_indirect_prune_tpr:.4f}")
    if fpr > config.maximum_true_edge_prune_fpr:
        failures.append(f"true-edge FPR {fpr:.4f} above allowed {config.maximum_true_edge_prune_fpr:.4f}")
    if margin < config.required_margin:
        failures.append(f"margin {margin:.4f} below required {config.required_margin:.4f}")

    status = "PROCEED" if not failures else "REASSESS"
    return NDecision(shape, n, status, selected, tpr, fpr, margin, tuple(failures))


def evaluate_stage4b_gate(raw: pd.DataFrame, config: Stage4bConfig) -> GateDecision:
    cells = [(shape, n) for shape in SHAPES for n in config.sample_sizes]
    return GateDecision(tuple(evaluate_cell(raw, shape, n, config) for shape, n in cells))


def _repository_root(config: Stage4bConfig) -> Path:
    if config.source_path is not None:
        return config.source_path.parent.parent
    return Path(__file__).resolve().parents[3]


def _load_baseline_mean(path: Path, column: str, n: int, bounds: tuple[int, int] = (1000, 1999)) -> float | None:
    if not path.is_file():
        return None
    baseline = pd.read_csv(path)
    subset = baseline.loc[(baseline["n"] == n) & baseline["replicate"].between(*bounds)]
    if subset.empty or column not in subset.columns or not np.isfinite(subset[column]).all():
        return None
    return float(subset[column].mean())


def _compare_to_conservative(decision: GateDecision, config: Stage4bConfig) -> pd.DataFrame:
    """Descriptive, non-gating comparison against the conservative engine's
    own on-disk evidence: D-015 (hub, hand-fed), D-017 (overlap, hand-fed
    -- "does conditioning work here at all"), and D-018 (overlap, composed
    with real screening on a p=15 noisy network -- the motivating
    question). See docs/stage4b_charter.md's own framing of why the
    isolated overlap comparison here already speaks to D-018's question.
    """
    root = _repository_root(config)
    rows: list[dict[str, object]] = []
    for d in decision.by_cell:
        if d.n not in (750, 1500):
            continue
        if d.shape == "hub":
            baseline_tpr = _load_baseline_mean(root / "results/generated/stage1k_hub/raw_metrics.csv", "indirect_prune_tpr", d.n)
            baseline_source = "D-015 (Stage 1k, hand-fed hub)"
        else:
            baseline_tpr = _load_baseline_mean(root / "results/generated/stage1l_overlap/raw_metrics.csv", "indirect_prune_tpr", d.n)
            baseline_source = "D-017 (Stage 1L, hand-fed overlap)"
        composed_tpr = None
        if d.shape == "overlap":
            composed_tpr = _load_baseline_mean(
                root / "results/generated/stage2d_composition/raw_metrics.csv", "overlap_indirect_tpr", d.n
            )
        rows.append(
            {
                "shape": d.shape,
                "n": d.n,
                "sequential_status": d.status,
                "sequential_indirect_tpr": d.indirect_prune_tpr,
                "baseline_source": baseline_source,
                "baseline_hand_fed_tpr": baseline_tpr,
                "baseline_composed_overlap_tpr_D018": composed_tpr,
            }
        )
    return pd.DataFrame(rows)


def _plot_indirect_tpr_by_shape(decision: GateDecision, path: Path) -> None:
    figure, axis = plt.subplots()
    for shape, marker in (("hub", "o"), ("overlap", "s")):
        cells = [d for d in decision.by_cell if d.shape == shape]
        ns = [d.n for d in cells]
        tpr = [d.indirect_prune_tpr for d in cells]
        axis.plot(ns, tpr, marker=marker, label=f"{shape} indirect TPR")
    axis.axhline(0.80, color="gray", linestyle="--", linewidth=0.8, label="TPR gate (.80)")
    axis.set_xlabel("N")
    axis.set_ylabel("Indirect-edge TPR")
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage4b_report(raw: pd.DataFrame, config: Stage4bConfig, output_dir: Path) -> GateDecision:
    output_dir.mkdir(parents=True, exist_ok=True)
    decision = evaluate_stage4b_gate(raw, config)
    (output_dir / "decision.json").write_text(
        json.dumps({"by_cell": [asdict(d) for d in decision.by_cell]}, indent=2, allow_nan=True) + "\n",
        encoding="utf-8",
    )
    _plot_indirect_tpr_by_shape(decision, output_dir / "indirect_tpr_by_shape.png")

    comparison = _compare_to_conservative(decision, config)
    comparison.to_csv(output_dir / "conservative_comparison.csv", index=False)

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    rows = [
        "| shape | N | status | alpha | indirect TPR | true-edge FPR | margin | failures |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in decision.by_cell:
        alpha = "None" if d.selected_alpha is None else f"{d.selected_alpha:.4f}"
        failures = "None" if not d.failures else ", ".join(d.failures)
        rows.append(
            f"| {d.shape} | {d.n} | {d.status} | {alpha} | {fmt(d.indirect_prune_tpr)} | "
            f"{fmt(d.true_edge_prune_fpr)} | {fmt(d.margin)} | {failures} |"
        )
    table = "\n".join(rows)

    (output_dir / "stage4b_report.md").write_text(
        "# Stage 4b Sequential/Greedy Conditioning Engine — Hub and Overlap Report\n\n"
        f"{table}\n\n"
        "`conservative_comparison.csv` compares this engine's overlap "
        "indirect TPR against both D-017 (Stage 1L, the conservative "
        "mechanism hand-fed the same clean, noise-free DGP) and D-018 "
        "(Stage 2d, the conservative engine's own *composed*, "
        "screening-realistic pipeline on a noisy p=15 network -- the "
        "motivating comparison, since D-018 REASSESSed at N=750 on this "
        "exact shape and signal strength). See `docs/stage4b_charter.md` "
        "for why the isolated overlap result here already speaks to that "
        "comparison, without needing a noisy composed pipeline of its own.\n\n"
        "See `raw_metrics.csv`, `decision.json`, `conservative_comparison.csv`, "
        "and `indirect_tpr_by_shape.png` for complete evidence.\n",
        encoding="utf-8",
    )
    return decision
