# Stage 3d Charter: Bootstrap Stability's General Gate on the Overlap Network (R4d)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-021's consequences flagged the one remaining gap in this line of
work: Stage 3's *general* stability-selection gate (recall over true
direct edges, pooled FDR over null pairs, no-regression on the final
false-edge rate — the exact procedure confirmed on the disjoint-triad
DGP in D-019 and the hub DGP in D-021) has never been run, unmodified,
on the shared-node-overlap DGP. Stage 3b touched this DGP, but only
through a narrower, filtering-specific lens (a different, higher
`pi_min` grid, and a gate built around the overlap-indirect-edge
category specifically) — it never asked the plain question Stage 3 and
3c asked of the other two DGPs. This charter asks it.

**A predeclared expectation stated before running anything, because it
follows from how the gate is built, not from a new simulation check:**
Stage 3's three criteria (stability recall over `true_direct`, pooled
FDR over `null`, no-regression on the `null`-only final false-edge
rate) **never reference the indirect-edge category at all.** D-018's
known `N=750` failure lives entirely inside the `indirect_overlap`
category — the four cross-branch pairs screening under-detects. A gate
that never inspects that category cannot detect that failure, by
construction, regardless of `N`. Combined with D-019's already-frozen
descriptive evidence on this exact DGP (`results/generated/
stage3_bootstrap/raw_metrics.csv`, `secondary_overlap_diagnostic` rows,
`N=750`): mean `pi_final` for `true_direct` is `.99999`, for `null` is
`.021` — a separation at least as clean as the disjoint-triad and hub
DGPs' — **this charter is expected to PROCEED at both `N`, including
`N=750`, despite D-018's REASSESS there.** That is not a contradiction:
D-018 and this charter test different things (indirect-edge pruning
accuracy vs. true/null stability separation), and stating the
expectation this plainly in advance is meant to prevent a future reader
from misreading two different PROCEED/REASSESS statuses about the same
`N` as inconsistent.

## Mechanism

Unchanged from Stage 3/3c: `mintnet.bootstrap.compute_edge_stability`,
`B=500` row bootstraps per dataset, applied to the frozen composed
pipeline (screening `alpha=.001`, DPI `alpha=f(N)`). No new code.

## Data-generating process

Identical to Stage 2d / Stage 3's secondary DGP / Stage 3b: `p=15`,
chain (0-2), measured fork (3-5), shared-node overlap (6-10, node 8
shared), 4 noise columns (11-14), strength `.5`. `N = [750, 1500]`,
master seed `20260829`, screening `alpha=.001`, DPI `alpha=f(N)`,
`B=500`.

**Ground truth**, identical to Stage 2d/3b: 10 true direct edges; 6
indirect edges (chain 1, fork 1, overlap 4 — tracked descriptively in
this charter's evidence, per the Non-goals section below, but **not**
part of the gate); 89 null pairs.

**60 outer replicates per `N`, development (0-29) / validation
(30-59)** — the same split Stage 3's primary DGP and Stage 3c used,
now applied here for the first time (Stage 3's own pass over this DGP
used only 30 undivided, descriptive replicates; Stage 3b used 60 but
gated on a different criterion set).

## Selection and gate

Stage 3's exact grid and criteria, unmodified: `pi_min in {.70, .80,
.90}`. Per `N`, on development, a `pi_min` is eligible if:

1. Stability recall (fraction of the 10 true direct edges
   stability-retained) `>= .90`.
2. Pooled stability FDR (stability-retained edges, across all 105
   pairs, that are actually null) `<= .10`.
3. Stability-filtered final false-edge rate (null pairs only) within
   `.01` of the point-estimate baseline.

Smallest eligible `pi_min` selected, confirmed on validation with the
same three criteria, PROCEED per `N` if all hold with no recorded
error — identical procedure to Stage 3/3c.

## Non-goals

**This charter does not test, and its gate cannot detect, D-018's
indirect-edge pruning failure.** Indirect-edge `pi_final` values (all
three motifs) must still be reported descriptively in this charter's
evidence and report, explicitly to document — not to gate on — how the
`indirect_overlap` category behaves under the same run that PROCEEDs on
the general gate. Any report built on this evidence must state plainly,
next to a PROCEED at `N=750`, that this says nothing about whether the
overlap DGP's indirect-edge accuracy problem is resolved at that `N` —
it is not; that is Stage 3b's separate, already-answered question.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate, per-pair evidence (`pi_candidate`,
`pi_final`, point-estimate status, ground-truth category — same
five-category schema as Stage 3's secondary DGP and Stage 3b),
aggregate metrics, the per-N decision table, a descriptive indirect-
edge-category stability summary (mean/median `pi_final` per motif, at
the selected `pi_min`, alongside what fraction of each indirect
category would be stability-retained), report, and figures.

## Consequences

If PROCEED at both `N` (expected, including `N=750`): confirms Stage
3's general recall/FDR/no-regression gate transfers to a third,
structurally different composed-pipeline DGP, closing the gap D-021
flagged. It explicitly does **not** mean the overlap DGP's `N=750`
indirect-edge problem is resolved, superseded, or reassessed by this
result — that remains D-018's REASSESS, addressed only by Stage 3b's
separate filtering mechanism. Any summary of this project's status must
not cite this charter's PROCEED as evidence against D-018.

If REASSESS at either `N` (unexpected, given D-019's already-frozen
partial evidence on this exact DGP): would mean the true/null
separation behaves differently on this DGP than the pre-charter
analysis suggested — worth investigating specifically why, since
nothing in the mechanism gives an a priori reason for it, unlike the
indirect-edge category's known weak-signal explanation.
