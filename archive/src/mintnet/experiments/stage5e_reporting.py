"""Evidence rendering and the predeclared descriptive ranking for the
Stage 5e PC-algorithm skeleton comparison. See docs/stage5e_charter.md.

Implementation-time clarification, made before any evidence exists: the
charter's own "Decision structure" required stating, per shape, whether
PC's skeleton recovery is "comparable to or better than" MINT's and/or
EBICglasso's own D-047 numbers, without pinning an exact tolerance or
what counts as "at most tested N." This module fixes both now: a cell
counts as "comparable to or better" when PC's mean validation F1 is
within `0.01` of (or exceeds) the comparator's own D-047 F1 at that
same `N` -- the same tolerance this project's Stage 5b/5c/5d work has
already used throughout for gap comparisons. A shape counts as
satisfying a ranking condition when it holds at a majority (`>= 4` of
the `7` tested `N` values), not necessarily every one -- "at most
tested N" in the charter's own wording, fixed to a concrete number
here rather than left to post-hoc judgment.

D-047's own per-cell MINT/EBICglasso numbers (`docs/decision_log.md`,
`results/generated/stage5a_comparator_benchmark/stage5a_report.md`)
are hardcoded below, not re-derived: MINT and EBICglasso are not
re-run in this charter (see docs/stage5e_charter.md's own
"Data access" fair-comparison rule -- PC's fresh numbers are paired
against D-047's own draws via identical condition seeds, not merely
comparable to them).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage5a import DGPS
from mintnet.experiments.stage5e import METHODS, Stage5eConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

_GAP_TOLERANCE = 0.01
_MAJORITY_THRESHOLD = 4  # of 7 tested N values

# D-047's own published per-(dgp, N) numbers, hardcoded from
# results/generated/stage5a_comparator_benchmark/stage5a_report.md.
_D047_REFERENCE: dict[tuple[str, int], dict[str, float]] = {
    ("chain_fork_hub", 400): {"mint_f1": 0.9541, "ebicglasso_f1": 0.8583},
    ("chain_fork_hub", 500): {"mint_f1": 0.9510, "ebicglasso_f1": 0.8527},
    ("chain_fork_hub", 600): {"mint_f1": 0.9533, "ebicglasso_f1": 0.8509},
    ("chain_fork_hub", 750): {"mint_f1": 0.9568, "ebicglasso_f1": 0.8477},
    ("chain_fork_hub", 1000): {"mint_f1": 0.9589, "ebicglasso_f1": 0.8452},
    ("chain_fork_hub", 1500): {"mint_f1": 0.9642, "ebicglasso_f1": 0.8394},
    ("chain_fork_hub", 1750): {"mint_f1": 0.9658, "ebicglasso_f1": 0.8389},
    ("overlap", 400): {"mint_f1": 0.9332, "ebicglasso_f1": 0.8892},
    ("overlap", 500): {"mint_f1": 0.9208, "ebicglasso_f1": 0.8861},
    ("overlap", 600): {"mint_f1": 0.9148, "ebicglasso_f1": 0.8856},
    ("overlap", 750): {"mint_f1": 0.9101, "ebicglasso_f1": 0.8863},
    ("overlap", 1000): {"mint_f1": 0.9215, "ebicglasso_f1": 0.8805},
    ("overlap", 1500): {"mint_f1": 0.9528, "ebicglasso_f1": 0.8786},
    ("overlap", 1750): {"mint_f1": 0.9588, "ebicglasso_f1": 0.8815},
    ("triangle_balanced", 400): {"mint_f1": 0.9998, "ebicglasso_f1": 1.0000},
    ("triangle_balanced", 500): {"mint_f1": 1.0000, "ebicglasso_f1": 1.0000},
    ("triangle_balanced", 600): {"mint_f1": 1.0000, "ebicglasso_f1": 1.0000},
    ("triangle_balanced", 750): {"mint_f1": 1.0000, "ebicglasso_f1": 1.0000},
    ("triangle_balanced", 1000): {"mint_f1": 1.0000, "ebicglasso_f1": 1.0000},
    ("triangle_balanced", 1500): {"mint_f1": 1.0000, "ebicglasso_f1": 1.0000},
    ("triangle_balanced", 1750): {"mint_f1": 1.0000, "ebicglasso_f1": 1.0000},
    ("triangle_moderate", 400): {"mint_f1": 0.9682, "ebicglasso_f1": 0.9908},
    ("triangle_moderate", 500): {"mint_f1": 0.9818, "ebicglasso_f1": 0.9962},
    ("triangle_moderate", 600): {"mint_f1": 0.9848, "ebicglasso_f1": 0.9972},
    ("triangle_moderate", 750): {"mint_f1": 0.9930, "ebicglasso_f1": 0.9990},
    ("triangle_moderate", 1000): {"mint_f1": 0.9970, "ebicglasso_f1": 1.0000},
    ("triangle_moderate", 1500): {"mint_f1": 0.9996, "ebicglasso_f1": 1.0000},
    ("triangle_moderate", 1750): {"mint_f1": 1.0000, "ebicglasso_f1": 1.0000},
    ("triangle_strong", 400): {"mint_f1": 0.9208, "ebicglasso_f1": 0.9718},
    ("triangle_strong", 500): {"mint_f1": 0.9328, "ebicglasso_f1": 0.9810},
    ("triangle_strong", 600): {"mint_f1": 0.9424, "ebicglasso_f1": 0.9856},
    ("triangle_strong", 750): {"mint_f1": 0.9582, "ebicglasso_f1": 0.9924},
    ("triangle_strong", 1000): {"mint_f1": 0.9714, "ebicglasso_f1": 0.9972},
    ("triangle_strong", 1500): {"mint_f1": 0.9862, "ebicglasso_f1": 0.9996},
    ("triangle_strong", 1750): {"mint_f1": 0.9914, "ebicglasso_f1": 0.9992},
}


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class CellSummary:
    dgp: str
    method: str
    n: int
    status: str
    precision: float | None
    recall: float | None
    f1: float | None
    shd: float | None
    mean_runtime_seconds: float | None
    n_errors: int


@dataclass(frozen=True)
class GapPoint:
    dgp: str
    n: int
    pc_f1: float | None
    pc_recall: float | None
    mint_f1: float
    ebicglasso_f1: float
    matches_mint: bool | None
    matches_ebicglasso: bool | None


@dataclass(frozen=True)
class ShapeVerdict:
    dgp: str
    n_matches_mint: int
    n_matches_ebicglasso: int
    n_tested: int
    verdict: str


@dataclass(frozen=True)
class Stage5eReport:
    by_cell: tuple[CellSummary, ...]
    gap_by_condition: tuple[GapPoint, ...]
    by_shape: tuple[ShapeVerdict, ...]
    recall_holds: bool
    recall_note: str


def summarize_cell(raw: pd.DataFrame, dgp: str, method: str, n: int, config: Stage5eConfig) -> CellSummary:
    cell_raw = raw.loc[(raw["dgp"] == dgp) & (raw["method"] == method) & (raw["n"] == n)]
    validation = _partition(cell_raw, config.validation_replicates)
    n_errors = int((validation["status"] != "ok").sum())
    ok = validation.loc[validation["status"] == "ok"]

    if ok.empty:
        return CellSummary(dgp, method, n, "no valid replicates", None, None, None, None, None, n_errors)

    return CellSummary(
        dgp,
        method,
        n,
        "ok",
        float(ok["precision"].mean()),
        float(ok["recall"].mean()),
        float(ok["f1"].mean()),
        float(ok["shd"].mean()),
        float(ok["elapsed_seconds"].mean()),
        n_errors,
    )


def _gap_points(by_cell: tuple[CellSummary, ...], config: Stage5eConfig) -> tuple[GapPoint, ...]:
    points = []
    for dgp in DGPS:
        for n in config.sample_sizes:
            pc = next(c for c in by_cell if c.dgp == dgp and c.method == "pc" and c.n == n)
            reference = _D047_REFERENCE[(dgp, n)]
            matches_mint = (pc.f1 >= reference["mint_f1"] - _GAP_TOLERANCE) if pc.f1 is not None else None
            matches_ebic = (pc.f1 >= reference["ebicglasso_f1"] - _GAP_TOLERANCE) if pc.f1 is not None else None
            points.append(
                GapPoint(
                    dgp, n, pc.f1, pc.recall, reference["mint_f1"], reference["ebicglasso_f1"],
                    matches_mint, matches_ebic,
                )
            )
    return tuple(points)


def _shape_verdict(dgp: str, gap_by_condition: tuple[GapPoint, ...]) -> ShapeVerdict:
    points = [p for p in gap_by_condition if p.dgp == dgp]
    n_tested = len(points)
    n_matches_mint = sum(1 for p in points if p.matches_mint)
    n_matches_ebic = sum(1 for p in points if p.matches_ebicglasso)

    if n_matches_mint >= _MAJORITY_THRESHOLD:
        verdict = (
            f"PC comparable to or better than MINT at a majority of tested N "
            f"({n_matches_mint}/{n_tested})"
        )
    elif n_matches_ebic >= _MAJORITY_THRESHOLD:
        verdict = (
            f"PC comparable to or better than EBICglasso but not MINT "
            f"({n_matches_ebic}/{n_tested} vs. EBICglasso, {n_matches_mint}/{n_tested} vs. MINT)"
        )
    else:
        verdict = (
            f"PC trails both MINT and EBICglasso at a majority of tested N "
            f"({n_matches_mint}/{n_tested} vs. MINT, {n_matches_ebic}/{n_tested} vs. EBICglasso)"
        )
    return ShapeVerdict(dgp, n_matches_mint, n_matches_ebic, n_tested, verdict)


def _recall_check(by_cell: tuple[CellSummary, ...]) -> tuple[bool, str]:
    offenders = [c for c in by_cell if c.recall is not None and c.recall < 0.999]
    if not offenders:
        return True, (
            "Recall holds at ~1.0 for PC in every cell -- as in every prior R6 charter, this "
            "arc's own gap remains a precision story, not a detection story, for a third method now."
        )
    worst = min(offenders, key=lambda c: c.recall or 0.0)
    return False, (
        f"Recall drops below 1.0 for PC in {len(offenders)} cell(s), worst: {worst.dgp} N={worst.n} "
        f"recall={worst.recall:.4f} -- unlike every prior R6 charter, PC misses real edges here, not "
        f"just retaining false ones; this is new information for the arc."
    )


def evaluate_stage5e(raw: pd.DataFrame, config: Stage5eConfig) -> Stage5eReport:
    by_cell = tuple(
        summarize_cell(raw, dgp, method, n, config) for dgp in DGPS for n in config.sample_sizes for method in METHODS
    )
    gap_by_condition = _gap_points(by_cell, config)
    by_shape = tuple(_shape_verdict(dgp, gap_by_condition) for dgp in DGPS)
    recall_holds, recall_note = _recall_check(by_cell)
    return Stage5eReport(by_cell, gap_by_condition, by_shape, recall_holds, recall_note)


def _plot_f1_vs_reference(report: Stage5eReport, config: Stage5eConfig, path: Path) -> None:
    figure, axes = plt.subplots(1, len(DGPS), figsize=(5.5 * len(DGPS), 4.5), sharey=True)
    for axis, dgp in zip(axes, DGPS):
        points = sorted((p for p in report.gap_by_condition if p.dgp == dgp), key=lambda p: p.n)
        axis.plot([p.n for p in points], [p.pc_f1 for p in points], marker="o", label="PC")
        axis.plot([p.n for p in points], [p.mint_f1 for p in points], marker="s", linestyle="--", label="MINT (D-047)")
        axis.plot(
            [p.n for p in points], [p.ebicglasso_f1 for p in points], marker="^", linestyle="--",
            label="EBICglasso (D-047)",
        )
        axis.set_title(dgp)
        axis.set_xlabel("N")
        axis.set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Mean validation F1")
    axes[-1].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage5e_report(raw: pd.DataFrame, config: Stage5eConfig, output_dir: Path) -> Stage5eReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage5e(raw, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "gap_tolerance": _GAP_TOLERANCE,
                "majority_threshold": _MAJORITY_THRESHOLD,
                "recall_holds": report.recall_holds,
                "recall_note": report.recall_note,
                "by_cell": [asdict(c) for c in report.by_cell],
                "gap_by_condition": [asdict(g) for g in report.gap_by_condition],
                "by_shape": [asdict(s) for s in report.by_shape],
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_f1_vs_reference(report, config, output_dir / "pc_vs_d047_f1.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = [
        "# Stage 5e PC-Algorithm Skeleton Comparison Report (R6)\n",
        f"**Recall check: {report.recall_note}**\n",
        f"PC uses `alpha={config.pc_alpha}`, fixed (`pcalg`'s own canonical-tutorial convention), "
        f"skeleton phase only -- no orientation phase implemented at all (see "
        f"`docs/stage5e_charter.md`). PC's data is drawn identically to D-047's own (same "
        f"`master_seed`, same condition-seed derivation) -- MINT and EBICglasso columns below are "
        f"D-047's own published numbers, not re-run.\n",
        f"'Comparable to or better' means PC's mean validation F1 is within `{_GAP_TOLERANCE}` of, "
        f"or exceeds, the comparator's own F1 at that `N`; a shape verdict requires this holding at "
        f"a majority (`>= {_MAJORITY_THRESHOLD}` of `7`) of tested `N`, not necessarily every one -- "
        f"both fixed before this run, per this module's own docstring.\n",
    ]

    sections.append("## Per-shape verdict\n")
    sections.append("| DGP shape | matches MINT (N of 7) | matches EBICglasso (N of 7) | Verdict |")
    sections.append("|---|---|---|---|")
    for shape in report.by_shape:
        sections.append(
            f"| {shape.dgp} | {shape.n_matches_mint}/{shape.n_tested} | "
            f"{shape.n_matches_ebicglasso}/{shape.n_tested} | {shape.verdict} |"
        )
    sections.append("")

    for dgp in DGPS:
        rows = [
            f"## {dgp}\n",
            "| N | PC F1 | PC recall | MINT F1 (D-047) | EBICglasso F1 (D-047) | matches MINT | matches EBICglasso |",
            "|---|---|---|---|---|---|---|",
        ]
        for point in sorted((p for p in report.gap_by_condition if p.dgp == dgp), key=lambda p: p.n):
            rows.append(
                f"| {point.n} | {fmt(point.pc_f1)} | {fmt(point.pc_recall)} | {fmt(point.mint_f1)} | "
                f"{fmt(point.ebicglasso_f1)} | {point.matches_mint} | {point.matches_ebicglasso} |"
            )
        sections.append("\n".join(rows) + "\n")

    for dgp in DGPS:
        rows = [
            f"### {dgp} -- PC raw metrics\n",
            "| N | precision | recall | F1 | SHD | mean runtime (s) | errors |",
            "|---|---|---|---|---|---|---|",
        ]
        for n in config.sample_sizes:
            cell = next(c for c in report.by_cell if c.dgp == dgp and c.n == n)
            rows.append(
                f"| {n} | {fmt(cell.precision)} | {fmt(cell.recall)} | {fmt(cell.f1)} | {fmt(cell.shd)} | "
                f"{fmt(cell.mean_runtime_seconds)} | {cell.n_errors} |"
            )
        sections.append("\n".join(rows) + "\n")

    sections.append(
        "Descriptive result, not a validation gate; skeleton recovery only, no causal-direction "
        "claim of any kind -- see `docs/stage5e_charter.md`'s own decision structure and non-goals. "
        "See `raw_metrics.csv`, `report.json`, `resolved_config.yaml`, and `pc_vs_d047_f1.png` for "
        "complete evidence.\n"
    )
    (output_dir / "stage5e_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


write_report = write_stage5e_report
