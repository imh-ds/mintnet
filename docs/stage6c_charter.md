# Stage 6c Charter: Local-Permutation Null Calibration — `k_perm` and `k_CMI` Sweep (mi-native)

Status: **FROZEN before results**
Date: 2026-09-02

## Background and objective

D-054 (Stage 6b, first pass) formally REASSESSed on the local-
permutation test's Type-I error gate, but the REASSESS was itself
inconclusive: exact binomial tests showed none of the out-of-band null
cells were statistically distinguishable from correctly calibrated,
at only 50 validation replicates per cell. That ambiguity is the
reason this charter exists — not to rerun the same design with more
replicates, but to investigate the actual object in question: **does
the local-permutation construction in `mintnet.mi.cmiknn._local_permutation`
adequately approximate the conditional-independence null**, and if so,
under what `k_perm` (and separately, `k_CMI`) regime?

This charter treats two tuning problems as genuinely separate, per
explicit user direction, and does not conflate them:

- **`k_CMI`** (the `k` in `estimate_cmiknn`): governs the point
  estimate's own bias/variance, exactly as `k` did for the bivariate
  KSG-1 estimator in Stage 0.
- **`k_perm`** (the neighborhood size in `_local_permutation`): governs
  how faithfully the empirical null distribution approximates the true
  conditional-independence null. This is a property of the
  *significance test*, not the estimator, and a well-chosen `k_CMI`
  does not imply a well-chosen `k_perm` or vice versa.

Framing note, stated explicitly per user instruction: this is a
**nonparametric, local-permutation-based** significance test. It is
**not** described as an exact "distribution-free" test in this
charter, because that label requires a finite-sample exchangeability
argument under `H0` that this charter has not established — local
permutation is an *approximation* to the true conditional null (exact
only in the limiting case where "nearest neighbors in `Z`" are truly
exchangeable given `Z`, which does not hold exactly at finite `N`).
Establishing whether that approximation is adequate, and where, is
this charter's entire purpose.

## Design

### Stage A — `k_CMI` sensitivity (point-estimate only, no permutation test)

Cheap (no permutation loop: ~0.01-0.03s per call, measured directly),
so affordable at high replicate counts. Fixes DGPs to the null
conditions defined below (true `I(X;Y|Z) = 0` or a known-small
analytic reference under Gaussian DGPs) and sweeps `k_CMI in {10, 20,
40}` across `N in {150, 300, 750, 1500}` and `|S| in {0, 1, 2, 3}`.
Reports bias/RMSE of the point estimate per cell. Purpose: confirm (or
correct) the Stage 6b default `k_CMI = 20` before it is held fixed
throughout Stage B — this charter does not want a miscalibrated
`k_perm` conclusion confounded by a poorly-chosen `k_CMI`.
`500` replicates per cell (cheap enough not to ration).

### Stage B — `k_perm` null calibration (the primary study)

**Restricted to true-null / conditional-independence conditions only**
(per explicit user direction — this charter is not trying to
characterize power yet). Fixes `k_CMI` to Stage A's winner. Sweeps:

- `k_perm in {3, 5, 10, 20, adaptive}`, where `adaptive = clip(round(0.05
  * N), 3, 20)` (`N=150 -> 8`, `N=300 -> 15`, `N=750 -> 20`) — a
  documented heuristic to test whether scaling the neighborhood with
  `N` helps or hurts, since Runge (2018)'s own default (`k_perm = 5`,
  used unchanged in Stage 6b) is a **fixed constant regardless of
  `N`**, and this charter explicitly wants to know whether that fixed
  choice is robust across this project's own `N` range or was merely
  inherited without re-justification. Not applicable at `|S| = 0`
  (global permutation, no neighborhood concept) — one cell per `N`
  there instead of five.
