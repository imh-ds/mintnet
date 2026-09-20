# Stage 7d Charter: Structured Conditional-Density MI/CMI Estimator (mi-native)

Status: **FROZEN before results**
Date: 2026-09-05

## Background and objective

Stage 7c (D-061) closed the `k_CMI`-retuning question: a real,
calibrated gain was found (`k_CMI=80`), but it narrows rather than
closes the original hard-case gap, and the charter's own consequences
section named the remaining levers as separate, larger work —
"a different estimator entirely" among them, not a further parameter
nudge.

Separately, a side discussion this session quantified *why* CMIknn
pays the sample-efficiency cost it does on the Gaussian-linear
fixtures this project has tested throughout: a fully nonparametric,
density-free kNN estimator cannot exploit the fact that the true
relationship is linear, and pays for that generality in variance and
convergence rate, worsened by conditioning dimensionality. A classical
parametric partial-correlation test, by contrast, is efficient
*because* it assumes the correct shape on this specific test bed.

**This charter tests a middle path**: replace CMIknn's fully generic,
density-free estimation of `p(x,y,z)` with a **structured, low-
complexity conditional-density model** (regularized splines / low-
degree polynomial bases / strongly shrunk smoothers) that can
represent linear, mildly curved, U-shaped, inverted-U, and saturating
relationships, but is deliberately *not* an unrestricted smoother. MI
and CMI are then computed as differences of fitted, cross-fitted log
predictive densities — not as regression-coefficient or spline-term
significance — preserving MI/CMI as the network edge quantity
throughout. The goal is to determine whether this buys back sample
efficiency on the effect sizes and sample sizes this project actually
cares about, while still catching genuine nonlinear dependence that a
linear test would miss outright.

**This is a new estimation mechanism, not a retuned CMIknn parameter**
— it gets its own charter, its own calibration, and its own
falsification attempt, exactly as CMIknn itself did (D-053 through
D-057) before being trusted for any composition.

## Design

### Estimator specification

**Marginal case** (`I(X;Y)`): fit a conditional-density model
`p(Y|X)` using a constrained basis (candidates: natural cubic splines
with a small, fixed maximum degrees of freedom; low-degree orthogonal
polynomials; a strongly-regularized GAM-style smoother). Fit the
*mean* via the basis and the *residual distribution* explicitly
(homoscedastic Gaussian residual with fitted or estimated variance, at
minimum — heteroscedastic extensions are an explicit non-goal below).
Combine with an estimate of the marginal `p(Y)` (fit via the same
constrained family, or a simple parametric marginal — resolved during
implementation, disclosed in the report either way) and compute:

```
I(X;Y) = E[ log p(Y|X) - log p(Y) ]
```

**Conditional case** (`I(X;Y|Z)`): fit two models in the same
constrained family —

```
M0: p(Y|Z)
M1: p(Y|X,Z)
```

and compute:

```
I(X;Y|Z) = E[ log p(Y|X,Z) - log p(Y|Z) ]
```

**Cross-fitting is mandatory, not optional.** Both expectations above
are estimated out-of-sample (K-fold cross-fitted log predictive
density, K resolved during implementation and disclosed) specifically
to prevent overfitting bias from inflating MI/CMI — a plug-in
estimator that evaluates its own fit on its own training data would
systematically overstate dependence, especially at the small `N` this
project's own accessibility question is about.

**The edge/test quantity remains MI or CMI in nats**, exactly as
CMIknn's output is used today. Regression-coefficient significance,
spline-term significance, or model `R^2` are explicitly **not** the
reported quantity at any point in this pipeline — this mirrors this
project's own standing MI-vs-beta-coefficient distinction, not a new
rule invented for this charter.

**No derived deterministic features** (e.g. adding `X^2` as an input
alongside `X`) are added to any nonparametric density estimator as a
substitute for this charter's own approach — a deterministic
transform of `X` contains no information beyond `X` and only adds
embedding dimensionality without changing population MI. Structural
assumptions enter exclusively through the conditional-density model's
own functional form and regularization, per the design above.

**Complexity is a calibrated parameter, not a hand-picked default.**
The function class's own complexity (basis dimension / degrees of
freedom / regularization strength) is swept, not assumed, using the
same two-stage discipline as Stage 7c: a calibration filter first
(Type-I error must hold under the null before any power claim is
trusted), then a frontier comparison among calibrated survivors only.
This directly addresses the risk, raised before this charter was
written, that hand-tuning complexity against only the fixtures already
in hand would silently reconstruct something close to a linear model
and pass its own benchmark by construction.

### DGPs — genuine curvature is mandatory, not optional

Unlike every prior mi-native charter, this one is explicitly
**disqualified from a meaningful conclusion if it tests only
Gaussian-linear fixtures** — a structured estimator that improves
efficiency only by degenerating into a linear model would look
identical to a real win on this project's existing benchmarks alone.
Required conditions, at minimum:

- **Null independence** — reuses the existing `weak_edge_triangle`
  in-family null (`target_rho=0`), for direct calibration comparability
  with D-056/Stage 7c.
- **Linear effects across a range of partial correlations** — reuses
  `sample_weak_edge_triangle` at `target_rho` values spanning D-060's
  own mapped frontier and the still-unresolved hard case: at minimum
  `{0.08, 0.12, 0.15, 0.20}`.
