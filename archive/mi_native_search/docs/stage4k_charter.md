# Stage 4k Charter: Shape/Signal-Strength Sweep for the Sequential Engine (R6k)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

Every Stage 4 charter to date except 4a/4b/4c has tested exactly one
DGP: the shared-node-overlap shape's one fixed, weak (`~.135`)
cross-branch correlation. That single case drove the entire alpha(N)
recalibration line of work (D-034 through D-039) and the discovery that
a fixed, `N`-independent `alpha` is miscalibrated for weak signal. What
remains untested is whether this is a **general property of weak
signal under the sequential engine** (any shape, low enough correlation,
needs the same treatment) or a **property specific to the overlap
shape's particular DGP** (its fixed `-0.25` precision structure, its
five-variable topology) — the R6a milestone's own precondition ("a
broader shape/signal-strength sweep") for any user-facing recommendation
has not yet been addressed for any shape other than overlap and hub
(D-030/D-031, at a single fixed operating point each).

**Objective:** test whether the sequential engine, using **D-012's
already-frozen `alpha(N)` formula unmodified** — the same one long used
for the conservative engine's DPI step, never previously tested against
the sequential engine at all except once, incidentally, in Stage 4a's
direct-comparison charter — holds up across a grid of shapes and signal
strengths, without any new per-cell fitting. This is deliberately a
**cheap, broad, descriptive sweep**, not another deep per-shape
calibration project like Stage 4e-4j's overlap work: the question is
whether that expensive treatment generalizes or was overlap-specific,
not to build a second one.

**Scope, deliberately narrow:** isolated conditioning only (a single
3-column motif tested alone), mirroring the project's own established
order (Stage 1's isolated triads before Stage 2's composed pipeline;
Stage 1L/4b's isolated overlap before Stage 2d/4h's composed one). A
composed, `p`-large, noisy version of this sweep is explicitly out of
scope and would be a natural follow-up only if this charter PROCEEDs.

## Data-generating processes

**Three motifs, chosen for structural symmetry** (each yields exactly
three measured columns, two direct edges, and one weak indirect pair —
directly comparable across shapes with no per-shape metric redesign
needed):

1. **Chain**: `mintnet.simulation.sample_chain(n, strength, rng)` —
   columns `(0, 1, 2)`. Direct edges `(0,1)`, `(1,2)`. Indirect pair
   `(0, 2)`.
2. **Fork**: `mintnet.simulation.sample_measured_fork(n, strength,
   rng)` — columns `(0, 1, 2)`, `1` the shared center. Direct edges
   `(0,1)`, `(1,2)`. Indirect pair `(0, 2)`.
3. **Hub, 2 children**: `mintnet.simulation.sample_hub(n, strength,
   children=2, rng)` — columns `(0, 1, 2)`, `0` the hub. Direct edges
   `(0,1)`, `(0,2)`. Indirect pair `(1, 2)`. **Deliberately restricted
   to 2 children** for structural symmetry with chain/fork in this
   charter; this does not touch or reopen Stage 4b/4d's own hub result
   (which used a different, larger child count).

**Signal-strength grid: `strength = [0.30, 0.40, 0.50, 0.70]`.** For
all three motifs, the direct-edge correlation equals `strength`
exactly, and the indirect/marginal correlation induced by the shared
node equals `strength^2` — so `strength=0.40` (indirect `~.16`)
brackets the overlap shape's own historically-difficult `~.135`
correlation from just above, `strength=0.30` (indirect `.09`) brackets
it from below (a *harder* case than anything tested so far), and
`0.50`/`0.70` (indirect `.25`/`.49`) cover comfortably-strong signal
for contrast.

**Sample sizes: `N = [750, 1000, 1500]`.** Deliberately kept **inside**
D-012's own validated interpolation range (`[700, 3000]`,
`docs/validated_operating_ranges.md`) — this charter tests whether that
existing formula transfers to the sequential engine and to new shapes,
it does not test extrapolating it. `N=750` and `N=1500` also match the
general floor points used throughout Stage 2/3.

**Alpha: `alpha(N) = f(N)`, D-012's own formula, re-derived
deterministically** via `mintnet.experiments.stage1j_fit.
fit_candidate_forms`/`select_form` on its own frozen six-point fitting
data — not re-fit, not re-selected, identical machinery reused
unmodified. The same single `alpha` value is used for every shape and
every strength at a given `N` — this charter is explicitly testing
whether one shared, shape/strength-agnostic formula suffices, not
building shape-specific ones.

