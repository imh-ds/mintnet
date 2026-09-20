# Stage 6b Charter: Conditional-MI Estimator Validation — Bias, Variance, and Local-Permutation Type-I Error Control (mi-native)

Status: **FROZEN before results**
Date: 2026-09-02

## Background and objective

This is `mi-native`'s own Stage-0 equivalent — the prerequisite Stage
1b's own charter named explicitly: *"A separate charter to build and
validate a nonparametric conditional-MI estimator (with its own
Stage-0-style bias/variance evidence) remains a prerequisite before
that generalization is trusted for a gate."* No DPI, screening, or
retain/prune decision is tested here. This charter validates the
estimator and its significance test **in isolation**, against a known
analytic reference, exactly mirroring `docs/stage0_charter.md`'s own
structure for the bivariate case.

D-053 (Stage 6a) scoped what this estimator must support: most
decisions resolve at conditioning size `1`, but the composed networks
need `|S| >= 3` for a real minority of edges. This charter validates
across `|S| in {0, 1, 2, 3}` accordingly — `|S| = 0` is included
deliberately as a direct cross-check against the already-validated
bivariate KSG-1 estimator (D-001): conditional MI with an empty
conditioning set is mathematically identical to bivariate MI, so this
estimator's own `|S| = 0` output must agree with the existing
validated estimator, or something in the new implementation is wrong
before any conditional claim can be trusted at all.

## The estimator: CMIknn (Frenzel & Pompe, 2007)

Direct generalization of `mintnet.mi.ksg.estimate_ksg_mi`'s own
validated bivariate formula and counting convention (self-inclusive
neighbor counts via the epsilon-minus radius trick, Chebyshev/max-norm
distance, per-dimension standardization) — not a reimplementation from
a different convention. New module `mintnet.mi.cmiknn`:

1. Standardize each column of `(X, Y, Z)` independently.
2. Build a joint `cKDTree` over `(X, Y, Z)`; find each point's `k`-th
   nearest-neighbor distance (Chebyshev), then set `radius =
   nextafter(distance, 0.0)` (strictly smaller — the same open-ball
   trick the bivariate estimator already uses).
