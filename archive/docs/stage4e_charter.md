# Stage 4e Charter: Candidacy-Conditional Overlap Metric (R6d)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-032 (Stage 4d) found that the naive indirect-edge TPR metric used
throughout Stage 4 cannot be trusted for the overlap shape below
`N=750`: a cross-branch pair that never clears initial screening is
scored identically to one the engine correctly reasoned about and
pruned, and at low `N` the *former* happens more often (screening power
falls), inflating apparent TPR in exactly the direction that looked like
good news. Overlap's floor below `750` was left explicitly unknown, not
favorable. This charter builds the corrected metric that separates
those two outcomes, mirroring how Stage 1L/1k already separated "does
conditioning work" from "does screening detect a clean component" for
the conservative engine (D-017 vs. D-018) — a distinction Stage 4d's
metric had collapsed back together for the sequential engine.

**Scope, deliberately narrow.** This charter tests **overlap only** —
hub's Stage 4d result was independently verified as genuine (D-032) and
does not need re-testing under a corrected metric. This is a
metric-correction charter, not a new mechanism or new DGP.

## Data-generating process

Identical to Stage 4d's overlap condition: `sample_overlapping_
triangles(n, rng)`, no noise columns. **`N = [300, 500, 600, 650, 700,
750]`** — the full curve, re-simulated fresh at every point (no bookend
reuse this time: Stage 4d's raw evidence recorded only aggregate
`conditionally_tested_pairs`/`confirmed_pairs` counts, not which
*specific* cross-branch pairs were candidates per replicate, so the new
metric cannot be recovered from that file without re-running the
pipeline). **Seed derivation is reused unmodified from Stage 4b/4d**
(`_condition_seed(master_seed, shape_index, sample_index, replicate)`,
`master_seed=20260830`, overlap's `shape_index`), so this charter's
draws are the identical data Stage 4d already analyzed, not a fresh
independent sample — direct comparability, not a new replication.

Same alpha grid as Stage 4a/4b/4d: `[.50, .30, .20, .10, .05, .01,
.005, .001, .0001]`. 2,000 replicates per `N` (development 0-999,
validation 1000-1999).

## Mechanism

No code change to the engine. New **metric extraction only**, using
`mintnet.pipeline.sequential_screen_and_prune_detailed`'s existing
per-pair `PairDecision` list (already returns, for every pair that
cleared initial screening, whether it was ultimately confirmed):

For each of the 4 cross-branch pairs, per replicate:

1. **Candidate?** Present in the `PairDecision` list at all (cleared
   the marginal screening step). If not, this pair is excluded from the
   corrected metric's numerator and denominator entirely — it
   contributes to a separate, purely descriptive **candidacy rate**,
   not to pruning accuracy.
2. **If a candidate, correctly pruned?** `confirmed == False`.

**Corrected metric — pooled, not averaged per replicate** (matching
D-013's own pooled-fraction convention, for the same reason: some
replicates may have zero cross-branch candidates at low `N`, and a
per-replicate ratio is undefined there):

```
candidacy_rate      = (sum of candidate cross-branch pairs across replicates) / (4 * replicates)
conditional_accuracy = (sum of correctly-pruned candidate cross-branch pairs) / (sum of candidate cross-branch pairs)
```

`conditional_accuracy` is the corrected replacement for Stage 4d's
`indirect_prune_tpr` — it answers "when the engine actually got a
chance to reason about this edge, did it get it right," stripped of the
detection-power confound. `candidacy_rate` is reported alongside it,
descriptively, exactly as Stage 1L reported clean-clique rate
descriptively rather than gating on it.

True-edge retention FPR is unchanged from every prior Stage 4 charter
(the 6 within-triangle pairs' own strong signal was never in question).

## Selection and gate

Same procedure and thresholds as Stage 4b/4d (largest development-
eligible `alpha`, confirmed on validation): per `N`,

1. `conditional_accuracy >= .80` with margin `>= .02`.
2. True-edge retention FPR `<= .10` with margin `>= .02`.

**PROCEED** for a given `N` only if both hold on validation with no
recorded error. `candidacy_rate` is **not** a gate criterion — reported
descriptively, per the same "mechanism vs. detection" separation of
concerns Stage 1L used.

**Predeclared expectation, stated before results, not after:** removing
the non-detection "free pass" should make this metric *harder* to
satisfy than Stage 4d's own TPR at low `N`, not easier — the previous
apparent improvement below `750` is predicted to disappear or reverse
once conditional accuracy is measured instead. A monotonically
non-decreasing (or flat) `conditional_accuracy` curve as `N` increases,
the normal direction for every other metric in this project, would
confirm the D-032 diagnosis; a curve that still rises as `N` falls would
mean the artifact explanation itself was incomplete and needs further
diagnosis before trusting either metric.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (per-cross-branch-pair candidacy
and correctness, not just aggregate counts), aggregate metrics
(`candidacy_rate` and `conditional_accuracy` reported separately, per
`N` and `alpha`), the per-`N` decision table, a plot of both curves vs.
`N`, and a report stating whether the predeclared expectation held.

## Consequences

If `conditional_accuracy` PROCEEDs at some `N` below `750`, with
`candidacy_rate` also reported honestly alongside it (even if `<1.0`):
this is a genuine, defensible floor for the *conditioning mechanism*
specifically — but still not a recommendation to use this shape at that
`N`, since a low `candidacy_rate` there would mean many replicates never
get the chance to reason about a real cross-branch pair at all, which
matters for a practitioner regardless of how well the mechanism performs
on the ones it does see. Both numbers must be reported together in any
future use of this result; reporting `conditional_accuracy` alone would
reintroduce a version of the same misleading-completeness problem this
charter exists to fix.

If `conditional_accuracy` never clears the gate below `N=750` at all:
this would mean D-018's original composed-pipeline REASSESS at `N=750`
reflects a genuine conditioning-mechanism limitation for this shape, not
just a detection-power or composition-order artifact — a materially
different, more pessimistic conclusion than D-031's promising `N=750`
near-miss suggested, and would need to be reconciled with it explicitly
before any further Stage 4 work on this shape.

This charter does not authorize any user-facing `N` recommendation —
Stage 4c's cascading-error stress test remains the unconditional
precondition, per the R6a milestone in
`outline/information_network_technical_build_plan_v3_2026-08-30.md`.
