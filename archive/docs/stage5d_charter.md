# Stage 5d Charter: Signal-Strength Sweep — Does MINT's Advantage Over EBICglasso Hold Across Weak-to-Strong Effects? (R6)

Status: **FROZEN before results**
Date: 2026-09-01

## Background and objective

D-047 through D-049 characterized MINT-vs-EBICglasso on Gaussian
composed noisy networks along one axis — nuisance/noise-column count —
at one fixed signal strength (`.5`) throughout. `docs/stage5a_charter.md`'s
own recommendation flagged signal strength as the other open variable,
deliberately deferred (D-047's own non-goals; D-048's consequences
section held it back explicitly until the `alpha`-recalibration
question resolved). That question is now resolved (D-049): `alpha(p)`
is the better-tested MINT configuration for any further `p`-varying R6
work. This charter opens the deferred strength axis, using `alpha(p)`
as the default MINT configuration from the start rather than the fixed
`alpha` D-047 originally used.

**What "wins" has meant throughout this arc, restated for this
charter's own scope:** every MINT-vs-EBICglasso cell tested so far
(D-047 through D-049) found **perfect recall for both methods** — the
entire measured gap is precision, i.e. EBICglasso retaining more false
edges than MINT among noise-noise and noise-signal pairs, not either
method missing real structure. **This charter is the first one in the
arc where that could plausibly change** — at weak enough signal
strength, missing a real edge (recall < 1) becomes a live possibility
for either method, not just a false-positive question. Both failure
modes should be reported, not just precision, if recall drops below
`1.0` anywhere.

## No strong directional prediction — stated explicitly

Unlike Stage 5b's noise-count sweep, which followed from a specific,
falsifiable mechanistic claim (EBICglasso's `ln(p)` penalty vs. MINT's
`p`-adjusted `alpha`), this charter has no comparably sharp a priori
mechanism to test. Plausible expectations pull in different
directions: very strong signal should let both methods approach
ceiling performance (F1 near `1.0`), narrowing the gap simply because
there is less room left for MINT's precision edge to matter; very weak
signal could go either way — MINT's own per-edge test might become
noisier and lose precision faster than EBICglasso's global penalty, or
the opposite. This charter is exploratory on this axis, per
`docs/stage5a_charter.md`'s own "no claim of superiority" framing — the
predeclared reading below reports the pattern found, not a
confirm/refute verdict against a stated prediction.

## Grid

Same two shapes as every prior R6 charter (`chain_fork_hub`,
`overlap`), same `N in {500, 1500}` (Stage 5b/5c's own reduced grid,
retained for direct comparability). **Noise held at each shape's own
native column count** (multiplier `1` — the noise-count axis is
already characterized separately; conflating it with strength here
would re-introduce exactly the confound this project's own
single-variable discipline exists to avoid). **Strength `in {.3, .5,
.7}`** — `.5` is every prior R6 charter's own value, included here as
the direct link back to D-047/D-049 rather than a fresh draw at a
different seed; `.3` and `.7` are new, bracketing it symmetrically in
the same units this project's own DGP fixtures already use throughout
(Stage 4k's own chain/fork/hub strength grid included `.3`-`.7`).

MINT: `alpha(p)` (Stage 5c's own log-linear interpolation of Stage 2's
two calibrated anchor points), evaluated at each shape's own native
`p` (`15` for both shapes at multiplier `1`, so `alpha(p) = alpha(15) =
.001` exactly — numerically identical to D-047's own original value,
carried forward via the now-preferred mechanism rather than a bare
constant). DPI's own `alpha(N)` (D-012's general formula) unchanged.
EBICglasso: `gamma=.5`, `n_lambda=100`, `lambda_min_ratio=.01`,
unchanged. `2,000` replicates per cell (development `0`-`999`,
validation `1000`-`1999`). New, disjoint seed stream (fresh draws, not
a re-score of any prior charter's data, since strength changes the
underlying DGP draw itself).

## Sharding: three dimensions from the start

Following Stage 5c's own fix (three shard-filterable dimensions so no
CI shard ever contains more than one task), this charter's runner
shards by `(dgp, N, strength)` from the outset —
`.github/workflows/sharded_benchmark.yml`'s existing three-dimension
support requires no further changes.

## Metrics and reporting

Full per-cell metrics (precision, recall, F1, SHD, runtime, both
methods), reported per `(dgp, N, strength)` cell, full grid, no cell
omitted. **Recall reported explicitly and prominently at every cell**,
not folded silently into F1 — per this charter's own restated scope
note above, a recall drop below `1.0` anywhere would be new information
this whole R6 arc has not yet encountered, and must not be allowed to
pass unremarked inside an aggregate F1 number.

## Decision structure

Descriptive, not a gate, same standing as every prior R6 charter in
this arc. Predeclared reporting requirement (not a confirm/refute
branch, per this charter's own "no strong directional prediction"
section above): state, per `(dgp, N)` series across ascending strength,
whether the F1 gap is increasing, decreasing, flat, or non-monotonic,
and separately state whether recall stays at `1.0` for both methods
throughout or drops anywhere — the second question gets its own
sentence in the report regardless of the answer to the first.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate metrics for both methods at every `(dgp,
N, strength)` cell, and a report presenting the full grid, the F1-gap-
by-strength comparison, and the recall-floor check described above.

## Consequences

Completes the two-axis characterization of D-047's original finding
(noise-count: D-048/D-049; strength: this charter) using the
now-preferred `alpha(p)` MINT configuration throughout. Neither
D-047 nor D-048 nor D-049 is retracted or superseded by this charter —
each remains a valid reading of its own tested axis and configuration.
If a recall drop is found at weak strength, that would be new evidence
warranting its own follow-up charter (a precision/recall trade-off
question this arc has not yet had to address) rather than being folded
into this charter's own predeclared reporting requirement after the
fact.