3. Count neighbors within `radius`, self-inclusive, in three marginal
   subspaces: `(X, Z)`, `(Y, Z)`, and `(Z)` alone (`Z` omitted
   entirely when `|S| = 0`, reducing exactly to the bivariate
   estimator's own `(X)`/`(Y)` counting).
4. `CMI_hat = psi(k) - mean(psi(n_xz) + psi(n_yz) - psi(n_z))` (`|S| =
   0`: `n_z` is undefined and the `n_z` term is dropped, reducing
   exactly to `mintnet.mi.ksg`'s own formula — verified by direct
   equality test, not just claimed).

`k = 20` as the starting default (D-001's own selected value) — this
charter's own development phase may re-select `k` for the conditional
case specifically, mirroring Stage 0's own development/validation
split, not assumed to transfer unchanged.

## The significance test: local permutation (Runge, 2018)

KSG-style CMI has no closed-form null distribution (this charter's own
reason for existing). Runge's local permutation scheme: to test
`X \perp Y | Z`, shuffle `Y`'s values only among each point's
`k_perm` nearest neighbors in `Z`-space (preserving the `X`-`Z` and
`Y`-`Z` marginal dependence structure while breaking only the direct
`X`-`Y` link), recompute `CMI_hat` on the shuffled data, repeat `B`
times to build an empirical null distribution, and compute a p-value
as the shuffled-null proportion exceeding the observed statistic.
`k_perm = 5` (Runge's own paper default) and `B = 199` (giving a
minimum resolvable p-value of `1/200`, adequate for this charter's own
`alpha in {.05, .01}` validation grid — **not** adequate for this
project's own eventual operational alphas as small as `.0001`; scaling
the permutation count or fitting a parametric tail to a smaller `B` is
explicitly deferred to a later charter, once this charter confirms the
basic mechanism is sound at all). For `|S| = 0` (no conditioning
variable), "nearest neighbors in `Z`-space" is undefined; use a
uniform (global) permutation instead — the ordinary, already-valid
permutation test for unconditional independence.

## Data-generating processes

**Gaussian reference (primary validation target, known closed-form
answer):** for jointly Gaussian `(X, Y, Z)` with `Z` a `|S|`-dimensional
conditioning set, `I(X;Y|Z) = -0.5 * ln(1 - r_{XY.Z}^2)`, the direct
generalization of Stage 0's own bivariate reference formula. DGPs:
reuse `mintnet.simulation.motifs.sample_chain`, `sample_measured_fork`,
`sample_hub`, `sample_precision_triangle`, and
`sample_overlapping_triangles` — every DGP already validated elsewhere
in this project, each supplying a known analytic conditional MI value
for at least one `(X, Y, Z)` triple at `|S| in {0, 1, 2, 3}` (the
overlapping-triangles fixture's own cross-triangle pairs, e.g.
`(0, 3) | {2}`, `(0, 3) | {1, 2, 4}`, supply the `|S| = 3` case).

`N = [300, 500, 750, 1500]` (Stage 0's own tested range, extended
toward this project's own typical operating floor), `500` replicates
per condition (Stage 0's own scale — this charter's compute cost per
replicate is substantially higher than Stage 0's, given `B = 199`
permutations per significance test; extending to this project's usual
`2,000` is deferred pending this charter's own runtime finding, not
assumed affordable).

## Selection and gate

Mirrors Stage 0's own structure exactly, generalized to the
conditional case. Development partition: replicates `0`-`249`.
Validation: `250`-`499`.

**Estimator accuracy (per `|S|`, development-selected `k`, tested on
validation):**
1. Absolute bias `<= 0.10` nats and RMSE `<= 0.20` nats at `N in [500,
   750, 1500]` (looser than Stage 0's own `0.05`/`0.10` bivariate
   bound — conditional estimation is harder, and this charter states
   that difference up front rather than reusing Stage 0's own bound
   and being surprised by a REASSESS).
2. Spearman correlation between estimated and analytic conditional MI
   across the tested DGP/`|S|` combinations `>= 0.85`.
3. `|S| = 0` cross-check: this estimator's own bivariate-equivalent
   output must match `mintnet.mi.ksg.estimate_ksg_mi`'s existing
   output within numerical tolerance (`1e-9`) on identical data — an
   exact-agreement check, not a bias/RMSE bound.

**Local-permutation test validity (per `|S|`, the charter's own
primary gate — an inaccurate but well-calibrated test is more useful
than an accurate but uncalibrated one, and this project's entire
downstream methodology depends on calibration, not point-estimate
accuracy):**
4. **Type-I error control**: under a constructed true null (`X \perp
   Y | Z` by DGP design — e.g. the chain's own `(X1, X3) | X2`), the
   rejection rate at nominal `alpha = .05` must fall in `[.03, .07]`,
   and at `alpha = .01` in `[.005, .015]`, at every tested `N` and
   `|S|`. **This is the one criterion that, if it fails, means the
   mechanism cannot be trusted at all regardless of every other
   result** — it is listed first among consequences below for that
   reason.
5. **Power**: under a constructed true alternative (a genuine direct
   edge, e.g. the chain's own `(X1, X2) | {}`, or the overlapping-
   triangles' own within-triangle pairs conditioned on the shared
   node), rejection rate at `alpha = .05` `>= .80` by `N = 1500`, at
   every tested `|S|`.

**PROCEED** only if every criterion holds at every tested `N` and
`|S|` on validation replicates. **REASSESS** otherwise, per this
project's own standing discipline — no partial credit, no averaging
across `|S|` or `N`.

## Explicit non-goals

- **No DPI, screening, or retain/prune decision.** This charter
  validates the estimator and test alone, exactly as Stage 0 validated
  KSG-1 alone before Stage 1 ever built DPI on top of it.
- **No nonlinear or non-Gaussian DGP.** Validating against a known
  closed-form reference requires a DGP where that reference exists;
  Gaussian is the only regime this project has one for. A nonlinear
  validation charter (where the actual claim "MI catches what
  correlation can't" gets tested) is separate future work, contingent
  on this charter's own PROCEED — an inaccurate or uncalibrated
  estimator is not worth testing on harder data first.
- **No re-derivation of `alpha(N)`-style thresholds for DPI.** This
  charter characterizes the test's own calibration at fixed literature
  `alpha` values; translating that into an `alpha(N)` formula for a
  future DPI mechanism is separate work, contingent on PROCEED here.
- **No small-alpha (`<.01`) validation.** `B = 199` permutations
  cannot resolve p-values that small; explicitly deferred.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (estimated CMI, analytic
reference, p-value, reject/retain decision per `alpha`), the
`|S| = 0` exact-agreement check's own result, aggregate bias/RMSE/
Type-I-error/power tables per `|S|` and `N`, decision, report, and
figures.

## Consequences

**If REASSESS on Type-I error control specifically**: the local-
permutation scheme itself needs revision (e.g. `k_perm` misspecified,
or the scheme's own validity assumptions do not hold as implemented)
before anything else in `mi-native` proceeds — this blocks the whole
track, not just this charter, since no downstream retain/prune
decision can be trusted on an uncalibrated test regardless of how
accurate the point estimate is.

**If REASSESS on bias/RMSE/power but Type-I error holds**: the
estimator is calibrated but underpowered or biased at the tested `N`
range — a narrower, more diagnosable problem (e.g. `k` needs
reselection, or `N` floor needs raising), not a fundamental validity
failure.

**If PROCEED**: `mi-native` may plan a Stage-1-equivalent charter
composing this estimator and test into a conditional-independence
retain/prune mechanism (mirroring `docs/stage1b_charter.md`'s own
next step after Stage 0), reusing Stage 6a's own growing-subset-DPI
architecture rather than full-component conditioning, per D-053. Does
not itself authorize any pipeline change.
