# Stage 1 DPI Motif Validation Design

## Goal

Test whether tolerance-modified DPI removes observed transitive dependencies
from continuous Gaussian chains and measured forks without pruning genuine
conditional-dependence triangle edges. This stage evaluates only the pipeline
`DGP -> KSG pairwise MI -> tolerant DPI`.

## Scope and boundaries

Implement only the three Gaussian motifs, pairwise KSG estimation, tolerant
DPI, reproducible experiment execution, and the Stage 1 decision report.
Do not add screening, bootstrap selection, mixed-type estimators, feedback
DGPs, effect sizes, or public network APIs.

## Data-generating processes

All variables are centered Gaussian with unit marginal variance. Each condition
uses `N = [100, 200, 300, 500, 750, 1000]`, 500 replicates, and master seed
`20260829`. Strengths are `a = b = [.3, .5, .7]`.

- Chain: `X1 ~ N(0,1)`, `X2 = a*X1 + sqrt(1-a^2)*e2`, and
  `X3 = b*X2 + sqrt(1-b^2)*e3`. Keep `(1,2)` and `(2,3)`; prune `(1,3)`.
- Measured fork: `X2 ~ N(0,1)`, `X1 = a*X2 + sqrt(1-a^2)*e1`, and
  `X3 = b*X2 + sqrt(1-b^2)*e3`. Keep `(1,2)` and `(2,3)`; prune `(1,3)`.
- True triangles: sample from `N(0, inverse(Theta))`, then standardize
  marginals. Use three positive-definite precision matrices:

  ```text
  balanced = [[1, -.25, -.25], [-.25, 1, -.25], [-.25, -.25, 1]]
  moderate = [[1, -.35, -.25], [-.35, 1, -.12], [-.25, -.12, 1]]
  strong   = [[1, -.45, -.25], [-.45, 1, -.08], [-.25, -.08, 1]]
  ```

  All three undirected edges are genuine and must be retained. Cholesky
  factorization is required before simulation; a failing factorization is an
  experiment error.

## DPI rule and evaluation

For every triangle, find its weakest MI edge `Iw` and the other edges `Is1` and
`Is2`. Prune the weakest edge only when:

`Iw < (1 - tau) * min(Is1, Is2)`.

Evaluate `tau = [0, .05, .10, .15, .20, .25, .30, .40, .50]`. Strict equality
does not prune. Each replicate begins from the complete three-node pairwise MI
graph. Record retained adjacency, indirect-edge pruning, genuine-edge pruning,
perfect motif recovery, and elapsed runtime for every tau.

Replicates 0–249 are the development partition. Select the lexicographically
lowest adjacent tau pair that meets the gate when metrics are pooled across
`N >= 500`, all strengths, and all three motifs. Replicates 250–499 are the
validation partition and may not alter the selected pair.

The frozen result is **PROCEED** only if the selected adjacent pair meets every
criterion separately for every `N in [500, 750, 1000]` and every strength:

1. Chain and fork indirect-edge pruning TPR are each at least 0.80.
2. Triangle genuine-edge pruning FPR is at most 0.10.
3. No estimator, DGP, or Cholesky error is recorded.

Otherwise the outcome is **REASSESS**. A development partition without an
eligible adjacent pair is also **REASSESS**. This experiment does not select a
public default tau.

## Software and evidence

New modules have one role each: Gaussian motif simulation, DPI pruning,
topology scoring, Stage 1 runner, and reporting. The CLI is:

```powershell
.\.venv\Scripts\python.exe -m mintnet.experiments.stage1 `
  --config configs/stage1_dpi.yaml `
  --output results/generated/stage1_dpi
```

Every output directory contains resolved config, charter hash, metadata,
per-replicate raw CSV, aggregate CSV, decision JSON, report, and performance
figures. Tests cover DGP truth, precision positive-definiteness, strict DPI
boundaries, column-order invariance, fixed-seed determinism, gate selection,
and an end-to-end smoke configuration.
