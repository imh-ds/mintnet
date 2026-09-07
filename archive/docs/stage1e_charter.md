# Stage 1e Charter: Per-Cell Selection at Higher Replicate Count (R2e)

Status: **FROZEN before results**
Date: 2026-08-28

## Background and objective

`docs/stage1d_charter.md` fixed R2c's pooled-average selection artifact by
requiring every individual `(N, strength)` cell to pass before an alpha is
eligible. Applied to R2c's evidence, only `alpha = 0.10` passed every cell,
with no adjacent eligible neighbor (`docs/decision_log.md`, D-005).
`alpha = .05` and `alpha = .20` each missed by a small margin — `strong`
triangle FPR at `.117`/`.111` against the `.10` gate, and several chain/fork
TPR values at `.76`-`.80` against the `.80` gate. At 250 development
replicates per cell, the binomial standard error is `~.025` (at a true rate
of `.80`) and `~.019` (at `.10`); every one of these misses is smaller than
one standard error. This is consistent with normal sampling noise around a
genuine boundary near `alpha ~ .10`-`.15`, not a real gap.

This charter tests that directly: **does quadrupling the development
replicate count (250 to 1000) resolve the near-misses one way or the
other?** This is not a new mechanism, DGP, or selection rule — it is a
statistical-power increase on the evaluation itself, decided from the
observed noise magnitude in R2d, before generating any new evidence.

## Data-generating process

Identical DGP and fixtures to R2c/R2d: `N = [100, 200, 300, 500, 750, 1000,
1500, 2000]`, strengths `a = b = [.3, .5, .7]`, `balanced`/`moderate`/
`strong` triangle fixtures, master seed `20260829`. **Replicate count
increases from 500 to 2000**, split development 0-999 / validation
1000-1999 (previously 0-249 / 250-499). Because seed derivation is
positional on replicate index alone, replicates 0-499 reproduce R2c/R2d's
exact simulated data; replicates 500-1999 are new. A fresh full simulation
run is the simplest correct way to generate this (the runner is
deterministic and cheap to re-run in full; there is no need to graft new
replicates onto old evidence files).

## Mechanism

Unchanged from R2b/R2c/R2d: per-edge Fisher-z partial-correlation test,
alpha grid `[.0001, .001, .005, .01, .05, .10, .20, .30, .50]`.

## Selection and gate

Unchanged from R2d: the gate floor is `N >= 750`, and an alpha is
development-eligible only if it passes every individual `(N, strength)`
cell — chain and fork indirect-edge pruning TPR at least 0.80, triangle
true-edge retention FPR at most 0.10 — not merely a pooled average.
Selection returns the first ascending adjacent pair of eligible alphas.
Validation (now replicates 1000-1999) is unchanged: every cell at the
selected pair must individually pass at each `N in [750, 1000, 1500, 2000]`
and strength. No error may be recorded. This stage does not select a
public default alpha and does not authorize Stage 2 work.

## Required evidence

Same evidence package as R2c: resolved configuration, this charter's
SHA-256, commit and runtime metadata, raw per-replicate evidence, aggregate
metrics, gate decision, report, figures, and the exploratory calibration
summary.

## Consequences

If REASSESS with near-misses still inside one standard error of their new,
smaller noise band: the boundary is being resolved correctly and simply
sits closer to one side than R2d's coarse alpha grid can express: finer
alpha resolution near `.10`-`.20`, frozen in a new charter, would be the
next step — not more replicates again.

If REASSESS with misses now clearly outside the (now smaller) noise band:
treat this as a real result, not noise, and diagnose accordingly before any
further replicate-count increase.

If PROCEED: the validated operating range is `N >= 750`, and the selected
alpha pair reflects the mechanism's real behavior rather than sampling
noise. Stage 2 candidate-edge screening may be planned using it. The
confidence-scored-edge-representation option from D-003 remains open and
unaffected by this result.
