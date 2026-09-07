# Stage 1c Charter: Conditional-Independence Motif Validation at a Higher N Floor (R2c)

Status: **FROZEN before results**
Date: 2026-08-28

## Background and objective

`docs/stage1b_charter.md` tested conditional-independence pruning
(partial-correlation Fisher-z test) against the R2 charter's failure and
returned REASSESS (`docs/decision_log.md`, D-003): chain/fork TPR and
triangle FPR now overlap in a real feasible `alpha` region, and the
`balanced`/`moderate` triangle fixtures pass cleanly. The `strong` fixture
still fails, but only at the gate's smallest sample size, `N = 500`, and its
FPR falls monotonically with `N` at every tested `alpha` (e.g., `alpha =
.05`: `.187` at `N = 500` down to `.111` at `N = 1000`, development
replicates) — unlike R2, where the analogous curve was flat regardless of
`N`. This is consistent with a sample-size/power limitation specific to
detecting `strong`'s weakest edge (population partial correlation `~0.08`),
not a mechanism-wide confound.

This charter tests that hypothesis directly: **does the R2b mechanism clear
its gate once the minimum sample size is raised to `N = 750`, dropping `N =
500` from the gate floor?** This is not a retroactive re-selection of an
alpha value that happened to pass in already-observed R2b data — the alpha
grid and every other condition are held identical to R2b. It is a scope
revision to the method's stated minimum operating sample size, decided from
the *shape* of the R2b trend before generating any new evidence, exactly as
Stage 0 fixed `k = 20` and Stage 1 fixed its own `N` floor from prior
evidence rather than from this run's results.

## Data-generating process

Identical DGP, precision fixtures, and master seed to R2b, extended with two
new sample sizes: `N = [100, 200, 300, 500, 750, 1000, 1500, 2000]`. Because
seed derivation is positional on each value's index in the frozen
`sample_sizes` list, appending `1500` and `2000` after the existing six
values reproduces R2b's exact simulated data at every previously tested `N`
and adds genuinely new data only at `N = 1500` and `N = 2000`. Strengths
`a = b = [.3, .5, .7]`, 500 replicates, development replicates 0-249,
validation replicates 250-499 — unchanged from R2b.

## Mechanism

Unchanged from R2b: per-edge Fisher-z partial-correlation test, `alpha` grid
`[.0001, .001, .005, .01, .05, .10, .20, .30, .50]`, identical to R2b. This
charter does not search over a different alpha grid; the R2b grid already
produced a real overlap region, and there is no trend evidence motivating a
change to it.

Confidence-score reporting (`1 - p_value`) remains exploratory and
non-gating, unchanged from R2b.

## Selection and gate

Structurally identical to R2b, with one frozen change: the large-N gate
floor moves from `N >= 500` to **`N >= 750`**. Development replicates 0-249
select the lexicographically lowest adjacent `alpha` pair meeting, pooled
across strengths, families, and `N in [750, 1000, 1500, 2000]`:

1. Chain and fork indirect-edge pruning TPR each at least 0.80.
2. Triangle true-edge retention FPR (each of the three edges, all three
   families) at most 0.10.
3. No estimator, DGP, regression, or Cholesky error is recorded.

Validation replicates 250-499 cannot alter selection. The result is
**PROCEED** only if the selected pair meets every validation cell
individually at each `N in [750, 1000, 1500, 2000]` and strength. Otherwise
**REASSESS**. `N = 500` evidence is generated (for continuity with R2b) and
reported descriptively but excluded from the gate.

This stage does not select a public default alpha or `N` floor for
production use and does not authorize Stage 2 work.

## Required evidence

Same as R2b: resolved configuration, this charter's SHA-256, commit and
runtime metadata, raw per-replicate evidence (partial correlations,
z-statistics, p-values, prune/retain decisions per alpha, confidence score),
aggregate metrics, gate decision, report, figures, and the exploratory
calibration summary, produced by a separate reporting step.

## Consequences

If REASSESS: document plainly. Do not build Stage 2 screening, bootstrap,
mixed-type, or confidence-scored-network layers on this evidence. A
mechanism that still fails at `N = 750` and above, after already resolving
`balanced`/`moderate` and improving with `N` through 1000, would point to a
harder problem with the `strong` fixture's edge-strength asymmetry
specifically, warranting its own diagnosis before any further sample-size
extension.

If PROCEED: the validated operating range is `N >= 750` under this
mechanism, not `N >= 500`; that scope restriction must be carried into any
Stage 2 planning. Separately, if exploratory calibration continues to look
promising, a dedicated charter for a confidence-scored edge representation
may be proposed as before — an executive decision, not an automatic
consequence.
