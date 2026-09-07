# Stage 3 Charter: Bootstrap Reproducibility of the Composed Pipeline (R4)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

Stage 1 validated conditional-independence pruning in isolation
(D-008-D-012, D-015, D-017). Stage 2 validated candidate-edge screening
in isolation (D-013). Stage 2b-2d validated the composed
screen-then-prune pipeline on disjoint triads (D-014), mixed
triad/hub components (D-016), and shared-node overlap (D-018) — the
last of these an explicit split outcome (REASSESS at `N=750`, PROCEED at
`N=1500`) driven by a known, quantified screening-power limitation, not
a surprise. Every one of those charters evaluates a single point
estimate: one dataset, one run of the pipeline, one final graph. Per
`outline/information_network_technical_build_plan_v2_2026-08-29.md`
Section 17, this charter tests the next, distinct mechanism: **does
bootstrap resampling of the composed pipeline produce an edge-stability
statistic that meaningfully separates true edges from false ones** —
not whether the point-estimate pipeline itself is accurate (already
tested), and not whether stability *filtering* should become the
default output (a downstream product decision, out of scope here).

**Why now, not earlier:** the second peer review's zero-variance/
degenerate-input hardening
(`docs/peer_review_followup_2026-08-30.md`, `fix: reject
zero-variance/degenerate inputs in DPI and screening`) is a direct
prerequisite for this charter, not an unrelated cleanup. Bootstrap
resampling draws rows with replacement, which occasionally produces a
resample where a low-variance column's already-small spread collapses
further — exactly the degenerate-input scenario those guards convert
from a silent `NaN` (previously misread by `nan <= alpha == False` as
"not significant") into a raised, recorded error. Without that fix,
Stage 3 could not distinguish "this resample's estimator was
undefined" from "this resample's edge is genuinely absent," which
would silently corrupt every stability estimate downstream.

Per the outline's Section 2.1 ("validate mechanisms independently
before composing them") and this project's falsification-first
practice of testing the simplest available case before a harder one,
this charter tests bootstrap stability **on top of the simplest fully
validated composed pipeline** — Stage 2b's disjoint-triad network,
PROCEED at both `N` — plus one explicit, targeted test of the
outline's own predicted failure mode (Section 17.5) using a DGP
already *known* to make a systematic pruning mistake (Stage 2d's
`N=750` shared-overlap case, D-018). It does not test bootstrap on the
hub or overlap networks' own gate criteria, does not test alternative
resampling schemes (block bootstrap, parametric bootstrap), and does
not authorize stability filtering as a production default.

## Mechanism

For a single dataset `X` (`N` rows, `p=15` columns, sampled once from a
validated DGP):

1. **Point estimate**: run the frozen composed pipeline (screening at
   `alpha=.001`, D-013; `mintnet.pipeline.compose.compose_screen_then_prune`
   at `alpha=f(N)`, D-012) on `X` itself, producing the candidate
   (pre-DPI) matrix and the final (post-DPI) matrix.
2. **Bootstrap resampling**: draw `B=500` resamples of `X`'s rows, with
   replacement, each of size `N` (standard nonparametric row bootstrap;
   matches the outline's own example default,
   `stability_bootstraps=500`, Section 25). Run the identical pipeline
   (same fixed `alpha` values — the resampling varies the data, not the
   thresholds) on each resample `X^(b)`, producing `G^(b)`.
3. **Edge stability**, stored separately per Section 17.3:
   - Pre-DPI candidate frequency: `pi_ij_candidate = (1/B) * sum_b
     1[(i,j) flagged as a candidate edge in resample b]`.
   - Post-DPI final frequency: `pi_ij_final = (1/B) * sum_b 1[(i,j)
     present in G^(b)]`.

This is a new two-level Monte Carlo structure (outer dataset
replicates, inner bootstrap resamples), not a reuse of prior charters'
single-level replicate loop — it belongs in a new
`mintnet.experiments.stage3` module plus a `mintnet.bootstrap` module
for the resampling/stability-computation logic itself, matching the
outline's Section 3 proposed repository structure (`bootstrap.py`).

## Data-generating processes

**Primary (gated) DGP** — identical to `docs/stage2b_charter.md`:
`p=15` (chain `X1->X2->X3`, fork `X4<-X5->X6`, triangle `X7,X8,X9` at
the `moderate` fixture, strength `.5`, six independent noise columns
`X10`-`X15`), `N = [750, 1500]`, master seed `20260829`. Ground truth
unchanged from Stage 2b: 7 true direct edges, 2 indirect edges DPI
should prune, 96 null pairs.

Outer dataset replicates: **30 development (0-29), 30 validation
(30-59)** per `N` — far fewer than prior charters' 2000, a deliberate
and justified reduction, not a shortcut: in every prior charter, the
replicate loop's *purpose* was to estimate a single per-`N` rate (e.g.
recall, FDR) precisely. Here, each single outer replicate already
produces a full distribution of `pi_ij` across all 105 pairs in three
ground-truth categories (true direct, indirect, null); the outer loop
only needs enough replicates to confirm that distribution's shape is
not a one-off artifact of one dataset's sampling noise, not to pin
down a rate to the third decimal. 30+30 replicates x `B=500`
bootstraps x 2 `N` = 60,000 pipeline evaluations, keeping runtime in
the same order as prior charters' 2000-4000-row runs.

