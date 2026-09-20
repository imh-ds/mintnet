"""First implementation of the v1 public API proposed in
`outline/api_design_v1.md` -- built to try the resolved design
decisions in practice, not yet reviewed as final. See that document
for the rationale behind every choice below, especially the
rescue-eligibility decision (report the qualifying rate, default
`enable_rescue` to `False`, require explicit opt-in rather than an
automatic, unvalidated heuristic gate).

**Disclosed dependency, not yet resolved**: the DPI significance
threshold (`alpha`) is computed via `mintnet.experiments.stage1j_fit`'s
`fit_candidate_forms`/`select_form`, whose own six calibration points
(D-008-D-010) were fit on the OLDER Fisher-z engine, not this MI-native
one. This is not a new dependency introduced here -- Stage 7h and
Stage 9c's own already-validated evidence (D-085, D-087) used this
exact same formula to pick `alpha` for
`growing_subset_dpi_structured_density`, so reusing it here keeps this
API consistent with what was actually validated. Replacing it would
require a structured-density-specific alpha(N) recalibration this
project has not yet chartered, and would also mean this API's own
behavior no longer matches the evidence behind D-085/D-087.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from mintnet.experiments.stage1j_fit import fit_candidate_forms, select_form
from mintnet.pipeline.growing_subset_dpi_structured_density import growing_subset_dpi_structured_density
from mintnet.pipeline.stability_rescue import (
    UNRESOLVED_CONDITIONING_SIZE,
    growing_subset_dpi_structured_density_with_stability_rescue,
)
from mintnet.screening import compute_pairwise_screening_evidence, screen_uncorrected

# D-083's own frontier table (docs/decision_log.md, docs/
# validated_operating_ranges.md): smallest resolvable |target_rho| at
# each tested N. Collapsed here into a conservative step function --
# the real table is a small set of tested points, not a continuum, so
# this is a simplification, not a re-derivation. `0.08` uses the
# "comfortable" N=1000 floor, not the "razor-thin" N=750 one (D-083's
# own language) -- a caller who specifically wants the thinner N=750
# window for a 0.08 effect must justify that themselves, this API
# does not offer it as a default.
_MIN_N_FOR_RESOLVABLE_EFFECT: tuple[tuple[float, int], ...] = (
    (0.12, 400),
    (0.08, 1000),
)

# D-087's own calibrated pi_min, independently per tested N -- does
# NOT interpolate (see docs/decision_log.md D-087 and
# outline/package_scope_v1.md section 5). Any other N falls back to
# the stricter validated value with an explicit warning.
_VALIDATED_PI_MIN_BY_N: dict[int, float] = {750: 0.5, 1500: 0.6}
_CONSERVATIVE_PI_MIN_FALLBACK = 0.6

_ALPHA_FORMULA = select_form(fit_candidate_forms())


class UntestedEffectSizeError(ValueError):
    """Raised when `weakest_expected_effect` falls below every
    effect size D-083 actually tested (`0.08`) -- there is no
    evidence-backed minimum N to recommend below this, so this API
    refuses to guess one rather than silently pick something."""


@dataclass(frozen=True)
class EdgeDecision:
    i: int
    j: int
    retained: bool
    conditioning_size_used: int
    confidence: float
    """Ordinal informativeness signal (D-083, D-085) -- NOT a
    calibrated probability. Higher means more decisive evidence behind
    this specific decision, nothing more; do not present as e.g. "80%
    likely correct" without the recalibration charter this project has
    not yet done."""
    low_confidence: bool
    """True only for edges D-085 actually found to be at risk: RETAINED
    edges at conditioning depth >= 2 that rescue did not confirm.
    Pruned edges are essentially always safe regardless of depth
    (D-085's own 99.96% retain reliability) and are never flagged."""
    rescue_applied: bool
    pi_final: float | None


@dataclass(frozen=True)
class DiscoveryResult:
    adjacency: np.ndarray
    edges: list[EdgeDecision]
    qualifying_rate: float
    """Fraction of screened candidate pairs reaching conditioning depth
    >= 2 -- always computed, regardless of `enable_rescue`. D-086 found
    this at ~7.4% for the one shape bootstrap-rescue is validated for
    (chain_fork_hub) and ~100% for the one shape it is NOT (overlap).
    Nothing is known about values in between (see
    outline/api_design_v1.md open question 1) -- this number is
    reported so the caller can weigh that themselves, not because this
    package can tell them what it means."""
    rescue_used: bool
    warnings: list[str] = field(default_factory=list)


def _required_min_n(weakest_expected_effect: float) -> int:
    for threshold, min_n in sorted(_MIN_N_FOR_RESOLVABLE_EFFECT, reverse=True):
        if weakest_expected_effect >= threshold:
            return min_n
    raise UntestedEffectSizeError(
        f"weakest_expected_effect={weakest_expected_effect} is below every effect size D-083 "
        "tested (smallest: 0.08) -- no evidence-backed minimum N exists for this. Either revise "
        "the expected effect size or treat this as genuinely untested territory."
    )


# A small margin above D-086's own measured ~7.4% qualifying rate for
# chain_fork_hub, the one condition rescue actually has evidence for.
_RESCUE_SUPPORTED_QUALIFYING_RATE_CEILING = 0.15


def _rescue_qualifying_rate_warning(qualifying_rate: float) -> str:
    """Deliberately NOT a "closer to X than Y" comparison -- an earlier
    version of this function did that and, when tried against a real
    sample actually drawn from the overlap DGP itself, called a 43.75%
    qualifying rate "reasonably well-supported" purely because it was
    numerically nearer chain_fork_hub's own ~7.4% than overlap's own
    ~100% -- while the data was, in fact, from the unvalidated shape.
    A single dataset's rate varies substantially and "closer in
    absolute distance to one anchor" is not evidence about which
    regime it resembles. Only affirm support near the one point with
    real evidence; anything else gets a flat "not validated," with no
    comparative language implying safety."""
    if qualifying_rate <= _RESCUE_SUPPORTED_QUALIFYING_RATE_CEILING:
        return (
            f"qualifying_rate={qualifying_rate:.3f} is near chain_fork_hub's own validated "
            "~7.4% reference point (D-087) -- the one condition rescue has real evidence "
            "for, at N in {750, 1500}."
        )
    return (
        f"qualifying_rate={qualifying_rate:.3f} is NOT near the ~7.4% rate rescue was "
        "actually validated at (D-087) -- rescue is being applied anyway because "
        "enable_rescue=True was set, but this is unvalidated territory, regardless of "
        "how far this rate is from overlap's own unvalidated ~100% reference (D-086)."
    )


def _resolve_pi_min(n: int, warnings: list[str]) -> float:
    if n in _VALIDATED_PI_MIN_BY_N:
        return _VALIDATED_PI_MIN_BY_N[n]
    warnings.append(
        f"N={n} has no calibrated pi_min (only N=750/1500 are validated, D-087) -- "
        f"falling back to the stricter validated value ({_CONSERVATIVE_PI_MIN_FALLBACK}) as a "
        "disclosed conservative default, not an interpolated or extrapolated estimate."
    )
    return _CONSERVATIVE_PI_MIN_FALLBACK


def discover(
    data: np.ndarray,
    *,
    screening_alpha: float = 0.001,
    max_conditioning_size: int = 4,
    weakest_expected_effect: float,
    enable_rescue: bool = False,
    bootstraps: int = 10,
    random_state: int | np.random.Generator | None = None,
) -> DiscoveryResult:
    """See outline/api_design_v1.md for the full design rationale.
    `weakest_expected_effect` is required, not defaulted -- it directly
    determines the minimum usable N per D-083's own frontier table, and
    silently picking one for the caller would silently pick their N
    floor too."""
    data = np.asarray(data, dtype=float)
    if data.ndim != 2:
        raise ValueError(f"data must be 2D (N, p); got shape {data.shape}")
    n, p = data.shape
    warnings: list[str] = []

    required_n = _required_min_n(weakest_expected_effect)
    if n < required_n:
        raise ValueError(
            f"N={n} is below the minimum ({required_n}) D-083 validated for detecting an effect "
            f"as weak as {weakest_expected_effect} -- this is a hard accessibility floor, not a "
            "soft recommendation."
        )

    if n not in (750, 1500):
        warnings.append(
            f"N={n} is outside the two points D-087 validated bootstrap-rescue for (750, 1500) "
            "-- rescue's own calibration does not interpolate; if enable_rescue=True, the "
            "conservative pi_min fallback is used instead of a matched calibration."
        )

    rng = np.random.default_rng(random_state)
    master_seed = int(rng.integers(0, 2**31 - 1))

    alpha = float(_ALPHA_FORMULA.predict(float(n)))
    evidence = compute_pairwise_screening_evidence(data)
    flagged = screen_uncorrected(evidence, screening_alpha)

    point_estimate = growing_subset_dpi_structured_density(
        data, flagged, alpha, master_seed=master_seed, replicate=0, max_conditioning_size=max_conditioning_size
    )

    candidate_pairs = [(i, j) for i in range(p) for j in range(i + 1, p) if flagged[i, j]]
    deep_pairs = [
        (i, j) for i, j in candidate_pairs
        if point_estimate.conditioning_size_used[(i, j)] >= UNRESOLVED_CONDITIONING_SIZE
    ]
    qualifying_rate = len(deep_pairs) / len(candidate_pairs) if candidate_pairs else 0.0

    if enable_rescue and deep_pairs:
        warnings.append(_rescue_qualifying_rate_warning(qualifying_rate))
        pi_min = _resolve_pi_min(n, warnings)
        rescue_result = growing_subset_dpi_structured_density_with_stability_rescue(
            data, flagged, alpha, max_conditioning_size=max_conditioning_size,
            screening_alpha=screening_alpha, bootstraps=bootstraps, pi_min=pi_min,
            master_seed=master_seed, replicate=0, bootstrap_rng=rng, n_jobs="auto",
        )
        final_adjacency = rescue_result.final_adjacency
        pi_final_by_pair = rescue_result.pi_final
        rescue_used = True
    else:
        if enable_rescue and not deep_pairs:
            warnings.append("enable_rescue=True but no candidate pair reached conditioning depth >= 2 -- nothing to rescue.")
        final_adjacency = point_estimate.adjacency
        pi_final_by_pair = {}
        rescue_used = False

    edges = _build_edge_decisions(
        candidate_pairs=candidate_pairs, deep_pairs=deep_pairs, final_adjacency=final_adjacency,
        conditioning_size_used=point_estimate.conditioning_size_used, confidence=point_estimate.confidence,
        pi_final_by_pair=pi_final_by_pair, rescue_used=rescue_used,
    )

    return DiscoveryResult(
        adjacency=final_adjacency, edges=edges, qualifying_rate=qualifying_rate,
        rescue_used=rescue_used, warnings=warnings,
    )


def _build_edge_decisions(
    *,
    candidate_pairs: list[tuple[int, int]],
    deep_pairs: list[tuple[int, int]],
    final_adjacency: np.ndarray,
    conditioning_size_used: dict[tuple[int, int], int],
    confidence: dict[tuple[int, int], float],
    pi_final_by_pair: dict[tuple[int, int], float],
    rescue_used: bool,
) -> list[EdgeDecision]:
    """Pulled out of `discover` so the safety-critical flagging logic
    (which retained edges are at risk -- see D-085/D-087, and the
    corrected direction noted in outline/api_design_v1.md) can be unit
    tested directly against synthetic inputs, without paying for an
    actual structured-density search."""
    deep_pair_set = set(deep_pairs)
    edges: list[EdgeDecision] = []
    for i, j in candidate_pairs:
        retained = bool(final_adjacency[i, j])
        depth = conditioning_size_used[(i, j)]
        pi_final = pi_final_by_pair.get((i, j))
        pi_final = float(pi_final) if pi_final is not None and not np.isnan(pi_final) else None
        rescue_applied_here = rescue_used and (i, j) in deep_pair_set
        # Only a RETAINED edge at depth >= 2 is the risk category D-085
        # found (false_wrongly_retained collapses .906 -> .119 by
        # depth); a pruned edge is essentially always safe regardless
        # of depth and is never flagged.
        low_confidence = retained and (i, j) in deep_pair_set and not (rescue_applied_here and pi_final is not None)
        edges.append(
            EdgeDecision(
                i=i, j=j, retained=retained, conditioning_size_used=depth,
                confidence=float(confidence[(i, j)]),
                low_confidence=low_confidence, rescue_applied=rescue_applied_here, pi_final=pi_final,
            )
        )
    return edges
