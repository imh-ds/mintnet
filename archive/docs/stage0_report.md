# Stage 0.1 Gaussian MI Report

Date: 2026-08-28

Stage: R1 — Gaussian MI estimator viability

## Decision: PROCEED

The frozen Gaussian Stage 0.1 experiment completed with 72,000 estimates
(`6` sample sizes × `6` correlations × `4` k values × `500` replicates) and
no recorded estimator errors. Generated evidence is located at
`results/generated/stage0_gaussian/` and is intentionally not committed.

The development partition selected `k=20` by lowest moderate-signal RMSE.
The independent validation partition passed every predeclared gate:

- Moderate-signal absolute bias was at most 0.0134 nats (limit: 0.05).
- Moderate-signal RMSE was at most 0.0452 nats (limit: 0.10).
- Strength-ranking Spearman correlation was 1.00 (minimum: 0.90).
- The null-estimate 95th percentile was 0.0213 nats (limit: 0.05).

## Consequence

The KSG-1 estimator is usable for the tested continuous Gaussian setting. The
next authorized methodological task is the separately chartered Stage 1 DPI
motif validation; this result does not validate nonlinear, mixed-type, or
causal interpretations.
