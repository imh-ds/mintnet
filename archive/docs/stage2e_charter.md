# Stage 2e Charter: Candidate-Edge Screening at p=30 (R3g)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-013 validated per-pair correlation screening at `p=15`, and its own
consequences explicitly deferred `p=30`: "does not authorize `p=30` or
other network sizes, which remain untested." This charter closes that
gap — for screening alone, in isolation, exactly as Stage 2 tested it
(per the outline's Section 2.1, composing screening with DPI at a new
network size is its own question, deferred to a future Stage 2b-analog
charter, not this one).

This is not a trivial re-run at a bigger number. Stage 2's own charter
text flagged the mechanism's real vulnerability: with a fixed, small
number of true relationships and a multiple-testing burden that grows
quadratically in `p`, the achievable uncorrected-alpha range shrinks as
`p` grows. At `p=15`, `9` true pairs sat against `96` null pairs
(`~10.7:1`); doubling `p` to `30`, while keeping the same 3 motifs (9
true variables) and adding noise columns to reach `30`, changes that
ratio to `9:426` (`~47:1`) — a `~4.4x` worse imbalance, entirely from
noise columns Stage 2 never had to contend with in this proportion.

**Predeclared expectation, computed from D-013's own findings before
running anything, not assumed:** D-013 found recall was never the
binding constraint — essentially `1.0` at every tested `alpha`. Holding
that fixed and using the same back-of-envelope approximation Stage 2's
own charter used successfully (`FDR ~= null_pairs * alpha / (true_pairs
* recall + null_pairs * alpha)`, which predicted D-013's actual `.0121`/
`.0106` from `.096`/`.144` expected false positives almost exactly):

| `alpha` | expected FP (`426 * alpha`) | predicted FDR |
|---|---|---|
| `.0001` | `.043` | `.005` |
| `.0005` | `.213` | `.023` |
| `.001` | `.426` | `.045` |
| `.005` | `2.13` | `.191` |
| `.01` | `4.26` | `.321` |
| `.05` | `21.3` | `.703` |
| `.10` | `42.6` | `.826` |

**This predicts a much narrower passing range than Stage 2's own**:
only `alpha <= .001` clears the `.10` gate (vs. `alpha <= .01` at
`p=15`, which itself sat right at the boundary per Stage 2's own text).
`alpha=.005` and above are predicted to fail outright, not sit near a
boundary. BH (`q in {.05, .10}`), which self-adjusts for the number of
tests, is predicted to still pass comfortably at both levels, by
design. **The candidate grid is deliberately extended below Stage 2's
own lower bound (`.0001`, `.0005`, in addition to Stage 2's original
`.001`-`.10`)** for the same reason Stage 2's own charter gave for
setting its original lower bound: the grid must reach low enough to
give the uncorrected approach a genuine, fair chance at this much
larger null-pair count, or "is BH necessary here" stops being an
honestly open question — at `p=30`, unlike `p=15`, that question now
has real stakes either way.

## Mechanism

Unchanged from Stage 2: per-pair Fisher-z test on raw (unconditional)
Pearson correlation (`mintnet.screening.compute_pairwise_screening_evidence`),
thresholded either by a fixed uncorrected `alpha` per pair
(`screen_uncorrected`) or by Benjamini-Hochberg FDR control across all
`C(p,2)` pairs (`benjamini_hochberg_threshold`). No new code — this
charter tests whether the same mechanism, unmodified, still works at a
larger `p`, not a new estimator.

## Data-generating process

`p = 30`: the same three motifs Stage 2 used — chain (`X1->X2->X3`,
columns 0-2), measured fork (`X4<-X5->X6`, columns 3-5), triangle
(`X7,X8,X9`, `moderate` fixture, columns 6-8) — plus **21** independent
standard-Gaussian noise columns (9-29), up from Stage 2's 6. Strength
`.5` throughout, matching every prior charter. `N = [750, 1500]`
(Stage 1/Stage 2's shared validated regime — unchanged, since this
charter varies `p`, not `N`, as the one new variable). Master seed
`20260829` (continuing the project's seed), 2000 replicates per `N`
(development 0-999, validation 1000-1999) — Stage 2's exact replicate
count and split, kept unchanged for direct comparability.

**Ground truth**: **9 true candidate pairs** (all pairs within each of
the three motifs, identical set to Stage 2), **426 null pairs**
(`C(30,2) - 9`). Candidate status is again about nonzero vs. zero
pairwise correlation, not direct vs. indirect edges — identical
convention to Stage 2.

## Selection and gate

Identical procedure to Stage 2, applied to a wider candidate grid:
**uncorrected `alpha in [.0001, .0005, .001, .005, .01, .05, .10]`**
(Stage 2's original five values, plus two new lower rungs per the
predeclared-expectation analysis above); **BH `q in [.05, .10]`**
(unchanged). Per `N`, independently: a rule is *eligible* if, on
development replicates, recall on the 9 true pairs `>= .80` and pooled
FDR (fraction of all flagged pairs, across all `426+9` possible pairs,
that are actually null — D-013's corrected pooled definition) `<= .10`.
Among eligible rules, select the simplest (smallest uncorrected
`alpha`; else smallest BH `q`) — Stage 2's exact tiebreak, unchanged.
The selected rule must then pass validation (replicates 1000-1999) at
the same thresholds, individually, with no recorded error, to PROCEED
for that `N`.

**Output is a per-N table**, evaluated independently, matching every
prior screening/composition charter's practice.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (which of the `435` pairs were
flagged, per rule and per replicate), aggregate metrics (recall, FDR,
per-edge FPR, family-wise any-false-edge rate), the per-N decision
table, report, and figures (screening operating curve, performance vs.
`alpha`) — identical evidence set to Stage 2, at the new `p`.

## Consequences

If REASSESS at a given `N`: document which criterion failed and by how
much. Given recall was never the constraint at `p=15` and nothing about
increasing `p` changes the true pairs' own signal strength, a REASSESS
here would most likely be an FDR failure at every candidate `alpha` —
worth checking whether the predeclared arithmetic's approximation
(constant recall `~1.0`) held, or whether a genuinely new effect
appeared. Do not proceed to a `p=30` composition charter (the natural
next step, analogous to Stage 2b) until a passing screening rule exists
at that `N`.

If PROCEED at both `N`: this validates that the screening mechanism and
its rule-selection framework, completely unmodified, scale to `p=30`
with the same 9 true signals — but with a substantially narrower
uncorrected-`alpha` safety margin than at `p=15` (predicted `~.045` at
the selected rule vs. D-013's `~.011`-`.012`, roughly `4x` thinner
relative to the `.10` gate). This is a meaningful practical signal for
any future default-rule recommendation: BH's self-adjusting property
becomes more valuable, not merely available, as `p` grows, even on a
DGP where the simpler uncorrected rule still technically wins Stage 2's
tiebreak. It does **not** authorize composing screening with DPI
pruning at `p=30` (its own composition question, per Section 2.1), nor
`p` values beyond `30`, nor DGPs with a different true-signal count or
true:null ratio than tested here.
