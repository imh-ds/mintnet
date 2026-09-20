"""Structural audit of `chain_fork_hub`/`overlap`'s own screened
conditioning subsets. See docs/stage8g_charter.md.

Steps 1 (`decisive_conditioning_subset` added to `GrowingSubsetResult`)
and 2 (that field persisted by `stage8c_composed_calibration.py`'s own
third enrichment) are implemented elsewhere. This module implements
Steps 3-5: for every false edge with `conditioning_size_used >= 2`,
regenerate that exact replicate's own data -- deterministic from the
`seed` `stage8c_composed_calibration.py`'s own raw evidence already
records per `(dgp, n, replicate)`, no re-derivation of the seed formula
needed and no new persisted raw data -- compute each decisive
conditioning subset's own "chance correlation" with the tested pair,
evaluate H3 (the finite-sample pseudo-collider hypothesis), and run the
Step 5 validity cross-check against each named indirect pair's own
known legitimate separator.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from mintnet.experiments.stage2d import CHAIN_INDIRECT as _OV_CHAIN_INDIRECT
from mintnet.experiments.stage2d import FORK_INDIRECT as _OV_FORK_INDIRECT
from mintnet.experiments.stage2d import OVERLAP_INDIRECT as _OV_OVERLAP_INDIRECT
from mintnet.experiments.stage4l import CHAIN_INDIRECT as _CFH_CHAIN_INDIRECT
from mintnet.experiments.stage4l import FORK_INDIRECT as _CFH_FORK_INDIRECT
from mintnet.experiments.stage4l import HUB_INDIRECT as _CFH_HUB_INDIRECT
from mintnet.experiments.stage5a import _DGP_REGISTRY as _COMPOSED_DGP_REGISTRY
from mintnet.experiments.stage6c_reporting import wilson_ci
from mintnet.experiments.stage8c_composed_calibration_reporting import explode_edges

# Each named "indirect" pair's own known legitimate separator -- a
# mediator (chain), common cause (fork/hub), or undirected graph
# separator (overlap's shared node) -- established by direct inspection
# of stage4l.py's/stage2d.py's own generative code (docs/stage8g_charter
# .md's own Background section), not derived from any evidence.
_LEGITIMATE_SEPARATOR: dict[str, dict[tuple[int, int], int]] = {
    "chain_fork_hub": {
        _CFH_CHAIN_INDIRECT[0]: 1,
        _CFH_FORK_INDIRECT[0]: 4,
        _CFH_HUB_INDIRECT[0]: 6,
    },
    "overlap": {
        _OV_CHAIN_INDIRECT[0]: 1,
        _OV_FORK_INDIRECT[0]: 4,
        **{pair: 8 for pair in _OV_OVERLAP_INDIRECT},
    },
}


def _replicate_seeds(raw: pd.DataFrame) -> dict[tuple[str, int, int], int]:
    return {(row.dgp, int(row.n), int(row.replicate)): int(row.seed) for row in raw.itertuples(index=False)}


def load_strength(raw_path: Path) -> float:
    """Stage 8c's own `strength` is a run-wide constant, recorded in
    `resolved_config.yaml` next to `raw_metrics.csv`, not per-row."""
    resolved = raw_path.parent / "resolved_config.yaml"
    with resolved.open(encoding="utf-8") as stream:
        values = yaml.safe_load(stream)
    return float(values["strength"])


def _regenerate_data(dgp: str, n: int, seed: int, strength: float) -> np.ndarray:
    sample = _COMPOSED_DGP_REGISTRY[dgp]["sample"]
    return sample(n, strength, np.random.default_rng(seed))  # type: ignore[operator]


def chance_correlation(data: np.ndarray, i: int, j: int, subset: tuple[int, ...]) -> float:
    """Largest marginal |Pearson correlation| between any decisive-subset
    member and either endpoint of the tested pair, in this specific
    sample -- the quantity a true collider would inflate, and which a
    merely-independent decoy would not, except by ordinary sampling
    noise (see Stage 8f's own step2_control, D-071)."""
    correlations = [abs(np.corrcoef(data[:, c], data[:, i])[0, 1]) for c in subset]
    correlations += [abs(np.corrcoef(data[:, c], data[:, j])[0, 1]) for c in subset]
    return max(correlations)


_CANDIDATE_COLUMNS = (
    "dgp", "n", "replicate", "i", "j", "correct", "decisive_conditioning_subset", "chance_correlation",
)


def enrich_with_chance_correlation(raw: pd.DataFrame, strength: float) -> pd.DataFrame:
    """Restrict to false edges with `conditioning_size_used >= 2` (D-069's
    own reversal-trigger condition) and add each one's own
    `chance_correlation`. Regenerates a replicate's own data once,
    cached, not once per edge -- a single replicate can have multiple
    such edges."""
    exploded = explode_edges(raw)
    if (
        "decisive_conditioning_subset" not in exploded.columns
        or exploded["decisive_conditioning_subset"].isna().all()
    ):
        raise ValueError(
            "raw evidence has no decisive_conditioning_subset data -- it predates Stage 8c's own "
            "third enrichment (see stage8c_composed_calibration.py); re-run Stage 8c to produce "
            "enriched evidence before running this audit"
        )

    candidates = exploded.loc[
        (~exploded["is_true_edge"])
        & exploded["conditioning_size_used"].notna()
        & (exploded["conditioning_size_used"] >= 2)
        & exploded["decisive_conditioning_subset"].apply(lambda s: isinstance(s, tuple) and len(s) > 0)
    ].copy()
    if candidates.empty:
        return pd.DataFrame(columns=_CANDIDATE_COLUMNS)

    seeds = _replicate_seeds(raw)
    data_cache: dict[tuple[str, int, int], np.ndarray] = {}
    chance_values: list[float] = []
    for row in candidates.itertuples(index=False):
        key = (row.dgp, int(row.n), int(row.replicate))
        if key not in data_cache:
            data_cache[key] = _regenerate_data(row.dgp, int(row.n), seeds[key], strength)
        chance_values.append(chance_correlation(data_cache[key], int(row.i), int(row.j), row.decisive_conditioning_subset))
    candidates["chance_correlation"] = chance_values
    return candidates[list(_CANDIDATE_COLUMNS)]


def h3_wrong_retention_table(candidates: pd.DataFrame) -> pd.DataFrame:
    """Per (dgp, n): a data-driven median split of chance_correlation
    into "high"/"low" halves, each half's own wrong-retention rate
    (fraction of these false edges that were, incorrectly, retained)
    with a Wilson 95% CI."""
    rows: list[dict[str, object]] = []
    if candidates.empty:
        return pd.DataFrame(rows)
    for (dgp, n), group in candidates.groupby(["dgp", "n"]):
        median = group["chance_correlation"].median()
        halves = {"high": group.loc[group["chance_correlation"] > median], "low": group.loc[group["chance_correlation"] <= median]}
        for level, half in halves.items():
            count = len(half)
            wrong = int((~half["correct"]).sum())
            ci_low, ci_high = wilson_ci(wrong, count) if count else (float("nan"), float("nan"))
            rows.append(
                {
                    "dgp": dgp, "n": n, "level": level, "count": count,
                    "wrong_retention_rate": wrong / count if count else float("nan"),
                    "ci_low": ci_low, "ci_high": ci_high,
                }
            )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class H3Verdict:
    status: str  # "CONFIRMED", "NOT_CONFIRMED", or "INCONCLUSIVE"
    cells_supporting: list[list[object]]
    cells_contradicting: list[list[object]]
    cells_inconclusive: list[list[object]]


def evaluate_h3(table: pd.DataFrame, min_count: int = 30) -> H3Verdict:
    """A (dgp, n) cell "supports" H3 if the "high" chance-correlation
    half's own wrong-retention-rate CI sits entirely above the "low"
    half's own CI (non-overlapping, high higher). "Contradicts" if not.
    Inconclusive if either half lacks `min_count` valid rows."""
    if table.empty:
        return H3Verdict(status="INCONCLUSIVE", cells_supporting=[], cells_contradicting=[], cells_inconclusive=[])

    high = table.loc[table["level"] == "high"].set_index(["dgp", "n"])
    low = table.loc[table["level"] == "low"].set_index(["dgp", "n"])
    supporting, contradicting, inconclusive = [], [], []
    for key in sorted(set(high.index) & set(low.index)):
        high_row, low_row = high.loc[key], low.loc[key]
        if (
            high_row["count"] < min_count
            or low_row["count"] < min_count
            or pd.isna(high_row["ci_low"])
            or pd.isna(low_row["ci_high"])
        ):
            inconclusive.append([key[0], int(key[1])])
            continue
        if high_row["ci_low"] > low_row["ci_high"]:
            supporting.append([key[0], int(key[1])])
        else:
            contradicting.append([key[0], int(key[1])])

    if not supporting and not contradicting:
        status = "INCONCLUSIVE"
    elif supporting and not contradicting:
        status = "CONFIRMED"
    else:
        status = "NOT_CONFIRMED"
    return H3Verdict(
        status=status, cells_supporting=supporting, cells_contradicting=contradicting, cells_inconclusive=inconclusive
    )


@dataclass(frozen=True)
class Step5Result:
    status: str  # "CLEAN" or "FLAGGED"
    flagged_rows: list[dict[str, object]]


def evaluate_step5_validity(candidates: pd.DataFrame) -> Step5Result:
    """Flags any wrongly-retained false edge (among the same
    conditioning_size_used >= 2 population H3 uses) whose own decisive
    conditioning subset contained that pair's own known legitimate
    separator -- a materially more serious finding than a pseudo-
    collider explanation (see docs/stage8g_charter.md's own Step 5)."""
    flagged: list[dict[str, object]] = []
    for row in candidates.itertuples(index=False):
        separators = _LEGITIMATE_SEPARATOR.get(row.dgp, {})
        pair = (row.i, row.j) if row.i < row.j else (row.j, row.i)
        separator = separators.get(pair)
        if separator is None or row.correct:
            continue
        if separator in row.decisive_conditioning_subset:
            flagged.append(
                {
                    "dgp": row.dgp, "n": int(row.n), "replicate": int(row.replicate),
                    "i": int(row.i), "j": int(row.j),
                    "decisive_conditioning_subset": list(row.decisive_conditioning_subset),
                    "legitimate_separator": separator,
                }
            )
    return Step5Result(status="FLAGGED" if flagged else "CLEAN", flagged_rows=flagged)


def run_stage8g_audit(raw_path: Path, output_dir: Path) -> tuple[H3Verdict, Step5Result]:
    raw = pd.read_csv(raw_path)
    strength = load_strength(raw_path)
    candidates = enrich_with_chance_correlation(raw, strength)
    table = h3_wrong_retention_table(candidates)
    h3 = evaluate_h3(table)
    step5 = evaluate_step5_validity(candidates)

    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "h3_wrong_retention_table.csv", index=False)
    candidates.to_csv(output_dir / "chance_correlation_candidates.csv", index=False)
    (output_dir / "h3_verdict.json").write_text(json.dumps(asdict(h3), indent=2) + "\n", encoding="utf-8")
    (output_dir / "step5_validity.json").write_text(json.dumps(asdict(step5), indent=2) + "\n", encoding="utf-8")
    return h3, step5


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path, help="path to Stage 8c's own enriched raw_metrics.csv")
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run_stage8g_audit(arguments.raw, arguments.output)


if __name__ == "__main__":
    main()
