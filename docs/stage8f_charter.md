# Stage 8f Charter: Collider-Conditioning-Bias Diagnostic (main)

Status: **FROZEN before results**
Date: 2026-09-07

## Background and objective

D-069 (Stage 8d) identified the composed-tier false-edge margin
reversal's own precise trigger condition — `conditioning_size_used >= 2`
— but explicitly left its causal mechanism unconfirmed, naming
**collider-conditioning bias** as the leading candidate: conditioning
on a variable that is a common effect (collider) of two otherwise
unrelated variables induces spurious statistical dependence between
them (the classical "explaining away" effect). D-070 (Stage 8e) then
validated a practical recalibration fix for the symptom, deliberately
without resolving this question — D-069's own text names it as the
remaining open option (a).

**This charter tests the collider-conditioning-bias hypothesis
directly**, on a minimal, isolated synthetic fixture where the causal
structure is fully known and controllable — not by re-examining the
composed `p=15` networks, whose own screened conditioning subsets are
data-dependent and not enumerable from a known ground-truth DAG without
a separate, heavier structural-audit effort explicitly out of scope
here (see Non-goals).

**Why this is testable in closed form.** `compute_partial_correlation_
evidence` (`mintnet.dpi.multi_conditional`) is a linear, Gaussian
Fisher-z partial-correlation test. For jointly Gaussian `X`, `Z`
(independent, correlation `0`) and a collider `Y = a*X + b*Z + noise`,
the conditional correlation `Corr(X, Z | Y)` has a known closed form:

```
rho(X,Z|Y) = -rho(X,Y) * rho(Z,Y) / sqrt((1 - rho(X,Y)^2)(1 - rho(Z,Y)^2))
```

This is **exactly zero only when `a=0` or `b=0`** (i.e., only when `Y`
is not actually a collider of both) — for any `a,b != 0`, conditioning
on `Y` induces a real, nonzero linear correlation between `X` and `Z`
that the project's own Fisher-z test is designed to detect. This is not
a numerical-instability or small-sample artifact; it is the textbook
collider effect, expressible in exactly the linear-Gaussian setting
this project's own partial-correlation mechanism already assumes and
tests. This charter measures how strongly it manifests in
`growing_subset_dpi`'s own actual OR-rule search, not just in the
closed-form formula.

## Mechanism

**Step 1 -- H1 (existence): does conditioning on an isolated collider
alone induce spurious rejection of independence?**

New minimal fixture, `sample_collider(n, strength, rng)` (added to
`mintnet.simulation.motifs`, alongside `sample_chain`/
`sample_measured_fork`/`sample_hub` as a plain three-column Gaussian
motif, not part of any existing composed network): `X`, `Z` drawn
independently (`Corr(X,Z) = 0` by construction), `Y = strength*X +
strength*Z + sqrt(1 - 2*strength^2)*noise` (unit-variance Y for
`strength < 1/sqrt(2)`, matching this project's existing
`sqrt(1 - strength^2)` motif convention). `X-Z` is a **known-false**
edge (no true edge, and genuinely marginally independent -- ground
truth is not merely "no direct edge" as in a chain, but literal
statistical independence).

