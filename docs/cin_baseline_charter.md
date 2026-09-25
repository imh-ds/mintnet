# CIN Task 11 Statistical Panel Charter

This charter freezes the bounded CIN v0.1.0 statistical-panel procedure. It is
an implementation and validation contract, not a claim that the panel has
already been run.

## Scope and matrix

The panel contains cases A-I from the simulation truth contract and the
historical `regression` organic-network smoke fixture. Each ordinary case has
10 development replicates (`0..9`) and 20 validation replicates
(`1000..1019`), with seeds derived from the full-grid coordinates. The
regression fixture is descriptive historical smoke only.

The method matrix is fixed:

| cases | methods |
| --- | --- |
| A-E | `cin`, `cin_linear`, `ebicglasso` |
| F-I | `cin` |
| regression | `cin` |

`cin_linear` uses the CIN code path with `max_curvature_rank=0`. EBICglasso
uses the same continuous data as CIN and reports convergence failures as
failure rows. It is not applied to categorical or mixed cases and no qgraph
reference-equivalence claim is made.

## Metrics and views

Raw rows preserve pair completion, AP, prevalence, AP minus prevalence,
thresholded effect and agreement views, nonempty-view counts, strong-edge
recall when population CMI exists, oracle-CMI error diagnostics, categorical
node loss, null positive-weight quantiles, orientation-gap quantiles, and
numerical floor diagnostics. AP requires every pair to be complete. An empty
display view has `NaN` precision and an explicit empty flag.

The only display thresholds eligible for development selection are `0.005`,
`0.01`, and `0.02`. Selection considers A/B development rows only. A candidate
qualifies when mean precision is at least `0.70` over nonempty views and the
nonempty-view fraction is at least `0.80` in both A and B. Choose the largest
mean strong-edge recall, breaking ties toward the smaller threshold. If none
qualifies, choose the largest mean minimum precision and mark the eventual
validation display gate as expected to fail. Validation cannot change this
choice.

## Stability and budget

Stability is descriptive for validation cases A, B, and F with 10 repeats at
fraction `0.8`, subject to a per-estimate 600-second limit. The panel is
bounded by 12 aggregate runner-hours. A preflight estimate must use the
accepted Task 10 cost envelope and the current compute ledger. If the full
matrix exceeds the remaining budget, replicate reduction must be documented
before freezing; hard cases C, D, and I may not be silently dropped.

## Evidence protocol

Freeze this charter, the resolved configuration, metric definitions, gates,
seed derivation, method matrix, sharding, and budget before development. Run
development shards, make at most one global methodological correction, and
rerun/refreeze development if a correction is made. Run validation once on new
seeds. The gate checker refuses development contamination, count mismatch,
duplicate identities, missing sidecars, and charter-hash mismatch.

The report includes contributing counts and Monte Carlo standard errors. It
does not claim precise tail probabilities, FDR control, causal effects, or
general recovery beyond each named scope. D, I, regression, variance-only/XOR,
stability, and high-p categorical observations are reported as descriptive or
unsupported where the gates do not apply.
