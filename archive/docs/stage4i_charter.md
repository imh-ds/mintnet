# Stage 4i Charter: Repairing the alpha(N) Formula's N=750 Boundary Gap (R6i)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

D-037 (Stage 4h) found that Stage 4g's fitted `inverse_sqrt` `alpha(N)`
formula predicts a **negative** alpha (`-.0044`) exactly at `N=750`,
causing every Stage 4h replicate at that `N` to error before producing
any evidence. The root cause: `N=750` was one of Stage 4g's six
**fitting** points (`docs/stage4g_charter.md`'s fitting data, reused
verbatim from Stage 4e), never one of its five **held-out validation**
points (`400, 550, 625, 675, 725`). Stage 4g's validation procedure
never checked that the fitted curve returns a valid probability at its
own fitting points — only that it does so at points strictly between
them. This left a silent, boundary-shaped gap inside a formula whose
own charter claimed validity across the entire `[300, 750]` range.

**Objective:** repair this specific gap with the smallest change that
fully closes it, re-establish a trustworthy `alpha(N)` value at
`N=750`, and use it to finally complete the direct `N=750` comparison
against D-018 that Stage 4h's charter was built around but could not
make.

**Scope, deliberately narrow:** this charter touches only the overlap
shape's `alpha(N)` formula and its behavior at `N=750`. It does not
revisit Stage 4g's `[400, 550, 625, 675, 725]` held-out results (still
valid and unchanged), Stage 4h's `N=625`/`700` results (still valid and
unchanged, per D-037), or any other shape.

## Diagnosis this charter is built on (already established, not re-tested)

Directly inspecting the selected `inverse_sqrt` form (`alpha = a +
b/sqrt(N)`) across `N=[300..750]` (done during Stage 4h's investigation,
reused here as background, not re-derived): the curve is positive and
shrinking through `N=725` (`.0015`) and crosses zero between `N=725` and
`N=750`, landing negative at `N=750` itself. This is a property of
*where the six fitting points place the regression line*, not a
property of `N=750`'s underlying data (no data was ever fit or
evaluated at `N=750` under this lens — it was only ever a lookup value
taken directly from Stage 4e's own raw evidence, never itself run
through a held-out validation gate).

## Repair procedure

**Re-fit with `N=750` moved from the fitting set to the validation
set.**

1. **Revised fitting points (five, not six):** `N = [300, 500, 600, 650,
   700]`, using the exact same selection rule as
   `docs/stage4g_charter.md` (`compute_fitting_points`: alpha
   maximizing `conditional_accuracy` on Stage 4e's development
   replicates, subject to true-edge FPR `<= .10` and candidacy rate
   `>= .80`) and the exact same source data
   (`results/generated/stage4e_candidacy_metric/raw_metrics.csv`, no
   new simulation for this step). `N=750`'s fitting point (`alpha=.005`,
   per Stage 4g's own table) is dropped from the fitting set entirely.

2. **Revised held-out validation points (six, not five):** Stage 4g's
   original five (`400, 550, 625, 675, 725`) plus `750` itself, now
   validated for the first time as a genuine held-out point rather than
   assumed-safe as a fitting point. `N=750` requires **fresh
   simulation** (2,000 replicates, development `0`-`999` / validation
   `1000`-`1999`), identical overlap DGP and seed derivation to
   Stage 4b/4d/4e/4f/4g (`master_seed=20260830`, overlap's own shape
   index) — this is new data Stage 4g never generated at `N=750` under
   this procedure, even though `N=750` evidence already exists from
   Stage 4b/4d/4e for *other* purposes. The other five held-out `N`
   reuse Stage 4g's own already-generated evidence verbatim (no
   re-simulation) exactly as Stage 4g reused Stage 4e's.

3. **Fitting.** Identical candidate forms and selection rule to Stage
   4g: linear in `N`, linear in `log(N)`, power law, inverse-sqrt; R²
   selection with the inverse-sqrt tiebreak preference from
   `docs/stage1j_charter.md`.

4. **New self-check (the correction this charter exists to add):**
   before any gate is evaluated, compute the refit formula's predicted
   `alpha` at **every one of its own five fitting `N` values**, and
   confirm each is a valid probability, `0 < alpha_hat < 1`. This check
   did not exist in Stage 4g and is the specific safeguard against a
   repeat of this exact failure mode. Record the result (pass/fail per
   fitting point) in the evidence regardless of outcome.

## Gate

For each of the six held-out `N` (`400, 550, 625, 675, 725, 750`),
compute the single predicted `alpha_hat = f(N)` — no grid search — and
test it against that `N`'s validation replicates (`1000`-`1999`):

1. `conditional_accuracy >= .80` with margin `>= .02`.
2. True-edge retention FPR `<= .10` with margin `>= .02`.
3. `alpha_hat` itself must be a valid probability, `0 < alpha_hat <
   1` — a held-out `N` where the formula produces an out-of-range value
   is an automatic failure of that `N`, reported explicitly rather than
   erroring silently (Stage 4h's error-status handling is reused for
   this, not re-implemented).
4. Candidacy rate reported descriptively alongside (not gated), per
   established practice.

**PROCEED** only if `alpha_hat` clears all three gated criteria at
**every** held-out `N`, including `750`, with no recorded error and no
fitting-point self-check failure. **REASSESS** otherwise, reporting
exactly which `N` failed, on which criterion, and by how much.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the Stage 4e raw-evidence SHA-256 (reused fitting data), the
Stage 4g raw-evidence SHA-256 (reused held-out data for the five
non-750 points), the five-point fitting table and each candidate form's
R², the fitting-point self-check results, the selected formula and its
parameters, fresh raw per-replicate evidence for `N=750`, the
six-point held-out decision table, a plot of the refit curve overlaid
on all eleven points (five fitting, six held-out) with Stage 4g's
original curve shown for comparison, and a report stating plainly
whether the repair generalizes or merely relocates the boundary
problem to a different `N`.

## Consequences

If PROCEED: this refit formula becomes the sequential engine's
validated `alpha(N)` rule for the overlap shape, superseding
`docs/stage4g_charter.md`'s formula, with `N=750` now genuinely
validated rather than silently assumed. The single predicted
`alpha_hat(750)` from this charter should then be used to re-run
**only** Stage 4h's `N=750` cell (reusing `stage4h.py`'s runner
unmodified — this is a data point, not a code change) to finally
complete the direct `N=750` comparison against D-018's `.569` TPR that
Stage 4h's own charter was built around but could not make. This does
not reopen or revalidate Stage 4h's `N=625`/`700` results, which stand
as recorded in D-037.

If REASSESS: this means dropping one boundary fitting point was not
sufficient to fix the underlying issue — plausibly because `N=750`
sits at a genuine inflection in the true relationship rather than
merely being under-supported by the original fit. In that case a
formula is not the right artifact for `N=750` specifically; document
this plainly and fall back to a lookup-table value for `N=750` (taken
directly from Stage 4e's own already-validated data point) rather than
trusting any fitted extrapolation there. Either outcome leaves Stage
4h's accepted `N=625`/`700` results untouched.
