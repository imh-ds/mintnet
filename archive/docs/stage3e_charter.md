# Stage 3e Charter: Stability-Filtering Rescue at p=30 Overlap (R4e)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-026/D-027 characterized the shared-node-overlap DGP's `p=30` floor
precisely: `N=1500` and `N=1600` REASSESS (overlap indirect TPR `.762`/
`.786`, both below the `.80` gate), `N=1750` PROCEEDs (`.815`). That
floor was located by *finding more `N`* — the same lever D-010/D-011
used for the general DPI floor. Stage 3b already established a
different lever exists for exactly this kind of problem: at `p=15`,
bootstrap stability filtering rescued the overlap DGP's `N=750`
REASSESS (D-018) without collecting more data (D-020, `pi_min=.80`).
**This charter asks whether that same lever works at `p=30`**, on the
two REASSESS cases D-026/D-027 just characterized — a materially easier
target than Stage 3b's original rescue, since these misses are much
smaller (`.786` and `.762` vs. gate `.80`, compared to Stage 3b's
starting point of `.633` at `p=15` `N=750`).

This combines only already-validated pieces: `mintnet.bootstrap.
compute_edge_stability` (Stage 3), the overlap DGP at `p=30` (Stage
2h/2i), and D-023's screening threshold. No new mechanism.

**Predeclared expectation:** unlike Stage 3b, no bootstrap evidence
exists yet for this exact DGP/`p` combination to analyze before
writing this charter (Stage 3/3b/3c/3d were all `p=15`) — this
prediction is therefore an analogy, stated with appropriately less
confidence than Stage 3b's own evidence-grounded prediction was.
Reasoning from Stage 3b's finding (wrongly-retained overlap edges are
*more* stable than correctly-pruned ones, but less stable than true
edges, with a workable separation found at `pi_min=.80` for a `.231`-
point miss) and from these misses being roughly `6`-`16x` smaller
(`.014`-`.038` points): **this charter predicts filtering can rescue
both `N=1500` and `N=1600`**, plausibly at a `pi_min` at or below
Stage 3b's own `.80` (a smaller miss should need a less aggressive
filter, not a more aggressive one) — but this is a directional
expectation to check, not a number to hold the evidence to.

## Mechanism

Identical to Stage 3b: a post-hoc stability filter layered after the
existing, unmodified screen-then-prune pipeline. Point estimate →
`compute_edge_stability` (`B=500`, same fixed screening/DPI `alpha`
values) → filtered final graph = point-estimate final graph with any
edge removed if `pi_final < pi_min`.

## Data-generating process

Identical to Stage 2h/2i: `p=30`, chain/fork/shared-node-overlap DGP,
19 noise columns, strength `.5`, screening `alpha=.0001` (D-023), DPI
`alpha=f(N)` (D-012). **`N = [1500, 1600, 1750]`** — the two REASSESS
cases from D-026/D-027, plus `1750` (the first PROCEED) as a
no-regression check, mirroring Stage 3b's own inclusion of an
already-passing `N` alongside its target. `2000`/`2500` are not
retested here — `1750` already demonstrates the mechanism doesn't
regress an already-working case, and D-027 already established the
point-estimate trend continues upward from there.

**60 outer replicates per `N`, development (0-29) / validation
(30-59)** — Stage 3's standard bootstrap-charter replicate count.

Ground truth, identical to Stage 2h/2i: 10 true direct edges; 6
indirect edges (chain 1, fork 1, overlap 4); 419 null pairs.

## Selection and gate

Stage 3b's exact grid and criteria, unmodified except for the DGP and
`N` values: candidate `pi_min in {.80, .90, .95, .98}`. Per `N`, on
development, a `pi_min` is eligible if, after filtering:

1. Overlap indirect-edge TPR (post-filter) `>= .80`.
2. True-edge retention FPR (post-filter) `<= .10`.
3. Chain and fork indirect-edge TPR do not decrease relative to the
   point estimate (safe by construction).
4. Filtered final false-edge rate does not exceed the point estimate's
   own rate by more than `.01` (safe by construction).

Smallest eligible `pi_min` selected on development, confirmed on
validation with the same four criteria, PROCEED per `N` if all hold
with no recorded error.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate, per-pair evidence (point-estimate and
`pi_final` status for every edge), aggregate metrics, the per-N
decision table, report, and figures — identical evidence set to
Stage 3b, at `p=30`.

## Consequences

If PROCEED at `N=1500` and/or `N=1600`: stability filtering is
validated as a rescue mechanism for the overlap shape at `p=30`,
specifically at `alpha=.0001`, meaning a real dataset stuck at `N=1500`
-`1600` with this shape need not collect `1750`+ samples to reach a
valid result — it could instead apply the located `pi_min` at its
existing `N`. This does **not** authorize skipping D-027's floor
finding when it is feasible to collect more data (filtering trades
`B=500`x compute cost for sample size, a real tradeoff each user must
weigh, not resolved by this charter), nor generalize to other
weak-signal shapes or thresholds not yet tested this way.

If REASSESS at both `N=1500` and `N=1600` (contradicting this
charter's directional prediction): this would indicate the rescue lever
that worked for a large (`.231`-point) `p=15` miss does not
straightforwardly work for a small (`.014`-`.038`-point) `p=30` miss —
counterintuitive, and worth its own investigation into why a smaller
gap would be *harder* to close via stability filtering, not easier.

If `N=1750` unexpectedly REASSESSes under filtering: this would be a
genuine regression the point estimate did not have, and should block
trusting stability filtering as a rescue mechanism generally until
understood, regardless of what happens at `N=1500`/`1600`.
