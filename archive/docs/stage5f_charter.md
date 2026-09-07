# Stage 5f Charter: Diagnostic — Why Does PC's Precision Beat MINT's on the Composed Noisy Networks? (R6)

Status: **FROZEN before results**
Date: 2026-09-01

## Background and objective

D-051, corrected the same day it was recorded, found that PC's F1
exceeds MINT's own at every tested `N` on both composed noisy networks
(`chain_fork_hub`, `overlap`) — not the "no incumbent dominates"
picture the finding was first described with. This charter is a
diagnostic follow-up, not a retuning attempt: it tests one specific,
falsifiable, mechanistic hypothesis for *why*, using only descriptive
measurement of the existing frozen pipelines — **no change to either
method's algorithm or hyperparameters, and no new tuning of any kind**.

## The hypothesis, stated before any measurement

`mintnet.pipeline.compose.compose_screen_then_prune`'s own docstring
states its scope directly: DPI conditioning is applied **only within
connected candidate-edge components that are a validated clique shape**
(size 3, 4, or 5, `VALIDATED_CLIQUE_SIZES`). Every other component —
including, critically, an **isolated two-node component** (a single
screened-in candidate edge with no other candidate edges touching
either endpoint) — is **passed through into the final graph completely
unconditioned**: `describe_component`'s own `is_validated_shape` check
requires `len(component) in {3, 4, 5}`, so a size-2 component is never
eligible no matter what. On a composed, noisy `p=15` network, a
noise-driven false positive that survives screening but does not
happen to chain into a clean 3/4/5-clique with other screened-in edges
is exactly this case: it becomes its own isolated component and DPI
never gets a chance to remove it.

**Hypothesis:** a material share of MINT's residual false-positive
edges on `chain_fork_hub` and `overlap` are exactly this
passthrough-unconditioned case, not edges DPI examined and wrongly
retained. If true, this is a direct, mechanistic (if partial)
explanation for why PC — which tests every remaining candidate edge
under growing conditioning sets regardless of its local component
shape — achieves higher precision: **PC never gives up on an edge just
because of the topology it happens to sit in; MINT's own conservative
engine currently does.**

This is stated as a hypothesis to be measured, not assumed true. It
may explain all of, part of, or none of PC's precision advantage — the
OR-rule multiple-testing effect discussed in D-051's own rationale
remains a live, un-excluded alternative (or co-occurring) explanation.

## Method: pure attribution, no algorithm change

Reuses `stage5a`'s own DGP registry, condition-seed derivation, and
`alpha(N)`/screening `alpha` exactly as D-047/D-051 used them — same
draws, same MINT configuration, zero modification. A new, additive
instrumentation wrapper around `compose_screen_then_prune` (not a
change to the function itself) records, for every final edge MINT's
conservative engine outputs, which of two categories produced it:

- **`dpi_conditioned`**: the edge survived a candidate component DPI
  actually examined (a validated 3/4/5-node clique).
- **`passthrough_unconditioned`**: the edge survived because its
  component was never eligible for DPI at all (isolated edges and
  non-clique or wrong-size components).

Each final edge is then cross-referenced against the known ground
truth (true edge vs. noise-driven false edge), giving four buckets per
replicate: true-edge/dpi-conditioned, true-edge/passthrough,
false-edge/dpi-conditioned, false-edge/passthrough. Only the two
false-edge buckets bear on the hypothesis; the true-edge buckets are
reported for completeness, not part of the predeclared reading.

## Data-generating processes and grid

`chain_fork_hub` and `overlap` only — the two DGPs where D-051's own
finding holds; `triangle_balanced` is excluded (no material MINT/PC
gap there per D-051) and `triangle_moderate`/`triangle_strong` are
excluded (D-051's finding there runs the opposite direction, a
recall story, not this charter's precision question). Full `N` grid,
identical to Stage 5a (`[400, 500, 600, 750, 1000, 1500, 1750]`),
`2,000` replicates per cell — retained at full scale since MINT's own
per-replicate cost is cheap (D-047: `~0.01s`), so this charter does not
need CI sharding; a local run is expected to finish in minutes.

## Explicit non-goals

- **No change to `compose_screen_then_prune`, `alpha(N)`, screening
  `alpha`, or any other MINT hyperparameter.** This charter measures
  the existing frozen pipeline; it does not propose or test a fix.
- **No re-run of PC or EBICglasso.** This charter is about attributing
  MINT's own false positives, not re-deriving the comparison itself.
- **No claim that this fully explains D-051's finding.** The
  predeclared reading below is scoped to confirming or disconfirming
  whether passthrough-unconditioned edges are a *material* contributor
  — not to quantifying the OR-rule effect or ruling it out.

## Decision structure

Descriptive, not a gate. Predeclared reading, fixed now: for each
`(dgp, N)` cell, compute the share of false-positive edges that are
`passthrough_unconditioned` (of the two false-edge buckets). State,
per DGP (pooling across `N`, since the hypothesis is about a structural
pipeline property, not expected to be `N`-dependent in direction):

1. **MATERIAL** if the passthrough share is `>= 0.5` (a majority of
   MINT's own false positives never reached DPI at all) at a majority
   of tested `N`,
2. **PARTIAL** if the passthrough share is `> 0.1` but `< 0.5` at a
   majority of tested `N` (some contribution, not the dominant one),
3. **MINIMAL** if the passthrough share is `<= 0.1` at a majority of
   tested `N` (the hypothesis is disconfirmed as a material factor;
   the explanation lies elsewhere, e.g. the OR-rule effect).

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate bucket counts for every `(dgp, N)` cell,
and a report presenting the passthrough-share table and the
predeclared per-DGP reading above.

## Consequences

If MATERIAL or PARTIAL: identifies a concrete, actionable candidate
mechanism for a future *implementation* charter (e.g. extending DPI's
own conditioning to non-clique or smaller components, which would be a
real algorithm change requiring its own fresh validation, not
something this diagnostic charter authorizes on its own). If MINIMAL:
rules out this specific structural explanation, redirecting attention
to the OR-rule/multiple-testing hypothesis or another mechanism not
yet named, for a separate future charter. Either way, does not alter
D-047 through D-051 — this charter explains, it does not re-test, the
existing finding.
