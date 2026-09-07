# Stage 2j Charter: Composed Pipeline Floor Check at p=5 and p=10 (R5a)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

Every composed-pipeline charter so far (`p=15`: D-013/D-014/D-016/D-018;
`p=30`: D-023 through D-028) has tested `p` at or above `15`. That
choice was inherited from Stage 2's original design, not validated as a
lower bound. A practical question motivates checking below it: many
real behavioral/psychological datasets this method targets have
`p` in the `5`-`10` range, well below anything tested here.

The `p=30` work found that the general `N=750` floor holds for
strong-signal shapes (disjoint-triad, hub) regardless of `p`, but the
weak-signal shared-node-overlap shape needed *more* than `750` as `p`
grew from `15` to `30` (D-026/D-027 located its floor at `1750`). The
mechanism identified for that increase was **screening pressure, not
network topology**: more variables means more candidate null pairs,
which pushed the selected screening `alpha` down (D-023, `.001` to
`.0001`), which made detecting the overlap shape's weak (`~.135`)
cross-branch correlation harder at fixed `N`.

**That mechanism runs in reverse as `p` shrinks.** Fewer variables means
far fewer null pairs (`p=15`: 89 null pairs; `p=10`: at most 32; `p=5`:
0, see below), which should let screening use a *looser* alpha without
paying a false-discovery cost — which should make the overlap shape's
weak signal easier to detect at a fixed `N`, not harder. **This charter
predicts the general `N=750` floor holds for all tested shapes at both
`p=10` and `p=5`, including the overlap shape** — the opposite
direction, and opposite conclusion, from the `p=30` line's finding.

This combines only already-validated pieces (screening, D-013/D-023;
DPI, D-012; the three motif DGPs, D-014/D-016/D-018) at new `p`. No new
mechanism.

## Data-generating process

Reusing Stage 2d's exact motif definitions at reduced scale. **The full
three-motif design (chain + fork + overlap = 11 true variables) does not
fit at `p=10` or `p=5`** — this charter uses a reduced subset at each
`p`, chosen to preserve the overlap shape (the one shape whose floor is
in question) in every condition:

- **`p=10`**: overlap motif (5 variables, node 4 shared, `~.135`
  cross-branch correlation) + chain motif (3 variables, 1 indirect edge)
  + 2 noise columns. True candidate pairs: overlap's `C(5,2)=10` + chain's
  3 = **13**. Null pairs: `C(10,2) - 13` = **32**. True direct edges:
  overlap's 6 + chain's 2 = **8**. Indirect edges: overlap's 4 + chain's
  1 = **5**.
- **`p=5`**: overlap motif only (5 variables), **zero noise columns** —
  there is no room left at this `p` for any noise once the overlap
  motif's own 5 variables are placed. True candidate pairs = null
  pairs's complement = all `C(5,2)=10` pairs (6 true direct + 4
  indirect); **null pairs = 0**.

**Disclosed limitation, stated before results, not discovered after:**
with zero null pairs at `p=5`, the final false-edge rate and any
FDR-style metric are **undefined, not merely untested**, at that `p` —
there is nothing for screening to wrongly retain. `p=5` evidence can
only speak to indirect-edge pruning TPR and true-edge retention, not to
false-discovery behavior. This is a structural property of testing this
specific shape at this specific `p`, not a limitation of the pipeline.

Screening `alpha` and DPI `alpha=f(N)` are **not reused unmodified** —
per D-023's own finding that the null-pair count changes which alpha is
selected, this charter re-runs D-013/D-023's screening-selection
methodology at each new `p`'s null-pair count before evaluating the
composed pipeline, using the same predeclared grid
(`{.05, .01, .005, .001, .0005, .0001}`) and the same selection rule
(smallest alpha clearing recall `>= .99` and FDR `<= .05` on
development, confirmed on validation). At `p=5` this step is **skipped**
for the reason above (an alpha selected against zero null pairs is not
meaningful) — `p=5` composition instead reuses D-013's original
`alpha=.001`, flagged explicitly as an assumption, not a re-derivation.

`N = [750, 1500]` (Stage 2's own two standard points, for direct
comparability against every prior `p` in this line) at each of `p=10`
and `p=5`. Master seed `20260830`. **2,000 replicates per condition
(development 0-999, validation 1000-1999)**, matching Stage 2b/2d's own
composition-charter scale (this is composition-only; no bootstrap, so
the `B=500` cost that shaped Stage 3's smaller 60-replicate count does
not apply here).

## Selection and gate

Per `p`, per `N`: select screening alpha as described above (`p=10`
only; `p=5` uses `.001` fixed), then evaluate the composed pipeline on
validation replicates:

1. Overlap indirect-edge TPR `>= .80` (the metric in question).
2. Chain indirect-edge TPR `>= .80` (`p=10` only; no chain motif at `p=5`).
3. True-edge retention FPR `<= .10` (both `p`).
4. Final false-edge rate does not exceed screening-alone's own rate by
   more than `.01` (**`p=10` only** — undefined at `p=5`, see above).

PROCEED for a given `(p, N)` cell only if every criterion that is
*defined* for that cell holds, with no recorded error. Report the
selected alpha and clean-clique formation rate per `p=10` cell
descriptively, mirroring D-018's own reporting.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, per-`p` screening selection table (alpha vs. recall/FDR,
`p=10` only), raw per-replicate per-pair evidence, aggregate metrics,
the per-`(p, N)` decision table, report, and figures — the same evidence
set as every prior composition charter in this line.

## Consequences

If PROCEED at `N=750` for the overlap shape at both `p=10` and `p=5`
(this charter's prediction): confirms the `p=30` line's finding
generalizes in the direction it implied — screening pressure, not
absolute variable count, drives the overlap shape's floor, and lower-`p`
behavioral datasets do **not** need more than the general `N=750` floor
for this shape. This would **not** imply floors keep dropping below
`750` — the general DPI floor (D-010/D-011) was never itself tested
below `700`, and this charter does not test it there either.

If REASSESS at `N=750` for the overlap shape at either lower `p`
(contradicting this charter's prediction): this would mean the
screening-pressure explanation for D-026/D-027 is incomplete, and some
other factor (plausibly: fewer total variables means each individual
correlation estimate is noisier in a different way not captured by the
Fisher-z model used so far) matters too — worth its own follow-up before
trusting any `p`-dependent floor claim in either direction.

If the `p=10` screening-selection step selects a **tighter** alpha than
`p=15`'s `.001` (contrary to the "fewer null pairs -> looser alpha"
reasoning): this alone would be a surprising finding worth flagging
before even reaching the composition gate, since it would undercut the
mechanism this whole charter is built on.

This charter does not test non-Gaussian or ordinal data, which
behavioral/psychological datasets often have — that remains a separate,
unaddressed gap regardless of this charter's outcome.