- **Mild monotonic curvature** — a new fixture, a monotonic but
  non-linear transform of an otherwise-equivalent relationship (e.g. a
  saturating/soft-threshold link) at a matched population-MI level to
  the linear cases above, so results are comparable on the same
  dependence-strength footing, not just the same correlation
  coefficient (which is not comparable once the relationship is
  nonlinear).
- **U-shaped and inverted-U effects** — a new fixture with a
  quadratic-in-mean relationship and **zero linear correlation by
  construction** (symmetric U/inverted-U around the conditioning
  variable's mean) — this is the single most diagnostic condition:
  a structured estimator that has quietly collapsed to a linear model
  will show *zero* power here regardless of effect size, while CMIknn
  and a correctly-implemented structured model should both detect it.
- **Several `N` matching this project's own empirical range** — reuse
  `{750, 1500, 3000}` for direct comparability with D-060/D-061;
  optionally a smaller value (e.g. `500`) if this charter's own
  results suggest the accessibility question is now live at smaller
  `N` than previously testable — resolved during implementation, not
  required up front.

New fixtures required for the curvature/U-shape conditions are
implemented as new functions in `mintnet.simulation.motifs` (or a new
module if warranted), each with its own unit test establishing the
claimed population relationship, following the same pattern as
`sample_weak_edge_triangle`'s own recovery test.

### Comparison baseline

The existing CMIknn estimator at its current best-known calibrated
setting (`k_CMI=80`, `k_perm=3`, `permutations=199`, per D-061) is run
against the **same** DGPs, same `N` grid, same alpha grid — not a
different historical run reused from a different fixture family. This
charter measures a head-to-head comparison on data neither estimator
has seen before, not a comparison against a different charter's own
numbers.

### Metrics, per condition

Bias of the MI/CMI point estimate against the DGP's own known
population MI (computable in closed form for the linear and — with
some derivation work, disclosed if not tractable — the curvature
fixtures), variance of the estimate across replicates, Type-I error at
the null, power across the swept effect-size/complexity grid, and the
resulting detection limit (same `operating_frontier`-style definition
as D-060, reused where the schema allows).

## Compute-cost disclosure

Per this project's own standing discipline: before finalizing
`batch_size`/shard count, measure real per-replicate cost directly —
this estimator's cost profile is not assumed to resemble CMIknn's
(cross-fitted density-model fitting has a fundamentally different cost
structure than kNN queries; likely cheaper per replicate but with
different scaling in `N` and in the swept complexity parameter). No
shard plan is finalized in this charter; it is deferred to the
implementation phase's own up-front timing measurement, exactly as
every prior mi-native evidence run has done.

## Explicit non-goals

- **No heteroscedastic residual modeling.** Homoscedastic Gaussian
  residuals (or the simplest tractable alternative) are used
  throughout; modeling how residual variance itself depends on
  covariates is separate future work if this charter's own results
  motivate it.
- **No interaction/multivariate basis search.** The constrained
  function class targets single-predictor and pairwise-conditioning
  shapes matching this project's own 3-node motifs; a general
  multivariate structured-density search is out of scope.
- **No composition into DPI.** Purely an estimator characterization,
  like Stage 6c/6d/7b/7c before it — a passing result here motivates a
  future composition charter, it does not itself change the pipeline.
- **No abandonment of CMIknn.** This charter tests a candidate
  replacement; CMIknn remains the validated default
  (`k_CMI=80`/`k_perm=3`, per D-061) unless and until this charter's
  own results, plus a subsequent composition charter, justify a
  change.
- **No claim about non-Gaussian/heavy-tailed marginals.** Fixtures
  here remain Gaussian-marginal with the mean relationship varied —
  matching this project's own tested scope throughout; robustness to
  non-Gaussian marginals is a separate, larger question.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the up-front timing measurement and its resulting batch-size
decision, new fixture implementations with their own unit tests, raw
per-replicate evidence for both estimators across every DGP/`N`/
complexity-setting combination, the Stage-A-style calibration-filter
table (per complexity setting, per `N`), the calibrated-survivor
comparison table against the CMIknn baseline (bias, variance, Type-I
error, power, detection limit — not a single summary number), and a
report that states plainly whether the U-shaped/inverted-U condition
was detected by the structured estimator at a rate distinguishable
from CMIknn's own — the single result this charter cannot skip without
undermining its own conclusion.

## Consequences

**If a calibrated structured setting improves the detection limit on
linear/mild-curvature effects at matched `N`, while retaining
meaningful power on the U-shaped/inverted-U condition** (not
necessarily equal to CMIknn's, but clearly non-zero and
distinguishable from a linear-collapsed model's expected null result
there): this becomes a genuine candidate replacement, worth a follow-
up composition charter — the first real alternative-estimator result
in this project's own history, not a parameter nudge.

**If the structured estimator improves linear-case efficiency but
collapses to near-zero power on the U-shaped/inverted-U condition**:
report this plainly as evidence the gain was bought by discarding
MI's own core value proposition, not a usable result — the
"reinventing a linear test with extra steps" failure mode named before
this charter was written, now checked directly rather than assumed
absent.

**If no calibrated structured setting improves on CMIknn's own
`k_CMI=80` frontier anywhere tested**: CMIknn's existing calibrated
default stands, and this specific structured-density approach is
recorded as tried and not beneficial — the remaining levers named in
D-061's own consequences section (more permutations, RCoT, a copula-
transform preprocessing step) remain the live candidates for any
future accessibility work.
