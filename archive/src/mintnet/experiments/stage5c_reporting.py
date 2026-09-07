"""Evidence rendering and the predeclared descriptive reading for the
Stage 5c p-adjusted-screening-alpha re-test. See docs/stage5c_charter.md.

Compares this charter's own F1 gap directly against D-048's own
fixed-alpha numbers (`docs/decision_log.md`), hardcoded below from that
already-published, frozen record -- Stage 5b's own raw evidence is not
assumed to be present in this worktree or CI run (it is ephemeral,
gitignored `results/generated/` output), so the comparison is against
the decision log's own numbers, not a re-read of prior artifacts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import pandas as pd

from mintnet.experiments.stage5c import DGPS, METHODS, Stage5cConfig

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

# D-048's own fixed-alpha (screening_alpha=.001 throughout) F1 values,
# hardcoded from docs/decision_log.md's own published table.
_D048_REFERENCE: dict[tuple[str, int, int], dict[str, float]] = {
    ("chain_fork_hub", 500, 1): {"mint_f1": 0.9513, "ebicglasso_f1": 0.8569, "gap": 0.0943},
    ("chain_fork_hub", 500, 2): {"mint_f1": 0.9406, "ebicglasso_f1": 0.8707, "gap": 0.0699},
    ("chain_fork_hub", 500, 3): {"mint_f1": 0.9255, "ebicglasso_f1": 0.8682, "gap": 0.0573},
    ("chain_fork_hub", 1500, 1): {"mint_f1": 0.9666, "ebicglasso_f1": 0.8435, "gap": 0.1231},
    ("chain_fork_hub", 1500, 2): {"mint_f1": 0.9543, "ebicglasso_f1": 0.8455, "gap": 0.1088},
    ("chain_fork_hub", 1500, 3): {"mint_f1": 0.9430, "ebicglasso_f1": 0.8493, "gap": 0.0937},
    ("overlap", 500, 1): {"mint_f1": 0.9192, "ebicglasso_f1": 0.8865, "gap": 0.0327},
    ("overlap", 500, 2): {"mint_f1": 0.9162, "ebicglasso_f1": 0.8926, "gap": 0.0236},
    ("overlap", 500, 3): {"mint_f1": 0.9139, "ebicglasso_f1": 0.9010, "gap": 0.0128},
    ("overlap", 1500, 1): {"mint_f1": 0.9503, "ebicglasso_f1": 0.8803, "gap": 0.0700},
    ("overlap", 1500, 2): {"mint_f1": 0.9456, "ebicglasso_f1": 0.8845, "gap": 0.0611},
    ("overlap", 1500, 3): {"mint_f1": 0.9389, "ebicglasso_f1": 0.8933, "gap": 0.0456},
}


def _partition(raw: pd.DataFrame, bounds: tuple[int, int]) -> pd.DataFrame:
    return raw.loc[raw["replicate"].between(*bounds)]


@dataclass(frozen=True)
class CellSummary:
    dgp: str
    method: str
    n: int
    noise_multiplier: int
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
    noise_multiplier: int
    mint_f1: float | None
    ebicglasso_f1: float | None
    gap: float | None
    d048_mint_f1: float | None
    d048_gap: float | None


@dataclass(frozen=True)
class Stage5cReport:
    by_cell: tuple[CellSummary, ...]
    gap_by_condition: tuple[GapPoint, ...]
    monotone_non_decreasing: bool
    reading: str


def summarize_cell(
    raw: pd.DataFrame, dgp: str, method: str, n: int, multiplier: int, config: Stage5cConfig
) -> CellSummary:
    cell_raw = raw.loc[
        (raw["dgp"] == dgp) & (raw["method"] == method) & (raw["n"] == n) & (raw["noise_multiplier"] == multiplier)
    ]
    validation = _partition(cell_raw, config.validation_replicates)
    n_errors = int((validation["status"] != "ok").sum())
    ok = validation.loc[validation["status"] == "ok"]

    if ok.empty:
        return CellSummary(dgp, method, n, multiplier, "no valid replicates", None, None, None, None, None, n_errors)

    return CellSummary(
        dgp,
        method,
        n,
        multiplier,
        "ok",
        float(ok["precision"].mean()),
        float(ok["recall"].mean()),
        float(ok["f1"].mean()),
        float(ok["shd"].mean()),
        float(ok["elapsed_seconds"].mean()),
        n_errors,
    )


def _gap_points(by_cell: tuple[CellSummary, ...], config: Stage5cConfig) -> tuple[GapPoint, ...]:
    points = []
    for dgp in DGPS:
        for n in config.sample_sizes:
            for multiplier in config.noise_multipliers:
                mint = next(c for c in by_cell if c.dgp == dgp and c.method == "mint" and c.n == n and c.noise_multiplier == multiplier)
                ebic = next(c for c in by_cell if c.dgp == dgp and c.method == "ebicglasso" and c.n == n and c.noise_multiplier == multiplier)
                gap = (mint.f1 - ebic.f1) if (mint.f1 is not None and ebic.f1 is not None) else None
                reference = _D048_REFERENCE.get((dgp, n, multiplier))
                points.append(
                    GapPoint(
                        dgp, n, multiplier, mint.f1, ebic.f1, gap,
                        reference["mint_f1"] if reference else None,
                        reference["gap"] if reference else None,
                    )
                )
    return tuple(points)


def _is_monotone_non_decreasing(gap_by_condition: tuple[GapPoint, ...], config: Stage5cConfig) -> bool:
    tolerance = 0.01
    for dgp in DGPS:
        for n in config.sample_sizes:
            series = sorted(
                (p for p in gap_by_condition if p.dgp == dgp and p.n == n), key=lambda p: p.noise_multiplier
            )
            values = [p.gap for p in series if p.gap is not None]
            for previous, current in zip(values, values[1:]):
                if current < previous - tolerance:
                    return False
    return True


def evaluate_stage5c(raw: pd.DataFrame, config: Stage5cConfig) -> Stage5cReport:
    by_cell = tuple(
        summarize_cell(raw, dgp, method, n, multiplier, config)
        for dgp in DGPS
        for n in config.sample_sizes
        for multiplier in config.noise_multipliers
        for method in METHODS
    )
    gap_by_condition = _gap_points(by_cell, config)
    monotone = _is_monotone_non_decreasing(gap_by_condition, config)

    mint_precision_holds = all(
        (
            next(c for c in by_cell if c.dgp == dgp and c.method == "mint" and c.n == n and c.noise_multiplier == config.noise_multipliers[-1]).precision or 0
        ) >= (
            next(c for c in by_cell if c.dgp == dgp and c.method == "mint" and c.n == n and c.noise_multiplier == config.noise_multipliers[0]).precision or 0
        ) - 0.01
        for dgp in DGPS
        for n in config.sample_sizes
    )

    if monotone:
        reading = (
            "RESTORES the mechanism: under alpha(p), the MINT-minus-EBICglasso F1 gap is non-decreasing "
            "in noise multiplier (within sampling tolerance) at every tested (dgp, N)."
        )
    elif mint_precision_holds:
        reading = (
            "CONFIRMS THE CONFOUND BUT NOT THE MECHANISM: the gap still shrinks with noise multiplier, but "
            "MINT's own precision no longer declines with p -- EBICglasso's own ln(p)-driven improvement "
            "still outpaces MINT's now-stabilized precision."
        )
    else:
        reading = (
            "NEITHER: alpha(p) did not materially change the pattern relative to D-048's own fixed-alpha "
            "result -- the interpolation may be too weak an adjustment, or the diagnosis needs revisiting."
        )

    return Stage5cReport(by_cell, gap_by_condition, monotone, reading)


def _plot_gap_by_multiplier(report: Stage5cReport, config: Stage5cConfig, path: Path) -> None:
    figure, axes = plt.subplots(1, len(DGPS), figsize=(6 * len(DGPS), 4.5), sharey=True)
    for axis, dgp in zip(axes, DGPS):
        for n in config.sample_sizes:
            series = sorted(
                (p for p in report.gap_by_condition if p.dgp == dgp and p.n == n), key=lambda p: p.noise_multiplier
            )
            axis.plot([p.noise_multiplier for p in series], [p.gap for p in series], marker="o", label=f"N={n} (alpha(p))")
            axis.plot(
                [p.noise_multiplier for p in series], [p.d048_gap for p in series],
                marker="x", linestyle="--", label=f"N={n} (D-048 fixed alpha)",
            )
        axis.axhline(0.0, color="gray", linestyle=":", linewidth=0.8)
        axis.set_title(dgp)
        axis.set_xlabel("Noise multiplier (x native noise-column count)")
    axes[0].set_ylabel("MINT F1 - EBICglasso F1")
    axes[-1].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def write_stage5c_report(raw: pd.DataFrame, config: Stage5cConfig, output_dir: Path) -> Stage5cReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_stage5c(raw, config)
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "monotone_non_decreasing": report.monotone_non_decreasing,
                "reading": report.reading,
                "by_cell": [asdict(c) for c in report.by_cell],
                "gap_by_condition": [asdict(g) for g in report.gap_by_condition],
            },
            indent=2,
            allow_nan=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _plot_gap_by_multiplier(report, config, output_dir / "gap_by_noise_multiplier_vs_d048.png")

    def fmt(value: float | None) -> str:
        return "None" if value is None else f"{value:.4f}"

    sections = [
        "# Stage 5c p-Adjusted Screening Alpha Report (R6)\n",
        f"**Reading: {report.reading}**\n",
        "Identical grid to Stage 5b (D-048), one substitution: MINT's screening alpha is `alpha(p)`, "
        "a log-linear interpolation of Stage 2's own two calibrated anchor points (`.001` at `p=15`, "
        "`.0001` at `p=30`), instead of Stage 5b's fixed `.001`. DPI's own `alpha(N)` (D-012's formula) "
        "is unchanged.\n",
        "## F1 gap by noise multiplier -- this charter vs. D-048's own fixed-alpha numbers\n",
        "| DGP shape | N | noise multiplier | MINT F1 (alpha(p)) | EBICglasso F1 | gap (alpha(p)) | gap (D-048, fixed alpha) |",
        "|---|---|---|---|---|---|---|",
    ]
    for point in report.gap_by_condition:
        sections.append(
            f"| {point.dgp} | {point.n} | {point.noise_multiplier} | {fmt(point.mint_f1)} | "
            f"{fmt(point.ebicglasso_f1)} | {fmt(point.gap)} | {fmt(point.d048_gap)} |"
        )
    sections.append("")

    for dgp in DGPS:
        rows = [
            f"## {dgp}\n",
            "| N | noise multiplier | method | precision | recall | F1 | SHD | mean runtime (s) | errors |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for n in config.sample_sizes:
            for multiplier in config.noise_multipliers:
                for method in METHODS:
                    cell = next(
                        c for c in report.by_cell
                        if c.dgp == dgp and c.method == method and c.n == n and c.noise_multiplier == multiplier
                    )
                    rows.append(
                        f"| {n} | {multiplier} | {method} | {fmt(cell.precision)} | {fmt(cell.recall)} | "
                        f"{fmt(cell.f1)} | {fmt(cell.shd)} | {fmt(cell.mean_runtime_seconds)} | {cell.n_errors} |"
                    )
        sections.append("\n".join(rows) + "\n")

    sections.append(
        "Descriptive result, not a validation gate -- see `docs/stage5c_charter.md`'s own decision "
        "structure. See `raw_metrics.csv`, `report.json`, `resolved_config.yaml`, and "
        "`gap_by_noise_multiplier_vs_d048.png` for complete evidence.\n"
    )
    (output_dir / "stage5c_report.md").write_text("\n".join(sections), encoding="utf-8")
    return report


write_report = write_stage5c_report
