# Stage 1d Charter: Per-Cell Development Selection (R2d)

Status: **FROZEN before results**
Date: 2026-08-28

## Background and objective

`docs/stage1c_charter.md` raised the gate's minimum sample size to `N =
750` and added `N = 1500, 2000` to test whether the R2b `strong`-family
triangle-FPR failure was a sample-size/power limitation. It was: at fixed
`alpha`, `strong`-family FPR fell from `.187` (`N = 500`) to `.015`
(`N = 2000`), converging toward zero (`docs/decision_log.md`, D-004). The
formal gate nonetheless returned REASSESS, because the development
**selection rule** — pick the first ascending `alpha` pair whose *pooled
average* across all strengths and all `N >= 750` clears both thresholds —
is blind to per-`N` variation once a wide `N` range is pooled together.
Strong performance at the newly added `N = 1500`/`2000` cells pulled the
pooled average under the FPR threshold at an `alpha` pair (`0.005, 0.01`)
that still failed individually at `N = 750`/`1000`. A materially better
pair (`0.05, 0.10`) existed in the same tested grid and would have passed
every validation cell individually, but the ascending scan never reached it
because it stopped at the first pooled-passing pair.

This charter changes only the **development selection rule**: an `alpha`
value is eligible only if it clears both thresholds in *every* individual
`(N, strength)` cell, not merely on average across them. Selection then
proceeds exactly as before — the first ascending adjacent pair where both
members are eligible. This is a methodology correction, not a new
experiment on the pruning mechanism, the DGP, or the alpha grid, all of
which are unchanged from R2c and already have strong supporting evidence.

## Data-generating process

Identical to R2c: `N = [100, 200, 300, 500, 750, 1000, 1500, 2000]`,
strengths `a = b = [.3, .5, .7]`, `balanced`/`moderate`/`strong` triangle
fixtures, 500 replicates, master seed `20260829`, development replicates
0-249, validation replicates 250-499. No new simulation is required; R2c's
raw evidence (`results/generated/stage1c_dpi/raw_metrics.csv`) already
covers every condition this charter's selection rule needs and may be
reused directly rather than re-run, since the DGP, mechanism, and seeds are
byte-for-byte identical.

## Mechanism

Unchanged from R2b/R2c: per-edge Fisher-z partial-correlation test, `alpha`
grid `[.0001, .001, .005, .01, .05, .10, .20, .30, .50]`.

## Selection and gate

**The only change from R2c.** Define an `alpha` as *development-eligible*
only if, for every `(N, strength)` cell with `N >= 750`:

1. Chain indirect-edge pruning TPR at that cell is at least 0.80.
2. Fork indirect-edge pruning TPR at that cell is at least 0.80.
3. Triangle true-edge retention FPR at that cell is at most 0.10.

(Previously, R2b/R2c required these three criteria to hold only for the
*pooled average* across cells, not for each cell individually.) Selection
then proceeds as before: the first ascending adjacent pair of
development-eligible alphas is selected. Validation (replicates 250-499)
is unchanged — every cell at the selected pair must individually pass, at
each `N in [750, 1000, 1500, 2000]` and strength, exactly as R2c defined it.
No error may be recorded. This stage does not select a public default alpha
and does not authorize Stage 2 work.

## Required evidence

If R2c's raw evidence is reused, this charter's evidence package persists a
pointer to that evidence (its file hash and the R2c charter's SHA-256) in
place of re-simulating; the resolved configuration, this charter's SHA-256,
commit and runtime metadata, and the aggregate metrics, gate decision,
report, and figures are still produced fresh under this charter's own
selection rule, mirroring R2c's reporting pipeline in every other respect.

## Consequences

If REASSESS: document plainly. A selection rule that still cannot find a
passing alpha pair even when checked per-cell would mean no single `alpha`
in the tested grid works uniformly across strengths and `N >= 750` — a
real limitation of a single global threshold, not a pooling artifact, and
would motivate either a finer alpha grid or a strength- or `N`-conditional
threshold, each requiring its own charter.

If PROCEED: Stage 2 candidate-edge screening may be planned using the
selected alpha, scoped to `N >= 750` per R2c. The confidence-scored-edge
option from D-003 remains open and unaffected by this result.
