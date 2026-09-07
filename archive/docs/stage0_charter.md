# Stage 0.1 Charter: Gaussian MI Sanity

Status: **FROZEN before results**  
Date: 2026-08-28

## Objective

Validate the bivariate continuous KSG-1 mutual-information estimator against
the analytic Gaussian reference before any DPI experiment is started.

## Data-generating process

For each condition, draw `N` independent samples from a centered bivariate
normal distribution with unit marginal variances and correlation `rho`. The
population mutual information, in nats, is:

\[
I(X;Y)=-\frac12\log(1-\rho^2).
\]

The final configuration fixes `N = [100, 200, 300, 500, 750, 1000]`,
`rho = [0, .1, .3, .5, .7, .9]`, `k = [3, 5, 10, 20]`, 500 replicates per
condition, and master seed `20260828`.

## Selection and gate

Replicates 0–249 form the development partition. Select the k with lowest
mean RMSE across `N = [300, 500]` and `rho = [.3, .5, .7]`; ties choose the
smaller k. Replicates 250–499 form the validation partition only.

The selected k receives **PROCEED** only if all validation criteria hold:

1. Each moderate-signal cell at `N = 300` and `500` has absolute bias no
   greater than 0.05 nats and RMSE no greater than 0.10 nats.
2. The Spearman correlation between six rho strengths' pooled mean estimates
   and analytic MI is at least 0.90.
3. The 95th percentile of null (`rho = 0`) estimates is no greater than 0.05
   nats.

Any estimator error or failed criterion produces **REASSESS**. This charter
must not be edited after generated results exist.

## Required evidence

Every run saves its resolved configuration, charter SHA-256, environment and
commit metadata, raw per-replicate CSV, aggregate metrics, decision JSON and
report, and bias/RMSE/runtime figures under `results/generated/`.
