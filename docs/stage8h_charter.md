# Stage 8h Charter: Over-Conditioning Power-Loss Diagnostic (main)

Status: **FROZEN before results**
Date: 2026-09-08

## Background and objective

D-072 (Stage 8g) audited the real composed-network evidence directly
and found D-071's own pseudo-collider hypothesis largely absent (12 of
14 cells contradicted it). Instead, a dominant, unanticipated pattern
emerged: for `99.7%` of wrongly-retained named-indirect-pair false
edges at `conditioning_size_used >= 2`, the pair's own known-correct
legitimate separator was **already present** inside the decisive
conditioning subset -- combined with one or more other variables -- and
the test still found "significant" dependence anyway. D-072's own
leading (but explicitly untested) explanation: an **over-conditioning
power-loss effect** -- adding any additional variable to an
already-sufficient, correct conditioning set degrades the test's own
ability to detect the true independence it would have found with that
variable alone. This charter tests that hypothesis directly, in a
controlled, known-truth fixture, mirroring Stage 8f's own precedent for
turning a data-observed pattern into a falsifiable isolated test.

**Why this is a genuinely different claim from D-071's collider
hypothesis.** A collider (true or pseudo) requires the *added* variable
to have some correlation, real or by chance, with the tested pair. This
charter's own hypothesis requires no such thing: the added variable can
be **completely, exactly independent** of everything else in the
fixture, with zero correlation by construction (not merely by
population design, as in Stage 8f's own decoys, but as the *entire
point* of the manipulation) -- if false rejection still rises when a
provably-irrelevant variable is added to an already-correct conditioning
set, the cause is intrinsic to the significance test's own finite-
sample behavior under compound conditioning, not to anything the added
variable happens to correlate with.

**Why classical test theory does not obviously predict this.**
Fisher-z's own standard error already accounts for conditioning-set
size (`1/sqrt(N - 3 - |conditioning|)`) -- in the large-`N`, well-
specified linear-Gaussian limit, adding a truly independent conditioning
variable should leave the test's own Type-I error rate at exactly
`alpha`, not inflate it. If this charter finds inflation anyway, it
would point specifically to a **finite-sample** effect (e.g. OLS
residualization against several regressors picking up spurious
in-sample structure that the theoretical SE correction does not fully
offset at realistic, non-asymptotic `N`) -- not a defect in the test's
own asymptotic theory.

## Mechanism

**Step 1 -- H4 (existence): does adding one irrelevant variable to an
already-sufficient conditioning set raise the false-rejection rate?**