**Secondary (diagnostic only, not gated) DGP** — identical to
`docs/stage2d_charter.md` at `N=750` only: `p=15` with the shared-node
overlap motif (columns 6-10, node 8 shared), the specific condition
D-018 found REASSESS on (overlap indirect-edge pruning TPR `~.59`,
below the `.80` gate, because screening only detects the weak
cross-branch correlation `~66%` of the time at this `N`). **30
replicates, no development/validation split** — this DGP exists
specifically to exercise Section 17.5's key failure test ("confirm
that high bootstrap stability can occur for wrong edges or wrong
pruning decisions") using a failure mode this project has *already
quantified and predicted*, not a new one manufactured for this
charter. `B=500` bootstraps per replicate, same as the primary DGP.

## Selection and gate

**Applies only to the primary (triad-only) DGP.** Per `N`,
independently (no pooling across `N`), using development replicates:

For each candidate stability threshold `pi_min in {.70, .80, .90}`
(Section 17.4 — "do not pick one from convention alone"), classify an
edge as *stability-retained* if `pi_ij_final >= pi_min`. Compute, pooled
across the 30 development replicates' edges:

1. **Stability recall**: fraction of the 7 true direct edges that are
   stability-retained `>= .90`. (A high bar, not Stage 2's `.80`:
   Stage 2b already validated near-perfect true-edge retention at the
   point estimate — D-014 — so a stability rule that fails to recover
   edges the pipeline itself already gets right would indicate the
   *stability statistic*, not the pipeline, is the problem.)
2. **Stability FDR**: fraction of stability-retained edges, across all
   105 pairs, that are actually null `<= .10` (mirrors Stage 2's
   frozen pooled-FDR definition, D-013's corrected implementation —
   sum of counts across replicates, not a mean of per-replicate
   ratios).
3. **No regression against the point estimate**: the stability-filtered
   final-edge false rate must not exceed the point-estimate pipeline's
   own final false-edge rate at that `N` (D-014) by more than `.01`
   absolute — stability filtering must not make the graph worse than
   simply trusting the single-run output.

Among `pi_min` values meeting all three criteria on development,
select the **smallest** (least conservative, retains the most true
edges) — same simplicity tiebreak as Stage 2's rule selection. The
selected `pi_min` must then meet criteria 1-3 again on validation
replicates (30-59), independently, with no recorded error, to PROCEED
for that `N`. If no `pi_min` is eligible on development, REASSESS for
that `N`: "bootstrap stability does not meaningfully separate true
from false edges at this `N`," a valid and informative negative
result, not a bug to chase.

**The secondary (overlap, `N=750`) DGP has no PROCEED/REASSESS gate.**
Its 30 replicates' `pi_ij_final` values for the known-mispruned
indirect overlap edges are reported descriptively, alongside the same
statistic for the network's other (correctly-handled) edges, to
directly answer Section 17.5's question: is elevated stability observed
for edges the pipeline is known to get wrong? A "yes" here is the
outline's own predicted, sought-after finding (proof the failure mode
is real and bootstrap does not automatically protect against it), not
a failure of this charter.

## Non-goals (explicit, per Section 17.6's third bullet)

`pi_ij` is a resampling-reproducibility statistic, not a p-value, not
a frequentist confidence level, and not evidence of population-level
statistical significance. Any report generated from this charter's
evidence must describe `pi_min` thresholds as calibrated operating
points (analogous to Stage 2's `alpha`), never as confidence levels,
and must not claim an edge is "significant" because it is stable, or
vice versa. This mirrors D-013/D-016/D-018's post-review correction
distinguishing "successful pre-specified prediction" from "independent
confirmation" — precision about what a statistic does and does not
license is a standing project norm, not a one-off fix.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-outer-replicate evidence (per-edge `pi_candidate` and
`pi_final` for all 105 pairs, tagged by ground-truth category, for
both DGPs), aggregate metrics (stability recall/FDR per `pi_min`
candidate, selected `pi_min`, no-regression check result), the per-N
decision table for the primary DGP, the descriptive stability
comparison for the secondary DGP, report, and figures (stability
distribution by edge category — true direct, indirect, null — as a
box or violin plot, separately for candidate- and final-level
stability, and separately for each DGP).

## Consequences

If PROCEED at both `N` (primary DGP): this validates that, for the
disjoint-triad composed pipeline at `p=15`, `N in [750, 1500]`, final-
graph bootstrap stability (at `B=500`, row bootstrap) meaningfully
separates true edges from false ones under a calibrated threshold, and
that filtering by it does not regress final graph quality relative to
the point estimate. It does **not** validate this for hub or overlap-
containing networks, for other resampling schemes, for other `B`
values, or authorize stability filtering as a production default
output rather than a diagnostic — those remain open questions for
later charters.

If REASSESS at a given `N`: document which of the three criteria
failed and by how much, same as every prior charter. A stability-FDR
or no-regression failure would suggest bootstrap adds noise rather
than signal at that `N`; a stability-recall failure would suggest the
statistic is systematically too conservative even for edges the point
estimate already retains correctly — worth distinguishing before
concluding bootstrap "doesn't work" outright.

The secondary DGP's result, regardless of what it shows, does not
change the primary DGP's PROCEED/REASSESS status — it is reported
alongside as a direct empirical answer to Section 17.5's key failure
test, using a failure mode this project already predicted and
quantified (D-018) rather than one invented for this charter.
