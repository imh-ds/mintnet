"""Population-level ground truth for D-072's own flagged decisive
conditioning subsets. See docs/stage8i_charter.md.

`chain_fork_hub` (`stage4l.py`) and `overlap` (`stage2d.py`) are both
built by column-stacking mutually independent motif blocks (chain,
fork, hub or overlap-triangles, noise) -- no cross-block term anywhere
in either `_sample_network`. Each block's own population covariance is
known in closed form, so the full `p=15` population covariance matrix
for either network can be constructed exactly, with no sampling at
all, and evaluated against any conditioning subset via the standard
Gaussian conditional-covariance formula. This module computes that,
purely analytically, against D-072's own already-collected flagged
evidence (`stage8g_structural_audit.enrich_with_chance_correlation`'s
own output) -- zero new stochastic evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from mintnet.experiments.stage8g_structural_audit import _LEGITIMATE_SEPARATOR

# Block membership for each network's own 15 columns -- established by
# direct inspection of stage4l.py's/stage2d.py's own _sample_network
# (independent rng draws per block, np.column_stack, no cross-block
# term). Each noise column is its own singleton block.
_CHAIN_FORK_HUB_BLOCKS: tuple[frozenset[int], ...] = (
    frozenset({0, 1, 2}), frozenset({3, 4, 5}), frozenset({6, 7, 8}),
    *(frozenset({c}) for c in range(9, 15)),
)
_OVERLAP_BLOCKS: tuple[frozenset[int], ...] = (
    frozenset({0, 1, 2}), frozenset({3, 4, 5}), frozenset({6, 7, 8, 9, 10}),
    *(frozenset({c}) for c in range(11, 15)),
)
_BLOCKS: dict[str, tuple[frozenset[int], ...]] = {
    "chain_fork_hub": _CHAIN_FORK_HUB_BLOCKS,
    "overlap": _OVERLAP_BLOCKS,
}
_P: dict[str, int] = {"chain_fork_hub": 15, "overlap": 15}


def _chain_like_block(strength: float) -> np.ndarray:
    """Cov for a 3-node path a-b-c (chain X1->X2->X3, or fork's own
    child-center-child with the center in the middle position): adjacent
    pairs correlate `strength`, the endpoints correlate `strength**2`."""
    return np.array(
        [[1.0, strength, strength**2], [strength, 1.0, strength], [strength**2, strength, 1.0]]
    )


def _hub_block(strength: float) -> np.ndarray:
    """Cov for hub, child1, child2 (in that column order): hub
    correlates `strength` with each child; children correlate
    `strength**2` with each other via the shared hub."""
    return np.array(
        [[1.0, strength, strength], [strength, 1.0, strength**2], [strength, strength**2, 1.0]]
    )


def _overlap_block() -> np.ndarray:
    """Cov for the shared-node-overlap motif's own 5 columns, from the
    already-committed precision matrix in mintnet.simulation.motifs.

    `sample_overlapping_triangles` standardizes each SAMPLED column to
    unit variance at runtime (`(data - mean) / std`), which converges,
    as N grows, to rescaling `inv(precision)` into a correlation matrix
    -- not `inv(precision)` itself, whose own raw diagonal is not `1`.
    Partial correlation is scale-invariant, so this rescaling does not
    change any partial-correlation value, but it does matter for the
    covariance matrix's own diagonal to legitimately read as `1`."""
    from mintnet.simulation.motifs import _OVERLAPPING_TRIANGLES_PRECISION

    raw_covariance = np.linalg.inv(_OVERLAPPING_TRIANGLES_PRECISION)
    scale = np.sqrt(np.diag(raw_covariance))
    return raw_covariance / np.outer(scale, scale)


def build_covariance(dgp: str, strength: float) -> np.ndarray:
    """The exact p=15 population covariance matrix for `dgp` at
    `strength` -- block-diagonal, each block's own closed-form value,
    zero everywhere else (independent blocks, independent noise)."""
    p = _P[dgp]
    covariance = np.eye(p)
    if dgp == "chain_fork_hub":
        blocks = {
            (0, 1, 2): _chain_like_block(strength),
            (3, 4, 5): _chain_like_block(strength),
            (6, 7, 8): _hub_block(strength),
        }
    elif dgp == "overlap":
        blocks = {
            (0, 1, 2): _chain_like_block(strength),
            (3, 4, 5): _chain_like_block(strength),
            (6, 7, 8, 9, 10): _overlap_block(),
        }
    else:
        raise ValueError(f"unknown dgp: {dgp!r}")

    for columns, block_covariance in blocks.items():
        for row_offset, row in enumerate(columns):
            for col_offset, col in enumerate(columns):
                covariance[row, col] = block_covariance[row_offset, col_offset]
    return covariance


def population_partial_correlation(covariance: np.ndarray, i: int, j: int, subset: tuple[int, ...]) -> float:
    """Population partial correlation of columns i, j given `subset`,
    computed from the true covariance matrix -- no sampled data."""
    if not subset:
        denom = np.sqrt(covariance[i, i] * covariance[j, j])
        return float(covariance[i, j] / denom)

    subset = tuple(subset)
    sigma_ss = covariance[np.ix_(subset, subset)]
    sigma_ss_inv = np.linalg.inv(sigma_ss)
    sigma_i_s = covariance[i, subset]
    sigma_j_s = covariance[j, subset]

    conditional_ii = covariance[i, i] - sigma_i_s @ sigma_ss_inv @ sigma_i_s
    conditional_jj = covariance[j, j] - sigma_j_s @ sigma_ss_inv @ sigma_j_s
    conditional_ij = covariance[i, j] - sigma_i_s @ sigma_ss_inv @ sigma_j_s
    return float(conditional_ij / np.sqrt(conditional_ii * conditional_jj))


