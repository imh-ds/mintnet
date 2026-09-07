# Stage 2f Charter: Composed Pipeline at p=30 (R3h)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-023 validated screening alone at `p=30` and explicitly deferred the
one gap that mattered most for a real-sized dataset: "does not
authorize composing screening with DPI pruning at `p=30` ... a natural
next charter." This is the direct `p=30` analog of Stage 2b (which
composed Stage 2's `p=15` screening with Stage 1's DPI on the same
disjoint chain/fork/triangle DGP) — same mechanism, same DGP shape,
only `p` and the screening threshold change, both already settled by
D-023.

Per the outline's Section 2.1, this is not a new mechanism: screening
and DPI have each been separately validated at `p=30` (screening,
D-023) and at every `N in [750, 1500]` (DPI, D-008-D-012); what has not
been tested is whether wiring them into one pipeline, at `p=30`,
behaves the way each did independently — the same question Stage 2b
asked at `p=15`, not a new one.

**Predeclared expectation, computed from D-023's own findings before
running anything:** D-023 found screening's *per-edge* false-positive
rate at its selected `p=30` rule (uncorrected `alpha=.0001`) is
`.00012` at both `N` — essentially exactly `alpha` itself, confirming
the test is well-calibrated regardless of `p` (unlike the *pooled FDR*,
which is `p`-dependent via the true:null ratio and was the whole reason
D-023 needed a stricter `alpha`). Stage 2b's own finding (D-014) was
that DPI cannot rescue an isolated false positive — a null pair
screened as a candidate edge, with no candidate neighbor, passes
through the pipeline unmodified — so the final false-edge rate should
closely track screening's own per-edge rate, not improve on it. **This
charter therefore predicts**: final false-edge rate `~.0001`, closely
tracking screening-alone's `.00012`; true-edge retention FPR `~0`
(matching D-014's `.000`); indirect-edge pruning TPR similar to D-014's
`~.80`-`.82` (unaffected by `p`, since it depends only on the chain/
fork motifs' own signal strength and DPI's `alpha=f(N)`, neither of
which changed); and PROCEED at both `N`, mirroring D-014's clean first-
attempt result.

## Pipeline (frozen mechanism)

Unchanged from Stage 2b, using D-023's `p=30`-specific screening
threshold in place of D-013's `p=15` one:

1. **Screen** every `C(30, 2) = 435` pairs using D-023's winning `p=30`
   rule: uncorrected Fisher-z on raw correlation, `alpha = .0001` (not
   D-013's `.001` — using the `p=15` threshold here would be reusing an
   unvalidated rule at the wrong network size, exactly the mistake this
   charter exists to avoid).
2. **Group** candidate edges into connected components.
3. **For each 3-node component with exactly 3 candidate edges**: apply
   DPI's validated conditional-independence test, conditioning on the
   third node, `alpha = f(N)` (D-012's formula, unchanged — it depends
   on `N`, not `p`).
4. **Every other candidate component**: retained unmodified (Stage 2b's
   explicit scope boundary, unchanged).
5. **Final output**: DPI-retained triad edges, plus unmodified other-
   shaped candidate edges.

No new code: `mintnet.pipeline.compose.compose_screen_then_prune` is
already `p`-agnostic (it operates on whatever candidate graph screening
produces, regardless of network size).

## Data-generating process

Identical to Stage 2e: `p = 30` (chain `X1->X2->X3` columns 0-2,
measured fork `X4<-X5->X6` columns 3-5, triangle `X7,X8,X9` `moderate`
fixture columns 6-8, 21 independent noise columns 9-29), strength `.5`,
`N = [750, 1500]`, master seed `20260829`, 2000 replicates (development
0-999, validation 1000-1999) — same DGP, `N` range, seed, and replicate
count as every prior screening/composition charter, changing only `p`
(via Stage 2e's noise-column count) and the screening `alpha` (via
D-023's selected rule).

**Ground truth**, identical to Stage 2b's own (the true-motif structure
is unchanged; only the noise-column count differs): **7 true direct
edges** (chain `(0,1)`,`(1,2)`; fork `(3,4)`,`(4,5)`; triangle
`(6,7)`,`(6,8)`,`(7,8)`), **2 indirect edges** DPI should prune (chain
`(0,2)`, fork `(3,5)`), **426 null pairs** (`C(30,2) - 9`).

## Selection and gate

No selection step — both `alpha` values are already frozen (D-012 for
DPI, D-023 for `p=30` screening); this charter only evaluates the
resulting pipeline. Per `N`, on validation replicates (1000-1999):

1. **Indirect-edge pruning TPR** (2 prunable pairs) `>= .80` (Stage 2b's
   bar, unchanged).
2. **True-edge retention** (7 true direct edges) — FPR `<= .10`.
3. **Final false-edge rate** (fraction of the 426 null pairs present in
   the final output) does not exceed screening-alone's own per-edge FPR
   at `p=30` (D-023: `.00012` at both `N`) by more than `.01` absolute
   — the same no-regression check Stage 2b used, now against the
   correct `p=30` baseline rather than D-013's `p=15` figure.

**PROCEED** for a given `N` only if all three hold with no recorded
error. Descriptive: the fraction of candidate components that are
actual triads vs. other shapes, to check whether the much stricter
`alpha=.0001` changes this rate from D-014's `~.96`.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (final retained/pruned status for
the 9 true-motif pairs, which of the 426 null pairs survived to the
final output), aggregate metrics, the per-N decision table, report, and
figures — identical evidence set to Stage 2b, at `p=30`.

## Consequences

If PROCEED at both `N`: the composed pipeline is validated at `p=30`
for disjoint, non-overlapping 3-node motifs, using D-023's `p=30`
screening threshold — closing the gap D-023 itself flagged. It does
**not** validate hub, overlap, or other candidate shapes at `p=30` (a
further follow-up, mirroring how Stage 2c/2d each needed their own
charter after Stage 2b at `p=15`), bootstrap stability at `p=30` (Stage
3's own line of work, untested at this `p`), or `p` values beyond `30`.

If REASSESS: given every constituent mechanism is independently
validated at this `p`/`N` (screening: D-023; DPI: D-008-D-012), a
failure here would specifically implicate an *interaction* between the
two at `p=30` — worth its own focused investigation, the same posture
Stage 2b took toward its own (never-triggered) REASSESS branch.
