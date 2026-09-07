# Stage 1g Charter: Margin-Robust Development Selection (R2g)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

`docs/stage1f_charter.md`'s per-cell selection rule returns the first
ascending adjacent alpha pair where both members pass every individual
cell on development data. Applied to R2f's evidence, it selected
`(0.09, 0.10)`, which failed validation at one cell by `.004` — under half
a standard error. The cause was not noise in the validation check itself:
`alpha = 0.09` cleared its development threshold at that same cell by only
`.008`, also under one standard error, while `alpha = 0.10` and `0.11`
both cleared it by roughly `.013`-`.018` on both development and
validation data (`docs/decision_log.md`, D-007). The rule has no concept
of margin — it accepts the first pair that merely crosses zero, including
one whose crossing is itself statistically indistinguishable from not
crossing at all.

This charter changes only the development **selection rule**, again: among
adjacent pairs where both members are per-cell eligible (unchanged
definition from R2d), select the pair that maximizes the *worst-case
margin* — the smallest amount by which any cell clears its threshold —
rather than the first such pair found in ascending order. This is not a
new mechanism, DGP, alpha grid, or per-cell eligibility definition; R2f's
raw evidence is reused verbatim, exactly as R2d reused R2c's.

## Data-generating process

Identical to R2f: `N = [100, 200, 300, 500, 750, 1000, 1500, 2000]`,
strengths `a = b = [.3, .5, .7]`, `balanced`/`moderate`/`strong` triangle
fixtures, master seed `20260829`, 2000 replicates (development 0-999,
validation 1000-1999), alpha grid `[.06 ... .25]` at 0.01 resolution.
`results/generated/stage1f_dpi/raw_metrics.csv` is reused directly; no new
simulation is performed.

## Mechanism

Unchanged: per-edge Fisher-z partial-correlation test.

## Selection and gate

**Margin definition.** For a given alpha, define its cell margins over
every `(N, strength)` cell with `N >= 750`:

- chain/fork cells: `indirect_prune_tpr - minimum_indirect_prune_tpr`
- triangle cells: `maximum_triangle_true_edge_prune_fpr - true_edge_prune_fpr`

An alpha's **margin** is the minimum of these values across all its cells
(its worst-case slack). An alpha is development-eligible only if its
margin is non-negative — identical to R2d/R2f's per-cell rule.

**Selection.** Among all adjacent pairs of development-eligible alphas,
select the pair maximizing `min(margin(left), margin(right))` — the most
robust adjacent pair, not the first one found. Ties broken by the
lexicographically lowest pair. If no adjacent eligible pair exists,
REASSESS as before.

Validation (replicates 1000-1999) is unchanged: every cell at the selected
pair must individually pass, at each `N in [750, 1000, 1500, 2000]` and
strength. No error may be recorded. This stage does not select a public
default alpha and does not authorize Stage 2 work by itself.

## Required evidence

Same evidence package as R2d: resolved configuration, this charter's
SHA-256, a pointer to (and hash of) the reused R2f raw evidence, commit and
runtime metadata, aggregate metrics, gate decision, report, figures, and
the exploratory calibration summary.

## Consequences

If REASSESS: the margin-robust rule finding no viable pair, despite R2f's
data showing `(0.10, 0.11)` clearing every cell with real margin on both
development and validation splits, would indicate an error in this
charter's selection logic rather than new evidence about the mechanism;
recheck the implementation before drawing any substantive conclusion.

If PROCEED: this closes the R2/R2b/R2c/R2d/R2e/R2f/R2g line of Stage 1
evidence with a margin-robust, independently verified alpha pair. The
validated operating range is `N >= 750` under conditional-independence
pruning. Stage 2 candidate-edge screening may be planned using the
selected pair. The confidence-scored-edge-representation option from D-003
remains open and unaffected by this result.