def _block_of(dgp: str, column: int) -> frozenset[int]:
    for block in _BLOCKS[dgp]:
        if column in block:
            return block
    raise ValueError(f"column {column} not found in any block for {dgp!r}")


def classify_subset_members(dgp: str, pair: tuple[int, int], decisive_conditioning_subset: tuple[int, ...]) -> dict[str, int]:
    """For every member of `decisive_conditioning_subset` besides `pair`'s
    own known legitimate separator, classify it as "same_block" (another
    member of the pair's own motif block) or "different_block" (any
    other block, including noise)."""
    separator = _LEGITIMATE_SEPARATOR.get(dgp, {}).get(pair)
    pair_block = _block_of(dgp, pair[0])
    same_block = 0
    different_block = 0
    for column in decisive_conditioning_subset:
        if column == separator:
            continue
        if column in pair_block:
            same_block += 1
        else:
            different_block += 1
    return {"same_block": same_block, "different_block": different_block}


_POPULATION_ROW_COLUMNS = (
    "dgp", "n", "replicate", "i", "j", "correct", "decisive_conditioning_subset",
    "population_partial_correlation", "same_block_extra", "different_block_extra", "is_named_indirect_pair",
)


def enrich_with_population_ground_truth(candidates: pd.DataFrame, strength_by_dgp: dict[str, float]) -> pd.DataFrame:
    """For every row in `candidates` (Stage 8g's own flagged, `conditioning_
    size_used >= 2` false edges), compute the population partial correlation
    of the tested pair given its own decisive conditioning subset, and
    classify the subset's own non-separator members."""
    covariances = {dgp: build_covariance(dgp, strength) for dgp, strength in strength_by_dgp.items()}
    rows: list[dict[str, object]] = []
    for row in candidates.itertuples(index=False):
        pair = (int(row.i), int(row.j))
        subset = tuple(row.decisive_conditioning_subset)
        population_partial = population_partial_correlation(covariances[row.dgp], pair[0], pair[1], subset)
        separator_defined = pair in _LEGITIMATE_SEPARATOR.get(row.dgp, {})
        classification = (
            classify_subset_members(row.dgp, pair, subset) if separator_defined else {"same_block": None, "different_block": None}
        )
        rows.append(
            {
                "dgp": row.dgp, "n": int(row.n), "replicate": int(row.replicate),
                "i": pair[0], "j": pair[1], "correct": bool(row.correct),
                "decisive_conditioning_subset": subset,
                "population_partial_correlation": population_partial,
                "same_block_extra": classification["same_block"],
                "different_block_extra": classification["different_block"],
                "is_named_indirect_pair": separator_defined,
            }
        )
    return pd.DataFrame(rows, columns=list(_POPULATION_ROW_COLUMNS))


@dataclass(frozen=True)
class H6Verdict:
    status: str  # "CONFIRMED" or "NOT_CONFIRMED"
    tolerance: float
    max_abs_population_partial_correlation: float
    violating_row_count: int
    total_row_count: int


def evaluate_h6(enriched: pd.DataFrame, tolerance: float = 0.05) -> H6Verdict:
    """Scoped to WRONGLY-RETAINED edges only (`correct == False`) --
    the population this charter's own H6 actually concerns (D-069's/
    D-072's own mechanism question). A CORRECTLY-pruned edge's own
    decisive subset is the one that *succeeded* in looking independent;
    it is not required to be a formal population separator to do that
    (a subset can carry a small, genuinely nonzero population relationship
    yet still be too weak to reject at a given N/alpha) -- a nonzero
    population value there is expected and benign, not evidence of a
    population-level conditioning-set error, and would otherwise dilute
    this verdict with an unrelated, already-understood phenomenon
    (confirmed empirically: 370/2,163 correctly-pruned rows in the real
    evidence show a small nonzero population value this way, versus only
    9/5,040 wrongly-retained rows -- see docs/decision_log.md D-074)."""
    wrongly_retained = enriched.loc[~enriched["correct"]] if "correct" in enriched.columns and not enriched.empty else enriched
    if wrongly_retained.empty:
        return H6Verdict(status="NOT_CONFIRMED", tolerance=tolerance, max_abs_population_partial_correlation=0.0, violating_row_count=0, total_row_count=0)
    magnitudes = wrongly_retained["population_partial_correlation"].abs()
    violating = int((magnitudes > tolerance).sum())
    return H6Verdict(
        status="CONFIRMED" if violating > 0 else "NOT_CONFIRMED",
        tolerance=tolerance,
        max_abs_population_partial_correlation=float(magnitudes.max()),
        violating_row_count=violating,
        total_row_count=len(wrongly_retained),
    )


def run_stage8i_audit(raw_path: Path, output_dir: Path) -> H6Verdict:
    """Reads Stage 8c's own enriched raw_metrics.csv directly (the same
    input Stage 8g's own audit consumes), so `decisive_conditioning_
    subset` stays a real Python tuple throughout -- no CSV round-trip
    string-parsing of a previously-written candidates table."""
    from mintnet.experiments.stage8g_structural_audit import enrich_with_chance_correlation, load_strength

    raw = pd.read_csv(raw_path)
    strength = load_strength(raw_path)
    candidates = enrich_with_chance_correlation(raw, strength)
    strength_by_dgp = {dgp: strength for dgp in candidates["dgp"].unique()}

    enriched = enrich_with_population_ground_truth(candidates, strength_by_dgp)
    h6 = evaluate_h6(enriched)

    output_dir.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(output_dir / "population_ground_truth.csv", index=False)
    (output_dir / "h6_verdict.json").write_text(json.dumps(asdict(h6), indent=2) + "\n", encoding="utf-8")
    return h6