For each of the project's own already-validated `N in {300, 500, 750,
1000, 1500, 3000}` and a small grid of `strength in {0.3, 0.5, 0.6}`
(bounded below `1/sqrt(2) ~ 0.707`), run `compute_partial_correlation_
evidence(data, i_X, i_Z, (i_Y,))` directly (one conditioning variable,
the collider itself -- this is a controlled significance-test
calibration check, not a full `growing_subset_dpi` component search,
since the pool here has exactly one candidate) across `R=2000`
replicates per cell. **H1 confirmed** if the empirical rejection rate
(`p <= alpha(N)`, D-012's existing formula) is materially and
consistently above the nominal rate a true-independence test should
show (i.e., materially above `alpha(N)` itself, with a non-overlapping
Wilson 95% CI) at every tested `(N, strength)` cell.

**Step 2 -- H2 (collider-specific, not conditioning-size-generic): is
the elevated bias attributable to the collider structure, or would any
second conditioning variable have the same effect?**

D-069's own empirical pattern needs more than "conditioning on a
collider is biased" -- it specifically found `size=1` clean but
`size=2` broken in the real composed networks. A competing, non-
collider explanation for that pattern is available and must be ruled
out before crediting collider bias specifically: **degrees-of-freedom
loss alone** (Fisher-z's variance grows with `1/(N - 3 -
|conditioning|)`; a larger conditioning set is a noisier test in
general, for any conditioning content, collider or not) could also
produce a size-graded increase in false rejections.

Extend the Step 1 fixture to four columns: `X`, `Z` (the same false
edge), `Y` (the collider, as above), and `W` -- an independent decoy
variable with **no causal relationship to `X`, `Y`, or `Z` at all**
(`W ~ N(0,1)`, drawn independently). Run `growing_subset_dpi`'s own OR-
rule search directly on this 4-node fixture for the `(X, Z)` pair, pool
`{Y, W}`, at the same `N`/`strength` grid as Step 1, `max_conditioning_
size=2`, comparing two conditions at matched conditioning-set size `2`:

- **Collider condition**: `{Y, W}` jointly (the size-2 subset the OR-
  rule actually tests once size `1` fails to prune) -- includes the
  collider.
- **Size-matched non-collider control**: an otherwise-identical 4-node
  fixture where `Y` is replaced by a second independent decoy `V` (no
  causal link to `X` or `Z`), so the size-2 conditioning set `{V, W}`
  has the same dimensionality but no collider present at all.

**H2 confirmed** if the collider condition's own empirical false-
rejection rate at `conditioning_size_used=2` is materially higher
(non-overlapping Wilson CI) than the size-matched non-collider
control's own rate, at every tested `(N, strength)` cell -- isolating
the effect to the collider's presence, not merely to using two
conditioning variables. **H2 not confirmed** (or "attenuates to a
generic size effect") if the two conditions show statistically
indistinguishable false-rejection rates -- in that case, D-069's own
graded pattern would be better explained by generic degrees-of-freedom
loss at larger conditioning sizes, not specifically by collider
structure, and the "collider-conditioning bias" label from D-069 would
need to be retracted or narrowed.

## Data-generating processes

`sample_collider` (new, Step 1) and its four-column extension with a
`W` decoy and, for the control, a `V` decoy in place of `Y` (Step 2) --
both newly introduced by this charter, not reused from any existing
motif or composed-network module. `N in {300, 500, 750, 1000, 1500,
3000}` (this project's own shared, previously-validated regime,
unchanged). `strength in {0.3, 0.5, 0.6}` for the collider's own
loading onto `X`/`Z`. `alpha(N)`: D-012's existing formula, unmodified.
`R=2000` replicates per cell, matching Stage 8a's own precedent.

## Compute-cost disclosure

Both steps use the same closed-form, non-permutation Fisher-z test
Stage 8a already measured as cheap at this replicate count and N range
-- no new mechanism, only new (and smaller, 3-4 column) fixtures. Per
this project's own standing discipline: **measure real wall-clock cost
of the full sweep (both steps, all cells) before finalizing shard plan**
-- not assumed cheap from Stage 8a's own precedent alone.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** --
unchanged, hard requirement, per this project's established practice.

## Selection and gate

Diagnostic charter -- no PROCEED/REASSESS gate on the whole (mirrors
Stage 8d's own precedent). Two separate, predeclared verdicts:

1. **H1 (collider bias exists)**: Confirmed / Not confirmed, per the
   Step 1 criterion above.
2. **H2 (collider-specific, not size-generic)**: Confirmed / Not
   confirmed / Attenuates to a generic size effect, per the Step 2
   criterion above. Only meaningfully evaluated if H1 is confirmed --
   if collider conditioning shows no bias at all in isolation, asking
   whether it is "size-specific" is moot.

## Explicit non-goals

- **No claim that this fully explains D-069's own real-network
  pattern.** This charter tests whether the collider mechanism is
  *real and detectable* in a controlled, known-truth setting, and
  whether it is specifically collider-driven rather than a generic
  size effect. It does **not** attempt to prove that collider structure
  is what actually occurs inside `chain_fork_hub`'s or `overlap`'s own
  screened conditioning subsets -- that would require a structural
  audit of which specific screened candidates are colliders relative to
  each false edge's own position in the known DAG, a separate, heavier
  effort not undertaken here.
- **No production deployment or fix.** Even a fully confirmed H1+H2
  does not by itself change `growing_subset_dpi`'s own search logic or
  supersede D-070's own deployed recalibration mapping -- that decision,
  if ever made, belongs to a future charter.
- **No nonlinear or non-Gaussian collider claim.** The closed-form
  argument above is specific to linear-Gaussian structure, matching
  this project's own partial-correlation mechanism; no claim is made
  about collider bias under CMIknn or structured-density's own
  (nonparametric) independence tests.
- **No re-litigation of D-069's own H1/H2 (cap-reached /
  conditioning-size-graded) findings** -- those remain as recorded;
  this charter investigates the *cause* of the size-graded pattern
  D-069 already established, not whether that pattern exists.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the up-front
timing measurement and resulting replicate/shard decision, raw
per-replicate evidence for both steps (fixture, `N`, `strength`,
replicate, conditioning set, p-value, rejection outcome), the Step 1
and Step 2 rejection-rate tables with Wilson CIs, the two verdicts
above, and a report.

## Consequences

**If H1 and H2 both confirmed**: collider-conditioning bias is
established as a real, controlled-fixture-demonstrated mechanism
specific to conditioning-set structure rather than size alone --
directly supports D-069's own leading hypothesis and motivates (as a
separate, not-yet-chartered future step) a structural audit of the
real composed networks' own false edges to check whether their
screened conditioning subsets actually contain collider relationships
relative to the DAG.

**If H1 confirmed but H2 is not (attenuates to a generic size
effect)**: the reversal's cause is better attributed to general
degrees-of-freedom loss at larger conditioning sizes than to collider
structure specifically -- D-069's own "plausibly collider-conditioning"
language should be revised to name the more general mechanism, and any
future candidate fix (e.g., a conditioning-size-aware significance
correction) should target that broader cause instead.

**If H1 is not confirmed**: the isolated collider mechanism does not
produce the kind of bias this project's own Fisher-z test would detect
under these conditions -- the composed-tier reversal's cause remains
open, and the "collider-conditioning" hypothesis named in D-069 should
be marked eliminated (a useful, disclosed result) rather than
re-attempted without a materially different fixture design.
