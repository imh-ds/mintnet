"""Step 1 of the frozen Stage 7g charter: does a properly-specified
statistical test support "the N=500->600 dip D-083 found is sampling
noise, and the overall confidence-vs-N trend is real"? See
docs/stage7g_charter.md.

Zero new compute -- reuses Stage 7f's own already-collected raw
evidence (results/generated/stage7f_frontier/raw_metrics.csv) entirely,
via the same `_decisions_at_alpha` helper D-083's own report already
used, at the same canonical alpha=0.10.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

from mintnet.experiments.stage7f_frontier_reporting import _CANONICAL_ALPHA, _decisions_at_alpha

_FRONTIER_CONDITION = "triangle_0"  # smallest tested target_rho, D-083's own frontier edge
_FRONTIER_PAIR = (1, 2)


def _frontier_confidence(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (n, replicate): confidence for the frontier edge, at
    Stage 7f's own canonical alpha. Mirrors D-083's own report exactly."""
    decisions = _decisions_at_alpha(raw, _CANONICAL_ALPHA)
    frontier = decisions.loc[
        (decisions["condition"] == _FRONTIER_CONDITION) & (decisions["pair"].apply(lambda p: p == _FRONTIER_PAIR))
    ]
    return frontier[["n", "replicate", "confidence"]].reset_index(drop=True)


@dataclass(frozen=True)
class Stage7gStep1Result:
    canonical_alpha: float
    # Pairwise check: is the N=500 -> N=600 dip distinguishable from noise?
    mann_whitney_statistic: float
    mann_whitney_p_value: float
    dip_consistent_with_noise: bool  # True if p > 0.05 (fails to reject "no difference")
    # Overall trend check: does confidence significantly increase with N, pooling all replicates?
    spearman_correlation: float
    spearman_p_value: float
    significant_positive_trend: bool  # True if p < 0.05 AND correlation > 0
    n_replicates_per_cell: dict[str, int]
    status: str  # "PROCEED", "REASSESS", or "AMBIGUOUS" (Step 2 required)


def run_step1(raw: pd.DataFrame) -> Stage7gStep1Result:
    frontier = _frontier_confidence(raw)

    at_500 = frontier.loc[frontier["n"] == 500, "confidence"]
    at_600 = frontier.loc[frontier["n"] == 600, "confidence"]
    mw_statistic, mw_p = mannwhitneyu(at_500, at_600, alternative="two-sided")
    dip_consistent_with_noise = bool(mw_p > 0.05)

    corr, trend_p = spearmanr(frontier["n"], frontier["confidence"])
    significant_positive_trend = bool(trend_p < 0.05 and corr > 0)

    # No significant overall trend is a direct REASSESS regardless of the
    # pairwise result -- more replicates at just N=500/600 (Step 2) would
    # not address "there's no real trend at all", so this never routes to
    # AMBIGUOUS. Charter's own gate: PROCEED needs both checks to hold.
    if not significant_positive_trend:
        status = "REASSESS"
    elif mw_p > 0.10:
        status = "PROCEED"  # dip clearly consistent with noise
    elif mw_p < 0.01:
        status = "REASSESS"  # dip is clearly a real, significant difference
    else:
        status = "AMBIGUOUS"  # borderline -- Step 2 needed to resolve

    return Stage7gStep1Result(
        canonical_alpha=_CANONICAL_ALPHA,
        mann_whitney_statistic=float(mw_statistic),
        mann_whitney_p_value=float(mw_p),
        dip_consistent_with_noise=dip_consistent_with_noise,
        spearman_correlation=float(corr),
        spearman_p_value=float(trend_p),
        significant_positive_trend=significant_positive_trend,
        n_replicates_per_cell={str(n): int((frontier["n"] == n).sum()) for n in sorted(frontier["n"].unique())},
        status=status,
    )


def write_report(raw: pd.DataFrame, output_dir: Path) -> Stage7gStep1Result:
    result = run_step1(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "stage7g_step1.json").write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw", type=Path, default=Path("results/generated/stage7f_frontier/raw_metrics.csv"),
        help="Path to Stage 7f's own raw_metrics.csv",
    )
    parser.add_argument("--output", type=Path, default=Path("results/generated/stage7g_dip_check"))
    arguments = parser.parse_args()

    raw = pd.read_csv(arguments.raw)
    result = write_report(raw, arguments.output)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