- `N in {150, 300, 750}` — `150` added beyond Stage 6b's own floor
  specifically to probe the user's own named concern, whether small
  `N` interacts with `k_perm` (a plausible failure mode: at small `N`,
  a fixed `k_perm` is a larger *fraction* of the available Z-neighborhood,
  which could bias the permutation toward being too global, or too few
  Z-neighbors may exist for the "leftover" fallback path in
  `_local_permutation` to trigger disproportionately often).
  `750` retained as the upper bound this pass can afford at the
  required replicate count (see runtime below); `1500` deferred, not
  silently dropped — an explicit non-goal below.
- `|S| in {0, 1, 2, 3}` — full range Stage 6a determined the pipeline
  must support (D-053).

Total null cells: `3 N * (1 + 3 |S| * 5 k_perm) = 3 * 16 = 48`.

DGPs (all already-validated fixtures, reused unchanged):
- `|S|=0`: `_sample_bivariate_independent` (Stage 6b's own condition).
- `|S|=1`: `sample_measured_fork`, testing the two non-adjacent
  children `(child1, child2) | center` — a genuine null by
  construction (conditional independence given the fork's center).
- `|S|=2`: `sample_hub` with 3 children, testing two non-adjacent
  children `(child_i, child_j) | {hub, child_k}`.
- `|S|=3`: `sample_overlapping_triangles`, testing the cross-triangle
  pair `(0, 3) | {1, 2, 4}` (Stage 6b's own `s3_null` condition,
  reused unchanged).

`permutations = 199` **is retained, but its adequacy for `alpha =
.01` is flagged explicitly here as a design constraint, not silently
accepted**: with `B = 199`, the minimum nonzero p-value is `1/200 =
.005`, meaning a rejection at `alpha = .01` requires the observed
statistic to exceed all but at most one of the 199 null draws — the
test has only two possible outcomes below `.01` (`p = 1/200` or `p =
2/200`). This is coarse but not fatal for *detecting* miscalibration
at `.01` (a systematically liberal test will still show an inflated
rate of `p <= .01` events even with this coarse resolution); it does
mean this charter's own `alpha = .01` estimates carry more inherent
quantization noise than `.05`'s, which the reporting must show via
confidence intervals rather than point estimates alone, per the gate
below.

`replicates = 400` per null cell (measured directly: ~1.15s/test at
N=150, ~3.5s/test at N=300, ~11.2s/test at N=750, roughly flat across
`k_perm` since neighborhood-matching cost is negligible next to the
199 `estimate_cmiknn` calls it drives — full 48-cell x 400-replicate
grid estimated at ~28 single-threaded hours, ~1.5-2 hours on this
machine's 20 logical cores via `ProcessPoolExecutor`). This is 8x
Stage 6b's first-pass replicate count and was sized specifically so
`alpha = .01` cells are estimable: at `n=400`, a true `.01` rate has
expected count `4` (vs. Stage 6b's `0.5` at `n=50`), and the reporting
below computes an exact Wilson-score confidence interval per cell
rather than asserting a bare pass/fail on the point estimate, so a
cell landing outside the strict band but with a CI overlapping the
nominal rate is reported as such, not silently rounded to "pass" or
"fail."

### Stage C — power at the calibrated setting (contingent, run last)

Only after Stage B identifies a defensible `(k_CMI, k_perm)` regime
(defined in the gate below). Reruns Stage 6b's own `_alt` conditions
(known true edges, same DGPs) at that regime, `N in {300, 750}`
(`150` excluded — underpowered by construction at any reasonable
`N` floor, not informative), `200` replicates per cell. Purpose:
confirm power is not lost at whatever `k_perm` the calibration study
prefers, not to re-litigate Stage 6b's own already-strong power
finding.

## Reporting requirements (every null cell)

- Nominal `alpha`.
- Rejections / total replicates.
- Empirical rejection rate.
- Wilson score 95% confidence interval around the rejection rate
  (`scipy`-computed, not a normal-approximation interval, which is
  unreliable near `p=0` or `p=1` — exactly the regime `alpha=.01`
  cells live in).
- Explicit pattern summaries across the swept dimensions: rejection
  rate as a function of `|S|` (pooled across `N`, `k_perm`), as a
  function of `N` within each `k_perm` (to surface small-N x `k_perm`
  interaction), and as a function of `k_perm` within each `|S|` (to
  surface whether calibration degrades as conditioning grows).

## Selection and gate

**A regime `(k_CMI, k_perm)` is "defensible" if, across every tested
`N in {150, 300, 750}` and `|S| in {0, 1, 2, 3}` cell using that
regime:**
1. The empirical rejection rate at `alpha=.05` falls in `[.03, .07]`
   **or** its Wilson 95% CI contains `.05`.
2. The empirical rejection rate at `alpha=.01` falls in `[.005, .015]`
   **or** its Wilson 95% CI contains `.01`.

This is a deliberate loosening of Stage 6b's own strict-band-only gate
(which produced an inconclusive REASSESS), replacing "point estimate
inside a fixed band" with "point estimate inside the band, or
statistically indistinguishable from nominal" — the exact distinction
D-054 had to establish post hoc via an unplanned binomial test is
built into this charter's gate up front instead.

**PROCEED** if at least one swept `k_perm` value (fixed or adaptive)
is defensible across the full `N x |S|` grid. The smallest such
`k_perm` is preferred as the operational default (smaller neighborhoods
cost less and stay closer to Runge's own local-permutation intent),
unless the pattern analysis shows a clear liberal/conservative trend
that argues otherwise, e.g. if only the adaptive rule is defensible
because a fixed constant fails at large `N`.

**REASSESS** if no swept `k_perm` value is defensible everywhere. In
that case the pattern analysis (does miscalibration concentrate at
specific `N`, `|S|`, or `k_perm` regions) determines next steps —
e.g. a `k_perm`-vs-`|S|` interaction would suggest the neighborhood
size should itself depend on conditioning dimension, not just `N`,
which this charter's swept grid does not yet test and would become a
named follow-up, not something decided ad hoc here.

**Stage C (power) is reported regardless of the Stage B verdict**, but
is only load-bearing for the overall decision if Stage B reaches
PROCEED — power at an uncalibrated test's chosen settings is not
meaningful, per Stage 6b's own precedent (Type-I error is gate-
determining; power is diagnostic).

## Explicit non-goals

- **No `N = 1500`.** Deferred pending this pass's own runtime
  finding, exactly as Stage 6b deferred it — not assumed affordable at
  the increased replicate count this charter requires.
- **No composition into DPI.** Same boundary as Stage 6b: this
  charter characterizes the significance test in isolation.
- **No `k_perm`-by-`|S|` joint neighborhood rule.** The adaptive rule
  tested here scales with `N` only; a rule that also scales with `|S|`
  is explicitly out of scope unless Stage B's own pattern analysis
  motivates it as a named follow-up.
- **No resolution of `alpha < .01`.** `B = 199` cannot resolve it;
  unchanged from Stage 6b's own deferral.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (Stage A: estimate + analytic
reference per cell; Stage B: estimate, p-value, reject/retain decision
per `alpha`, per cell; Stage C: same as Stage B for `_alt` conditions),
per-cell Wilson CI tables, pattern-analysis tables/figures, decision,
report.

## Consequences

**If Stage B PROCEEDs**: `mi-native` adopts the selected `(k_CMI,
k_perm)` regime as its operational default and may plan the Stage-1-
equivalent composition charter that D-053/Stage 6b's own "Consequences"
section already named as the next step, now with a null-calibrated
test to build on.

**If Stage B REASSESSes**: the local-permutation construction itself
needs revision (not just parameter retuning within the current
construction) before `mi-native` can proceed past the estimator-
validation layer — this charter's own pattern analysis is the required
input to that revision, not a signal to keep sweeping ad hoc.
