# Stage 4a Charter: Sequential/Greedy Conditioning Engine — Motif Validation in Isolation (R6a)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-026 through D-029 established that the validated (conservative) engine's
own composed-pipeline design has a specific, mechanical cost: before it
will attempt any conditioning-based pruning within a candidate component,
it requires **every pair in that component to clear screening
simultaneously**. For a weak-signal shared-cause shape, this conjunctive
requirement compounds several individually-plausible detections into one
much-less-likely joint event, which is the concrete reason that shape
needs `N=1500`-`1750` rather than the general `N=750` floor. This is a
property of the conservative engine's *composition* logic, not of the
underlying conditional-independence test itself, which is unchanged and
already validated (`docs/stage1b_charter.md` onward, D-008).

This charter begins a second, independently validated engine: build the
final graph **sequentially** — rank candidate pairs by raw association
strength, confirm the strongest as direct edges immediately, and test each
remaining candidate by conditioning on *already-confirmed* neighbors,
rather than waiting for the whole component to be simultaneously clean.
This is explicitly not a replacement for the conservative engine (see
`outline/information_network_technical_build_plan_v3_2026-08-30.md`'s
Version 3 Revision Notice) — it is a new mechanism entering its own
falsification arc, starting from the same smallest falsifiable slice the
conservative engine itself started from: hand-generated, three-node
motifs, no extra noise columns, no separate screening-then-compose split
(at three variables the two collapse into the same question this charter
tests directly).

**This charter deliberately does not yet test the weak shared-cause shape
this whole initiative is motivated by.** That comparison requires a
multi-node candidate component (the hub or shared-overlap shape) and is
reserved for Stage 4b, mirroring how the conservative engine validated
three-node motifs (`docs/stage1b_charter.md`) before hub/overlap
composition (`docs/stage1k_charter.md`, `docs/stage1L_charter.md`).
Skipping straight to the motivating case here would confound two
questions — "does the sequential mechanism work at all" and "does it need
less data on the specific hard shape" — that should be answered
separately.

## Mechanism

Frozen algorithm, applied directly to raw data (no separate screening
module call — the ranking step below plays that role):

1. **Score.** Compute every pair's marginal Fisher-z evidence (reuses
   `mintnet.screening.compute_pairwise_screening_evidence` unmodified).
2. **Seed the candidate set.** A pair enters the candidate set if its
   marginal `p <= alpha` (the same single `alpha` used in step 3 — this
   charter deliberately uses one threshold, not two, to keep the first
   test of this mechanism as simple as the conservative engine's own
   first charter was).
3. **Rank.** Order candidate pairs by descending `|z|` (strongest
   association first).
4. **Sequential confirm-or-test**, processing candidates in that order:
   - If neither endpoint has any variable `k` such that `(i, k)` and
     `(j, k)` are **both already confirmed**, confirm `(i, j)` as a direct
     edge immediately (nothing yet to condition on).
   - Otherwise, for every such `k`, test the partial correlation
     `r_ij.k` via the identical Fisher z-transform Stage 1b uses
     (`z = atanh(r) * sqrt(N - 4)`, two-sided `p`-value). If **any**
     qualifying `k` reduces the pair to non-significance (`p > alpha`),
     prune `(i, j)` **permanently** — it is not re-tested against a
     different `k` or reconsidered later. Otherwise confirm it.
5. Pairs that never entered the candidate set in step 2 are absent from
   the final graph without ever being conditioned on.

This is the one-directional-commitment design flagged as this engine's
central risk during planning: once pruned, an edge cannot return, even if
a later-processed pair would have changed the picture. Stage 4c is where
that risk gets its own dedicated stress test — not here.

## Data-generating process

Identical to `docs/stage1b_charter.md`, reused unmodified for direct,
apples-to-apples comparability against the conservative engine's own
first isolation result (D-008): chain (`X1 -> X2 -> X3`), measured fork
(`X1 <- X2 -> X3`), and the `balanced`/`moderate`/`strong` triangle
precision-matrix fixtures. `N = [100, 200, 300, 500, 750, 1000]`,
strengths `a = b = [.3, .5, .7]`, 500 replicates, master seed `20260830`,
development replicates 0-249, validation replicates 250-499.

## Selection and gate

Structurally identical to `docs/stage1b_charter.md`'s own gate, substituting
this charter's single `alpha` for that charter's `alpha`. Frozen grid:
`[.50, .30, .20, .10, .05, .01, .005, .001, .0001]`. Development
replicates (0-249) select the lexicographically lowest adjacent `alpha`
pair that, pooled across all strengths, families, and `N >= 500`, meets:

1. Chain and fork indirect-edge (`X1`, `X3`) pruning TPR each at least
   `.80`.
2. Triangle true-edge retention FPR (each of the three edges, all three
   families) at most `.10`.
3. No estimator, DGP, regression, or Cholesky error is recorded.

Validation replicates (250-499) cannot alter selection. **PROCEED** only
if the selected `alpha` clears every validation cell individually at each
`N in [500, 750, 1000]` and strength. Otherwise **REASSESS**.

**Direct comparison, not just an independent gate:** report this
mechanism's per-`(N, alpha)` chain/fork TPR and triangle FPR numbers
alongside Stage 1b's own recorded numbers at the same cells
(`docs/decision_log.md` D-008 evidence), descriptively. A materially
worse triangle FPR at any `N` where Stage 1b passed would indicate the
one-directional-commitment design is already costing accuracy even on
the easy motifs this charter tests — worth flagging explicitly before
Stage 4b even runs, not discovered only when the harder shape fails.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate per-pair evidence (marginal candidacy,
processing rank, which `k` (if any) was tested, conditional `p`-value,
final retain/prune decision), aggregate metrics, the selection table, the
validation decision, and a report comparing this engine's numbers to
Stage 1b's recorded ones at matching cells.

## Consequences

If PROCEED with a selected `alpha` and no material regression against
Stage 1b's own numbers: the sequential mechanism is validated as
correct on the smallest falsifiable case, clearing the way for Stage 4b
(hub/overlap components, hand-fed directly, then composed with real
noise columns) — the charter that actually tests whether less data is
needed for the weak shared-cause shape.

If REASSESS: the one-directional, rank-then-condition design has a basic
correctness problem even without any noise columns or weak signal to
contend with. This would need diagnosis (which motif and cell drives it,
and whether the failure is in ranking order, the "any qualifying k"
pruning rule, or the marginal screening step) before any further Stage 4
work — the same discipline used when the original tolerant-DPI mechanism
failed and was diagnosed before Stage 1b was chartered (D-002).

This charter does not authorize any user-facing exposure of this engine,
a default `engine` parameter, or a claim that it needs less data than the
conservative engine for any shape — those all remain open until Stage 4b
and Stage 4c (the cascading-error stress test) conclude, per this file's
own new R6a milestone in `outline/information_network_technical_build_plan_v3_2026-08-30.md`.