Fixture: `sample_chain(n, strength, rng)` (`X1 -> X2 -> X3`, columns
`0, 1, 2`), extended with independent decoy columns `W1, W2, W3 ~
N(0,1)` (zero correlation with everything by construction, exactly as
in Stage 8f's own `step2_control`). The tested pair is `(0, 2)`
(`X1`, `X3`) -- genuinely, exactly conditionally independent given `X2`
alone, this project's own already-validated ground truth for chain
(D-012 and earlier). Compare, at the same `N`/`strength`/`alpha(N)`:

- **Baseline**: `compute_partial_correlation_evidence(data, 0, 2,
  (1,))` -- the correct, sufficient conditioning set alone.
- **Plus one decoy**: `compute_partial_correlation_evidence(data, 0, 2,
  (1, 3))` -- the same correct variable, plus one independent decoy.

**Confirmed** if the "plus one decoy" condition's own false-rejection
rate (`p <= alpha(N)`, against the true null) is materially and
consistently higher (non-overlapping Wilson CI) than the baseline's own
rate, at every tested `(N, strength)` cell.

**Step 2 -- H5 (saturation shape): does the effect grow with more added
decoys, or saturate after the first one, matching D-069's own already-
observed shape?**

D-069 found the real composed-tier reversal is already total at
`conditioning_size_used=2` and does **not** worsen further at `3` or
`4` -- a sharp step, not a graded climb. Extend Step 1's comparison to
`(1, 3)`, `(1, 3, 4)`, and `(1, 3, 4, 5)` (one, two, and three added
decoys respectively -- conditioning sizes `2`, `3`, `4`, matching
`growing_subset_dpi`'s own `max_conditioning_size=4` cap). **Confirmed**
if the false-rejection rate at sizes `3` and `4` is **not** reliably
higher than at size `2` (overlapping CIs, or no consistent further
increase) -- the same "total already at the smallest multi-variable
size, no further degradation toward the cap" shape D-069 already
established empirically, now tested as an explicit prediction in a
controlled fixture rather than merely observed after the fact. **Not
confirmed** if the rate keeps climbing materially from size `2` through
`4` -- a graded effect would be a different, new shape not matching
D-069's own real-evidence pattern, undermining this as the specific
explanation for that pattern (even if Step 1's own H4 is confirmed).

## Data-generating processes

`sample_chain` (already validated, `mintnet.simulation.motifs`),
extended with independent `N(0,1)` decoy columns -- no new motif
function needed, matching Stage 8f's own precedent for a minimal
in-module extension rather than a new `motifs.py` addition.
`CHAIN_FORK_STRENGTHS = (0.3, 0.5, 0.7)` (this project's own shared,
already-validated regime, `mintnet.experiments.stage8a_conditions`,
reused unchanged). `N in {300, 500, 750, 1000, 1500, 3000}` (this
project's own shared, previously-validated regime, unchanged).
`alpha(N)`: D-012's existing formula, unmodified. `R=2000` replicates
per cell, matching Stage 8a/8f's own precedent.

## Compute-cost disclosure

Identical mechanism to Stage 8f's own (closed-form, non-permutation
Fisher-z test on small, 3-6 column fixtures) -- Stage 8f's own measured
cost (`108,000` rows in well under a minute) is a close upper-bound
precedent, not assumed without a fresh check. Per this project's own
standing discipline: **measure real wall-clock cost of the full sweep
(both steps, all cells) before finalizing shard plan** -- not assumed
cheap from Stage 8f's own precedent alone.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** --
unchanged, hard requirement, per this project's established practice.

## Selection and gate

Diagnostic charter -- no PROCEED/REASSESS gate on the whole (mirrors
Stage 8d/8f/8g's own precedent). Two separate, predeclared verdicts:

1. **H4 (over-conditioning power loss exists)**: Confirmed / Not
   confirmed / Inconclusive, per the Step 1 criterion above.
2. **H5 (saturates rather than climbs, matching D-069's own shape)**:
   Confirmed / Not confirmed / Inconclusive, per the Step 2 criterion
   above. Only meaningfully evaluated if H4 is confirmed -- if adding
   one decoy shows no effect at all, asking about the shape of a
   nonexistent effect is moot.

## Explicit non-goals

- **No claim about *why* a finite-sample power-loss effect would occur
  mechanistically** (e.g. the specific role of OLS residualization
  error at higher regressor counts) -- this charter tests *whether* the
  effect exists and *what shape* it takes, not its own root statistical
  cause. A follow-up theoretical or simulation-based charter could
  pursue that separately.
- **No claim that this fully explains D-072's own real-network
  finding.** Confirming H4/H5 in this controlled fixture would directly
  support, not prove, that the same mechanism is what happened in every
  one of D-072's own flagged real cases -- those involved specific,
  not-independently-verified conditioning variables (some may not be
  perfectly independent of each other or of the tested pair in a real
  screened component), unlike this charter's own provably independent
  decoys.
- **No production deployment or fix**, even if both H4 and H5 are
  confirmed. D-070's own recalibration mapping remains the deployed fix
  regardless of this charter's own result.
- **No re-litigation of D-069's, D-071's, or D-072's own findings** --
  all stand as recorded; this charter tests a hypothesis those findings
  motivated, in isolation.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the up-front
timing measurement and resulting replicate/shard decision, raw
per-replicate evidence for both steps (fixture, conditioning-set size,
`N`, `strength`, replicate, p-value, rejection outcome), the Step 1 and
Step 2 rejection-rate tables with Wilson CIs, both verdicts above, and
a report.

## Consequences

**If H4 and H5 both confirmed**: over-conditioning power loss is
established as a real, controlled-fixture-demonstrated mechanism that
reproduces both the existence and the specific saturating shape of
D-069's own real-network pattern -- the strongest candidate explanation
to date for the composed-tier false-edge reversal, superseding both the
true-collider (D-071) and pseudo-collider (D-072's own H3) hypotheses
in explanatory power. Motivates (as a separate, not-yet-chartered
future step) investigating the statistical root cause and whether a
correction (e.g. a stricter effective alpha at larger conditioning
sizes) could address it.

**If H4 confirmed but H5 is not (the effect keeps climbing rather than
saturating)**: over-conditioning power loss is real, but not, on its
own, a complete match for D-069's own observed shape -- some
additional, not-yet-identified factor would be needed to explain why
the real reversal stops worsening at `conditioning_size_used=2`.

**If H4 is not confirmed**: over-conditioning power loss, as tested
here, does not reproduce in a controlled fixture -- D-072's own
dominant Step 5 finding would remain real and reported, but its cause
would still be open, with the "provably irrelevant added variable"
explanation now eliminated (a useful, disclosed result) rather than
left as an untested leading candidate.
