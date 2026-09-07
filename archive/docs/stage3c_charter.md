# Stage 3c Charter: Bootstrap Stability on the Composed Hub/Triad Network (R4c)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

Stage 3 validated that bootstrap final-edge stability meaningfully
separates true edges from false ones — but only on Stage 2b's
disjoint-triad network (D-014, D-019). Stage 3b then validated a
stability-*filtering* rescue, but only for the shared-node-overlap DGP
(D-018, D-020), and only as a targeted fix for that DGP's specific
known failure — it did not re-run Stage 3's general recall/FDR
threshold-selection gate on a different network shape. Both of D-019's
and D-020's own consequences sections flag the same open gap: bootstrap
stability has never been gated on a network containing a **hub**
candidate component (D-016's chain+fork+hub composition), only on the
disjoint-triad network and, separately and narrowly, on the overlap
network. This charter closes that gap — it does not introduce any new
mechanism; it is Stage 3's exact primary-DGP procedure, re-run on
Stage 2c's DGP instead of Stage 2b's.

Per this project's per-shape validation practice (D-015's hub result
did not transfer automatically to D-016's composed pipeline without its
own charter; D-017's overlap result likewise needed D-018's own
composed-pipeline charter), a mechanism validated on one candidate
shape is not assumed to transfer to a structurally different shape
without being checked. The hub shape has a stronger, more reliably
detected signal than the overlap shape (D-016's point-estimate
indirect-edge TPR, `.820`-`.853`, already clears Stage 2's gate at both
`N` with a comfortable margin, unlike the overlap DGP's known `N=750`
failure) — so, unlike Stage 3b, **this charter is not chasing a known
failure**. The predeclared expectation is a clean PROCEED at both `N`,
similar to Stage 3's primary-DGP result, precisely because there is no
known weak-signal complication here. Chartering it anyway, rather than
assuming Stage 3's disjoint-triad result transfers, is the point: an
untested transfer is exactly the kind of assumption this project's
methodology (Section 2.1: validate mechanisms independently before
generalizing them) does not allow itself to make silently.

## Mechanism

Unchanged from Stage 3: for each dataset, run the frozen composed
pipeline (screening `alpha=.001`, D-013; DPI `alpha=f(N)`, D-012) to
get the point estimate, then draw `B=500` row-bootstrap resamples and
run the identical pipeline on each to compute per-pair candidate and
final-edge stability (`pi_candidate`, `pi_final`), exactly as
`mintnet.bootstrap.compute_edge_stability` already does. No new code
beyond wiring this existing mechanism to a different DGP and its own
gate evaluation.

## Data-generating process

Identical to `docs/stage2c_charter.md`: `p=15`, chain (`X1->X2->X3`,
columns 0-2), measured fork (`X4<-X5->X6`, columns 3-5), a hub with 3
children (column 6 hub, columns 7-9 children), 5 noise columns
(10-14), strength `.5`. `N = [750, 1500]`, master seed `20260829`,
screening `alpha=.001`, DPI `alpha=f(N)`, `B=500` bootstraps per
dataset (unchanged from Stage 3/3b).

**Ground truth**, identical to Stage 2c: 7 true direct edges (chain's
2 + fork's 2 + hub's 3 hub-child edges), 5 indirect/prunable edges
(chain's 1 + fork's 1 + hub's `C(3,2)=3` child-child pairs), 93 null
pairs.

**60 outer replicates per `N`, development (0-29) / validation
(30-59)** — the same count and rationale as Stage 3's primary DGP: each
replicate already yields a full per-edge stability distribution across
all 105 pairs, so the outer loop confirms the distribution's shape, not
a precise rate.

## Selection and gate

Identical procedure and thresholds to Stage 3's primary-DGP gate — no
new criteria invented for this DGP, since there is no evidence yet that
this shape needs different ones (unlike the overlap DGP, which needed a
materially different, higher `pi_min` grid, per Stage 3b's corrected
analysis):

Candidate thresholds `pi_min in {.70, .80, .90}` (Stage 3's original
grid, reused because this DGP's point-estimate behavior already
resembles Stage 3's primary DGP, not the overlap DGP). Per `N`,
independently, using development replicates, a `pi_min` is *eligible*
if, on the filtered final graph:

1. **Stability recall** (fraction of the 7 true direct edges
   stability-retained) `>= .90` (Stage 3's bar, not Stage 2's `.80` —
   the point estimate already retains true edges almost perfectly,
   D-016's FPR `.000` at both `N`, so a stability rule that fails to
   recover them would indict the statistic, not the pipeline).
2. **Stability FDR** (pooled fraction of stability-retained edges,
   across all 105 pairs, that are actually null) `<= .10` (Stage 2's
   corrected pooled-count definition, D-013).
3. **No regression**: the stability-filtered final false-edge rate must
   not exceed the point estimate's own final false-edge rate (D-016:
   `.00101` at `N=750`, `.00120` at `N=1500`) by more than `.01`
   absolute.

Among eligible `pi_min` values, select the smallest (least
conservative). The selected `pi_min` must meet all three criteria again
on validation replicates (30-59), with no recorded error, to PROCEED
for that `N`. If no `pi_min` is eligible on development, REASSESS: "the
disjoint-triad DGP's stability behavior does not transfer to the hub
shape" — an informative negative result given the predeclared
expectation above, not a bug to chase.

## Non-goals

Same as Stage 3's: `pi_final`/`pi_candidate` are resampling-
reproducibility statistics, never p-values or confidence levels, in
any report built on this evidence. This charter does not test
stability *filtering* on the hub DGP (there is no known failure here to
rescue, unlike Stage 3b's overlap case) — only whether the general
separation/selection gate itself transfers.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate, per-pair evidence (`pi_candidate`,
`pi_final`, point-estimate candidate/final status, ground-truth
category), aggregate metrics, the per-N decision table, report, and
figures (stability distribution by edge category, per `N`, matching
Stage 3's figure format).

## Consequences

If PROCEED at both `N`: bootstrap edge stability's general
recall/FDR/no-regression gate is validated on a second, structurally
different composed-pipeline DGP (hub, not just disjoint triads), at
`p=15`, `N in [750, 1500]`, `B=500`. This still does **not** validate
the gate on the overlap DGP itself (Stage 3b addressed that DGP through
a narrower, filtering-specific lens, not this general gate) or on any
DGP outside `p=15`/`N in [750, 1500]`.

If REASSESS at either `N`: since the point-estimate pipeline already
works well on this DGP (D-016), a failure here would specifically
implicate bootstrap resampling's interaction with the hub shape's
4-node conditioning step — worth its own focused investigation, not an
assumption that Stage 3's primary-DGP result was somehow wrong.
