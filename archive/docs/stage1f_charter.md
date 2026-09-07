# Stage 1f Charter: Finer Alpha Resolution Near the Passing Region (R2f)

Status: **FROZEN before results**
Date: 2026-08-28

## Background and objective

`docs/stage1e_charter.md` quadrupled development replicates to test whether
R2d's near-misses at `alpha = .05` and `alpha = .20` were sampling noise.
They were not, uniformly: `alpha = .05`'s failure sharpened into a real,
~3-standard-error miss, while `alpha = .20`'s failures shrank from 12 to 8
cells and mostly moved inside one standard error (`docs/decision_log.md`,
D-006). `alpha = .10` remains the only value passing every individual cell.
Two additional reference points from the same R2e evidence bound the
region further: `alpha = .01` fails at three `strong`-family cells (up to
`.21` against the `.10` gate — decisively, not marginally), and
`alpha = .30` fails chain/fork TPR at all 24 tested cells (mean `.698`
against the `.80` gate — decisively).

This charter does not test a new mechanism, DGP, or selection rule. It
tests whether a **finer alpha grid** between the confirmed failure at
`.05` and the confirmed-but-marginal region near `.20` contains an
adjacent pair that both pass the per-cell rule — which the coarse grid
(`.05 -> .10 -> .20`) is too widely spaced to detect even if such a pair
exists.

## Data-generating process

Identical to R2e: `N = [100, 200, 300, 500, 750, 1000, 1500, 2000]`,
strengths `a = b = [.3, .5, .7]`, `balanced`/`moderate`/`strong` triangle
fixtures, master seed `20260829`, 2000 replicates (development 0-999,
validation 1000-1999). Because seed derivation does not depend on alpha,
this reuses R2e's exact simulated data for every condition; only the
alpha grid tested against that data changes.

## Mechanism

Unchanged: per-edge Fisher-z partial-correlation test. **Alpha grid
narrows and sharpens** from R2b-R2e's nine-point `[.0001 ... .50]` grid to
twenty points at 0.01 resolution spanning the region bounded by R2e's
evidence: `[.06, .07, .08, .09, .10, .11, .12, .13, .14, .15, .16, .17,
.18, .19, .20, .21, .22, .23, .24, .25]`. The coarse grid's decisive
results outside this range (`.01`, `.30`, and beyond) are not retested;
they already have clear, recorded answers and retesting them would not
change this charter's question.

## Selection and gate

Unchanged from R2d/R2e: the gate floor is `N >= 750`; an alpha is
development-eligible only if it passes every individual `(N, strength)`
cell (chain/fork TPR `>= .80`, triangle FPR `<= .10`); selection returns
the first ascending adjacent pair of eligible alphas. Validation
(replicates 1000-1999) requires every cell to pass individually at the
selected pair, at each `N in [750, 1000, 1500, 2000]` and strength. No
error may be recorded. This stage does not select a public default alpha
and does not authorize Stage 2 work.

## Required evidence

Same evidence package as R2e: resolved configuration, this charter's
SHA-256, commit and runtime metadata, raw per-replicate evidence,
aggregate metrics, gate decision, report, figures, and the exploratory
calibration summary.

## Consequences

If REASSESS: this would mean no alpha in a 0.01-resolution grid across the
entire region bounded by two decisive failures (`.05` and `.30`) admits an
adjacent passing pair — a materially different and more serious finding
than any prior REASSESS in this line, since it would rule out grid
resolution as the explanation. It would warrant reconsidering whether a
single global alpha can ever satisfy all three triangle families
simultaneously, rather than further grid refinement.

If PROCEED: the validated operating range is `N >= 750` under a
conditional-independence pruning rule with the selected alpha, established
across six converging rounds of evidence. Stage 2 candidate-edge screening
may be planned using it. The confidence-scored-edge-representation option
from D-003 remains open and unaffected by this result.
