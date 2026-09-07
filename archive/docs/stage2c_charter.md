# Stage 2c Charter: Composed Pipeline with Mixed Triad/Hub Components (R3d)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

Stage 2b validated the composed screen-then-prune pipeline on a network
where every true-motif candidate component was a 3-node triad (D-014).
Stage 1k validated multi-variable conditioning, in isolation, on a
4-node hub shape (D-015). The pipeline code has since been generalized
(`mintnet.pipeline.compose`) to apply DPI within either validated shape,
verified to reproduce D-014's exact original results before being
trusted (regression-checked, not merely asserted). What has **not** been
tested is a single network containing *both* shapes at once, screened and
pruned end to end in one pipeline run — this charter closes that gap.

This is the direct combination of Stage 2b's and Stage 1k's DGPs, not a
new mechanism: no new code decisions are being tested here, only whether
wiring the two validated shapes into one pipeline behaves as each did
independently when they coexist in the same network and the same
screening pass.

## Data-generating process

`p = 15`: chain (`X1->X2->X3`, columns 0-2), measured fork (`X4<-X5->X6`,
columns 3-5), a hub with 3 children (column 6 hub, columns 7-9 children),
and 5 independent noise columns (10-14) — replacing Stage 2b's triangle
motif with the hub motif, keeping `p` fixed at 15 so this charter isolates
"mixed component shapes" as the only new variable, rather than also
changing network size. Strength `.5` throughout (matching every prior
charter). `N = [750, 1500]`, master seed `20260829`, 2000 replicates
(development 0-999, validation 1000-1999).

**Ground truth**: true candidate pairs (nonzero correlation) = chain's 3
+ fork's 3 + hub's `C(4,2)=6` = **12**; null pairs = `C(15,2) - 12` =
**93**. True direct edges (should survive the full pipeline) = chain's 2
+ fork's 2 + hub's 3 hub-child edges = **7**. Indirect/prunable edges =
chain's 1 + fork's 1 + hub's `C(3,2)=3` child-child pairs = **5**.

## Mechanism

Unchanged: screen at `alpha = .001` (D-013's winning rule), then compose
via `mintnet.pipeline.compose.compose_screen_then_prune` at `alpha =
f(N)` (D-012's formula) — the same two frozen values Stage 2b used,
applied here to the generalized pipeline code.

## Selection and gate

No selection step. Per `N`, on validation replicates (1000-1999):

1. Indirect-edge pruning TPR (5 prunable pairs) `>= .80`.
2. True-edge retention (7 true direct edges) — FPR `<= .10`.
3. Final false-edge rate does not exceed screening-alone's own rate (same
   `.01` absolute tolerance as D-014) — the same no-regression check.
4. Descriptive: rate at which each motif's candidate component actually
   achieves its validated shape (a clean triad for chain/fork, a clean
   4-clique for the hub) — expected close to D-014's `~.96` and D-015's
   implicit near-1.0 shape rate, not a new threshold.

**PROCEED** for a given `N` only if 1-3 hold with no recorded error.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence, aggregate metrics, the per-N
decision table, report, and figures.

## Consequences

If PROCEED at both `N`: the generalized composed pipeline is validated
for networks containing any mixture of disjoint 3-node and 4-node
hub-clique candidate components, at `p=15`, `N in [750, 1500]`. Larger
networks, additional shape types, or components sharing variables across
motifs remain untested and need their own charter.

If REASSESS: since neither shape alone failed in isolation (D-014,
D-015), a failure here would specifically implicate an *interaction*
between the two shapes coexisting in one screening pass and one
connected-components decomposition — worth its own focused
investigation rather than assuming either individual mechanism is at
fault.