**Seed derivation:** a new stream tag distinct from every prior Stage 4
charter (`_condition_seed(master_seed, motif_index, strength_index,
sample_index, replicate)`, `master_seed=20260830`), `1,000` replicates
per cell (development `0`-`499`, validation `500`-`999` — a lighter
split than the overlap-calibration charters, matching this charter's
own descriptive-sweep scope; no fitting happens on this data, so the
split exists for consistency with the project's own hygiene convention,
not to guard against overfitting a formula).

## Mechanism

For each of the `3 (motif) x 4 (strength) x 3 (N) = 36` cells: sample
the motif in isolation, run `mintnet.pipeline.
sequential_screen_and_prune_detailed(data, alpha)` unmodified
(`alpha = f(N)` per the shared formula above), and record:

1. **Candidate?** Whether the one indirect pair cleared initial
   screening at all (present in the returned `PairDecision` list).
2. **Correctly pruned?** If a candidate, whether it was ultimately
   pruned (`confirmed == False`) rather than wrongly retained.
3. **True-edge retention.** Whether both direct edges survive.

Pooled per cell (matching D-013/Stage 4e's own pooled-fraction
convention): `candidacy_rate`, `conditional_accuracy` (`None` if zero
candidates), `true_edge_prune_fpr`.

## Gate

Per cell, on validation replicates (`500`-`999`) only:

1. `conditional_accuracy >= .80` with margin `>= .02`.
2. True-edge retention FPR `<= .10` with margin `>= .02`.
3. Candidacy rate reported descriptively alongside (not gated), per
   Stage 4e's own established practice — a cell with near-zero
   candidacy makes `conditional_accuracy` for that cell close to
   meaningless even if it numerically clears the floor, and must be
   flagged as such in the report regardless of formal PROCEED/REASSESS
   status.

**PROCEED** only if all `36` cells individually PROCEED, with no
recorded error. **REASSESS** otherwise.

**Full-grid reporting requirement (mirrors Stage 4j's own partial-
success requirement):** report every cell's individual status
regardless of the overall outcome, organized as three tables (one per
motif) crossing strength against `N`, so any pattern — failures
concentrated at low strength, at low `N`, or specific to one motif — is
visible directly rather than collapsed into a single PROCEED/REASSESS
verdict.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, D-012's re-derived formula and its parameters (confirming it
was not altered), raw per-replicate evidence for all `36` cells, the
full per-cell decision table (three motifs x four strengths x three
`N`), a summary noting whether failures (if any) cluster by strength,
by `N`, or by motif, and a plot showing `conditional_accuracy` and
`candidacy_rate` against `strength` for each motif (one line per `N`),
so the shape of any strength-dependence is visible directly, not just
its gate outcome.

## Consequences

If PROCEED: this is strong evidence that D-012's existing `alpha(N)`
formula, and the general `N>=750` floor, generalize to the sequential
engine across multiple shapes and a signal-strength range that brackets
overlap's own historically-difficult correlation from both sides —
meaning the overlap shape's miscalibration (D-032 through D-039) was a
property of its specific DGP (five-variable topology, fixed precision
structure), not a systemic property of the sequential engine under weak
signal generally. This substantially derisks a user-facing
recommendation for chain/fork/hub-type shapes specifically, though it
still does not authorize one on its own — Stage 4c's cascading-error
caveats apply here too, and this charter is isolated-only, not composed
with screening or noise, per its own stated scope.

If REASSESS: report exactly which cells failed, organized by the three
axes above. **If failures cluster at low strength regardless of
motif**, that would suggest a real, general weak-signal miscalibration
issue independent of topology, meaning the alpha(N) recalibration
treatment Stage 4e-4j built for overlap specifically may need to become
a general pattern applied per-shape (or a single strength-aware formula
covering all shapes) rather than an overlap-only special case. **If
failures cluster by motif instead** (e.g., only hub, or only fork, fails
at otherwise-passing strength/`N` combinations), that would point to a
shape-specific mechanism difference worth its own dedicated
investigation, the way overlap's shared-node structure got one. Either
outcome is genuinely informative and neither retroactively changes any
prior Stage 4 result — this charter only ever reuses D-012's existing
formula and Stage 1's motif simulators, unmodified.
