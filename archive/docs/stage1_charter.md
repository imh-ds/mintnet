# Stage 1 Charter: Tolerant DPI Motif Validation

Status: **FROZEN before results**  
Date: 2026-08-28

## Objective

Test whether tolerance-modified DPI removes observed transitive dependencies
from continuous Gaussian chains and measured forks without pruning genuine
conditional-dependence triangle edges. This stage evaluates only the pipeline
`DGP -> KSG pairwise MI -> tolerant DPI`.

## Data-generating process

All variables are centered Gaussian with unit marginal variance. The frozen
configuration uses `N = [100, 200, 300, 500, 750, 1000]`, 500 replicates,
master seed `20260829`, strengths `a = b = [.3, .5, .7]`, and KSG-1 with
`k = 20`.

- Chain: `X1 -> X2 -> X3`; retain `(1,2)` and `(2,3)`, and prune `(1,3)`.
- Measured fork: `X1 <- X2 -> X3`; retain `(1,2)` and `(2,3)`, and prune
  `(1,3)`.
- Triangle: sample and standardize the three named positive-definite precision
  fixtures `balanced`, `moderate`, and `strong`; retain all three edges.

The tolerance grid is `[0, .05, .10, .15, .20, .25, .30, .40, .50]`. A
weakest edge is pruned only when its MI is strictly below
`(1 - tau) * min(the other two MIs)`; equality is retained.

## Selection and gate

Replicates 0–249 are development data. The reporting step selects the
lexicographically lowest adjacent tolerance pair that, when pooled across all
strengths, motifs, and `N >= 500`, meets the frozen performance criteria.
Replicates 250–499 are validation data only and cannot alter selection.

The result is **PROCEED** only if the selected pair meets every validation
cell at each `N in [500, 750, 1000]` and strength:

1. Chain and fork indirect-edge pruning TPR are each at least 0.80.
2. Triangle genuine-edge pruning FPR is at most 0.10.
3. No estimator, DGP, or Cholesky error is recorded.

Otherwise the result is **REASSESS**. This stage does not select a public
default tolerance or authorize Stage 2 work.

## Required evidence

Each run persists its resolved configuration, this charter's SHA-256, commit
and runtime metadata, and raw per-replicate evidence. Aggregate metrics,
gate decision, report, and figures are intentionally produced by the separate
reporting step rather than the runner.
