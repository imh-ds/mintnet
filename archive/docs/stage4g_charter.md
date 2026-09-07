# Stage 4g Charter: Fitting an alpha(N) Rule for the Sequential Engine (Overlap Shape) (R6f)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-034 (Stage 4f) explained the candidacy-accuracy anomaly: a fixed
significance level is not a fixed burden of proof across `N` — the
observed `|r_partial|` needed to reach `alpha=.10` significance is
`.095` at `N=300` but only `.060` at `N=750`. Every overlap-shape result
collected so far under the sequential engine (Stage 4b/4d/4e) used a
fixed, `N`-independent `alpha`, and D-034's consequences withheld any
`N` recommendation until this is corrected. This charter builds that
correction, mirroring `docs/stage1j_charter.md`'s own fit-then-holdout-
validate methodology exactly — the same approach already used once, for
the conservative engine's `alpha(N)` formula (D-012).

**Scope, deliberately narrow, matching Stage 4e/4f:** overlap shape
only. Hub has no evidence yet that it needs this correction (D-034's
own consequences note its wide true/indirect signal separation makes
miscalibration unlikely to matter, though this charter does not
re-confirm that — a separate light check, not this one).

**What this charter reuses vs. what it simulates fresh.** Fitting data
comes entirely from Stage 4e's own already-generated raw evidence
(`results/generated/stage4e_candidacy_metric/raw_metrics.csv`,
development replicates only) — no new simulation for the six known `N`
points. Fresh simulation is needed only for the held-out interpolated
`N` values used to validate the fitted formula, exactly mirroring Stage
1j's own reuse-then-holdout structure.

## Fitting data (no new simulation)

For each of Stage 4e's six `N` values (`300, 500, 600, 650, 700, 750`),
using only development replicates (`0`-`999`) from Stage 4e's raw
evidence: compute pooled `conditional_accuracy` (D-033's own definition
— correctness among candidate cross-branch pairs only) for **every**
`alpha` in Stage 4e's original grid (`[.50, .30, .20, .10, .05, .01,
.005, .001, .0001]`), and select `alpha_star(N)` = the alpha that
**maximizes** `conditional_accuracy` subject to true-edge retention FPR
`<= .10`. This is a different selection rule than Stage 4b/4d/4e's own
"largest eligible above both margins" — that rule picks the most
permissive alpha clearing a floor, not the best-performing one, and is
not the right target for fitting a curve. This gives six `(N,
alpha_star)` fitting points; no simulation is run for this step.

## Held-out validation data (new simulation required)

**`N = [400, 550, 625, 675, 725]`** — five interpolated points strictly
between the six fitting `N` values, never simulated before at any Stage
4 charter. Identical overlap DGP and seed derivation to Stage 4b/4d/4e/
4f (`master_seed=20260830`, overlap's own shape index). 2,000 replicates
per held-out `N` (development 0-999, validation 1000-1999) — a
development/validation split is still needed here because, unlike the
fitting step, this data feeds a real PROCEED/REASSESS gate.

## Fitting procedure

Identical candidate forms and selection rule to `docs/stage1j_charter.md`:

1. Linear in `N`: `alpha = a + b*N`
2. Linear in `log(N)`: `alpha = a + b*ln(N)`
3. Power law: `alpha = a * N^b`
4. Inverse-sqrt: `alpha = a + b/sqrt(N)` (theoretically motivated — the
   underlying Fisher-z statistic scales with `sqrt(N-4)`)

Fit all four via least-squares regression on the six `(N, alpha_star)`
fitting points. Select the form with the highest R². If two or more
forms are within `.005` R² of the best, select inverse-sqrt if it is
among them; otherwise the simplest (fewest-parameter) form among the
near-tied set. This selection uses only the fitting data above and is
not itself gated.

## Selection and gate

For each held-out `N in [400, 550, 625, 675, 725]`, compute the single
predicted `alpha_hat = f(N)` — no grid search, exactly the value a
production rule would compute. Test `alpha_hat` directly against
validation replicates (`1000`-`1999`):

1. `conditional_accuracy >= .80` with margin `>= .02`.
2. True-edge retention FPR `<= .10` with margin `>= .02`.
3. Candidacy rate reported descriptively alongside (not gated), per
   Stage 4e's own established practice.

**PROCEED** only if `alpha_hat` clears both gated criteria with the
required margin at **every** held-out `N`, with no recorded error.
**REASSESS** otherwise, reporting exactly which held-out `N` failed and
by how much — mirroring Stage 1j's own reporting standard.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the six-point fitting table (`alpha_star` per `N`, and each
candidate form's R²), the selected formula and its parameters, raw
per-replicate evidence for the five held-out `N`, aggregate metrics,
the per-held-out-`N` decision table, a plot of the fitted curve overlaid
on all eleven points (six fitting, five held-out), and a report stating
plainly whether this recalibration changes the overlap shape's apparent
floor once `alpha` is no longer fixed across `N`.

## Consequences

If PROCEED: this becomes the sequential engine's candidate `alpha(N)`
rule for the overlap shape specifically, scoped to interpolation within
`[300, 750]` (no extrapolation claim outside this charter's fitting
range). **Only then** does it become meaningful to re-ask whether the
overlap shape's floor under the sequential engine sits below `N=750` —
this charter's own held-out cells, evaluated under a properly calibrated
`alpha` for the first time, are the first trustworthy answer to that
question at those specific `N` values. This still does not authorize
any user-facing recommendation — Stage 4c's cascading-error stress test
remains the unconditional precondition, per the R6a milestone in
`outline/information_network_technical_build_plan_v3_2026-08-30.md`.

If REASSESS: document which held-out `N` failed and by how much. This
would mean the six-point relationship does not generalize smoothly
between the tested points — a real, informative finding in its own
right (mirroring Stage 1j's own REASSESS branch), meaning a lookup
table, not a formula, remains the right artifact until a future charter
investigates why the interpolation fails.

Neither outcome retroactively validates or invalidates hub's Stage 4d
result, which this charter does not touch.
