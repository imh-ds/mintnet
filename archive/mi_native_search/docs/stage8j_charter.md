# Stage 8j Charter: Post-Screening Selection-Effect Diagnostic (main)

Status: **FROZEN before results**
Date: 2026-09-08

## Background and objective

Five dedicated diagnostic charters (D-069, D-071 through D-074) have
now tested and eliminated or failed to confirm four candidate
mechanisms for the composed-tier false-edge margin reversal: a true
collider (real, but structurally absent from either network), a
finite-sample pseudo-collider via chance correlation with the tested
pair, over-conditioning power loss via a uniformly random decoy, and a
population-level conditioning-set error (D-074's own analytic
confirmation: 99.82% of wrongly-retained decisive subsets carry an
exactly-zero population relationship). **None explains D-072's own
central finding**: the pair's own correct blocking variable, present
in the decisive subset alongside something else, still failing.

**This charter's own hypothesis, named at the close of D-074**: D-073's
own eliminated "over-conditioning" test used a **uniformly random**
decoy -- one drawn without regard to its own sample correlation with
anything. The real composed networks' own added conditioning variables
are never like that: they reached the candidate pool for a given
component **because** MINT's own screening step
(`compute_pairwise_screening_evidence`/`screen_uncorrected`) found
*some* correlation strong enough to flag, however spurious or
finite-sample-only. A screened-in variable is therefore drawn from a
**selection-biased** distribution -- the winner of an implicit
multiple-comparisons contest against many candidates -- not a
uniformly random one. This charter tests directly whether *that*
distinction, not mere presence of an extra variable, is what elevates
false rejection.

**This is the last currently-planned charter in this specific
diagnostic thread.** Per the user's own explicit framing: if this
charter also fails to confirm a mechanism, the recommended path is to
stop chasing further candidate explanations here and treat the
composed-tier reversal's own root cause as a documented, open question
-- not to keep proposing new hypotheses indefinitely. This charter's
own Consequences section states that explicitly.

## Mechanism

**Step 1 -- H7 (selection, not mere presence, drives the effect).**
Fixture: `sample_chain(n, strength, rng)` (`X1 -> X2 -> X3`, columns
`0, 1, 2`), extended with `K` independent decoy columns (`3` through
`3+K-1`, `N(0,1)`, zero population correlation with everything). Per
replicate:

- **`decoy_0`**: the first decoy column, unconditionally -- the same
  "arbitrary, unselected" comparator D-073 already used at
  `decoy_count=1`.
- **`selected_decoy`**: whichever of the `K` decoy columns has the
  largest `max(|corr(decoy, X1)|, |corr(decoy, X3)|)` in that specific
  sample -- the "winner" of an implicit screening contest against `K`
  candidates, operationalizing "reached the pool via selection on
  sample correlation" directly, without needing to reproduce MINT's own
  exact `screening_alpha=0.001` threshold (which would require a much
  larger `K` for adequate power at that strictness -- a disclosed
  simplification, not an attempt at full pipeline fidelity).

Compare three conditions at the same `N`/`strength`/`alpha(N)`:
`baseline` (`(1,)` alone), `random_decoy` (`(1, decoy_0)`), and
`selected_decoy` (`(1, selected_decoy)`). **Confirmed** if
`selected_decoy`'s own false-rejection rate is materially and
consistently higher (non-overlapping Wilson CI) than `random_decoy`'s
own rate, at every tested `(N, strength, K)` cell -- isolating the
effect to selection specifically, since both conditions add exactly
one decoy at exactly the same conditioning size.

**Step 2 -- H8 (graded with pool size): does a larger selection pool
produce a larger effect?** Sweep `K in {5, 10, 20}`. If H7 is real and
driven by selection, extreme-value reasoning predicts `selected_decoy`'s
own correlation with `{X1, X3}` -- and therefore its own induced
false-rejection rate -- should grow with `K` (more candidates to select
the maximum from). **Confirmed** if `selected_decoy`'s own
false-rejection rate at `K=20` is materially higher (non-overlapping
CI) than at `K=5`, at every tested `(N, strength)` cell. `random_decoy`
is not expected to show this pattern (it is not a selected quantity) --
reported descriptively as a control, not gated.

## Data-generating processes

