# Stage 1j Charter: Fitting and Validating an alpha(N) Default Rule (R2j)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

Six sample sizes now have a validated working alpha pair
(`docs/decision_log.md` D-008 through D-010): `N=700` and `N=750` both
select `(0.14, 0.16)`; `N=1000` selects `(0.12, 0.14)`; `N=1500` selects
`(0.10, 0.12)`; `N=2000` selects `(0.08, 0.10)`; `N=3000` selects
`(0.06, 0.08)`. This is a clean, monotonically decreasing relationship,
but it remains a lookup table, not a rule the production method could
compute automatically from a dataset's sample size.

This charter fits a smooth, parsimonious `alpha(N)` formula from this
table and, critically, **validates it on sample sizes not used to fit
it** — interpolated `N` values between the six known points — rather than
declaring success from curve-fit quality alone. This is required input
for a future default-alpha mechanism, not that mechanism itself: this
charter does not select a public production default, and does not
authorize Stage 2 work.

## Data

**Fitting data** (no new simulation): the six `(N, alpha)` points above,
using each pair's midpoint as the fitted value (`N=700, 750`: `0.15`;
`N=1000`: `0.13`; `N=1500`: `0.11`; `N=2000`: `0.09`; `N=3000`: `0.07`).
`N <= 650` is excluded from fitting — those `N` have no valid alpha, and
the formula must not be extrapolated below the validated floor regardless
of what it predicts there (see Consequences).

**Validation data** (new simulation required): four held-out,
interpolated sample sizes never tested before: `N = [900, 1250, 1750,
2500]`. These sit strictly between fitted points, testing interpolation
specifically — extrapolation beyond `N=3000` or below `N=700` is out of
scope for this charter.

DGP unchanged from every prior Stage 1 charter: `balanced`/`moderate`/
`strong` triangle fixtures, chain, measured fork, strengths `a = b =
[.3, .5, .7]`, master seed `20260829`, 2000 replicates (development
0-999, validation 1000-1999).

## Mechanism

Unchanged: per-edge Fisher-z partial-correlation test.

## Fitting procedure

Fit four predeclared candidate forms to the six fitting points via
least-squares regression on `alpha` against `N`:

1. Linear in `N`: `alpha = a + b*N`
2. Linear in `log(N)`: `alpha = a + b*ln(N)`
3. Power law: `alpha = a * N^b`
4. Inverse-sqrt: `alpha = a + b/sqrt(N)` — theoretically motivated, since
   the mechanism's own Fisher-z statistic scales with `sqrt(N-4)`
   (`docs/stage1b_charter.md`)

Select the form with the highest R² on the six fitting points. If two or
more forms are within `0.005` R² of the best, select the inverse-sqrt
form if it is among them (theoretical motivation as a tiebreaker over a
negligible empirical difference); otherwise select the simplest
(fewest-parameter) form among the near-tied set.

This selection is itself deterministic and reproducible from the six
fitting points — it does not require simulation and is not the gated
step. The gate is the held-out validation below.

## Selection and gate

For each held-out `N in [900, 1250, 1750, 2500]`, compute the single
predicted `alpha_hat = f(N)` from the selected formula — no grid search,
exactly the value a production method would compute. Test `alpha_hat`
directly (not a pair) against validation replicates (1000-1999): for
every strength (all three triangle families), chain/fork TPR `>= .80`
and triangle FPR `<= .10`, with a required margin of at least `.02` on
each criterion (a "comfortable, not thin" bar, consistent with D-011's
established default standard — a formula whose predictions are
themselves thin-margin should not become the recommended rule).

**PROCEED** only if `alpha_hat` clears this bar with the required margin
at every held-out `N`. **REASSESS** otherwise, reporting exactly which
held-out `N` failed and by how much.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the fitting procedure's R² for all four candidate forms and the
selected formula's parameters, raw per-replicate evidence for the four
held-out `N`, aggregate metrics, the per-held-out-N decision table,
report, and figures (including the fitted curve overlaid on all ten
points — six fitting, four held-out).

## Consequences

If PROCEED: the fitted formula becomes a candidate default `alpha(N)`
rule, explicitly scoped to `N >= 700` (never extrapolate below the
established floor) and to interpolation within `[700, 3000]`
(extrapolation beyond `3000` untested and unclaimed). This is still not a
public production default by itself — adopting it as one is a separate,
later decision — but it closes the loose end from D-009's consequences.

If REASSESS: document which held-out `N` failed. A formula that fits the
six known points well but fails to generalize between them would be a
genuine, informative finding — it would mean the true relationship is not
smooth in the tested functional sense, and the lookup table (not a
formula) remains the right artifact to carry forward until a future
charter investigates why.