`sample_chain` (already validated) extended with `K in {5, 10, 20}`
independent decoy columns -- no new motif function needed, matching
Stage 8f/8h's own precedent. `strengths = (0.3, 0.5, 0.7)`
(`CHAIN_FORK_STRENGTHS`, reused unchanged). `N in {300, 500, 750, 1000,
1500, 3000}` (this project's own shared, previously-validated regime).
`alpha(N)`: D-012's existing formula, unmodified. `R=2000` replicates
per cell, matching Stage 8a/8f/8h's own precedent.

## Compute-cost disclosure

Same closed-form, non-permutation Fisher-z mechanism as Stage 8f/8h,
on small fixtures (`3 + K <= 23` columns) -- Stage 8h's own measured
cost (`144,000` rows in under two seconds) is a close precedent, not
assumed without a fresh check. Per this project's own standing
discipline: **measure real wall-clock cost of the full sweep (both
steps, all cells, largest `K=20`) before finalizing shard plan.**

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** --
unchanged, hard requirement, per this project's established practice.

## Selection and gate

Diagnostic charter -- no PROCEED/REASSESS gate. Two predeclared
verdicts:

1. **H7 (selection effect exists)**: Confirmed / Not confirmed /
   Inconclusive, per the Step 1 criterion above.
2. **H8 (graded with pool size)**: Confirmed / Not confirmed /
   Inconclusive, per the Step 2 criterion above. Only meaningfully
   evaluated if H7 is confirmed at every tested `K` -- if selection
   shows no effect at all, asking whether a nonexistent effect scales
   with pool size is moot.

## Explicit non-goals

- **No attempt to exactly reproduce MINT's own screening threshold or
  component-formation logic.** The `max(|correlation|)` selection
  procedure is a deliberate, disclosed simplification of "reached the
  pool via a screening pass," not a literal re-run of
  `compute_pairwise_screening_evidence`/`screen_uncorrected` on a
  larger decoy pool (which would need a much larger `K` for adequate
  power at `screening_alpha=0.001` specifically).
- **No claim that this fully explains D-072's own real-network
  finding**, even if confirmed -- would strongly support, not prove,
  that the same mechanism operates inside the real screened components,
  which involve additional complexity (multiple simultaneous candidate
  edges, a shared connected component, iterative pruning) this fixture
  does not reproduce.
- **No production deployment or fix.** D-070's own recalibration
  mapping remains the deployed fix regardless of this charter's own
  result.
- **No further candidate-mechanism charter planned after this one** if
  H7 is not confirmed -- see Consequences.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the up-front
timing measurement and resulting replicate/shard decision, raw
per-replicate evidence for both steps (condition, `K`, `N`, `strength`,
replicate, p-value, rejection outcome), the Step 1 and Step 2
rejection-rate tables with Wilson CIs, both verdicts above, and a
report.

## Consequences

**If H7 and H8 both confirmed**: post-screening selection bias is
established as a real, controlled-fixture-demonstrated mechanism that
explains D-072's own central finding, and does so in a way that scales
sensibly with how large/busy a screened component's own candidate pool
is -- the strongest, most complete explanation to date for the
composed-tier reversal, five charters in. Motivates (as a separate,
not-yet-chartered future step) checking whether this predicts real
per-component pool size in `chain_fork_hub`/`overlap`'s own evidence,
and whether a correction (e.g. a selection-adjusted effective alpha)
is worth designing.

**If H7 confirmed but H8 is not (no graded scaling with `K`)**:
selection matters, but not via the specific extreme-value mechanism
this charter predicted -- a real but incompletely understood effect,
still the best candidate to date.

**If H7 is not confirmed**: post-screening selection bias, operationalized
this way, does not reproduce in a controlled fixture. Per this
charter's own explicit framing, **this is the point to stop proposing
new candidate mechanisms for this specific phenomenon** and instead
treat the composed-tier reversal's own root cause as a documented,
unresolved open question -- five (now six) dedicated diagnostic
charters would have failed to identify it, and the marginal value of a
seventh, increasingly speculative hypothesis is judged not to justify
further dedicated charter-and-evidence cycles without a genuinely new
angle. D-070's own recalibration mapping already provides a working
practical fix regardless of whether the mechanism is ever identified.
