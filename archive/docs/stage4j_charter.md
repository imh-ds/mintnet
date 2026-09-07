# Stage 4j Charter: Densely-Spaced Refit Across the N=700-750 Boundary (R6j)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

D-038 (Stage 4i) found that removing `N=750` from the `alpha(N)`
fitting set did not close the negative-alpha gap it was meant to fix —
it relocated the curve's zero-crossing from between `N=725`/`750` to
between `N=700`/`725`, breaking a previously-valid point (`N=725`) in
the process. The diagnosis: this is a **sample-density problem**, not a
fitting-target problem. The curve is fit on points spaced `~50` apart
(`650, 700, 750`) right where it happens to cross zero, so small changes
in which points are included shift the crossing by a comparable amount
to the gap itself. Excluding one point can only relocate the shakiness,
never resolve it.

**Objective:** test the diagnosis directly. Add several new fitting
points *densely spaced inside* `[700, 750]` — the region actually
containing the crossing — so the curve has enough local support to be
trustworthy there, then hold out points *between* those new dense
points as the real test of whether density (not point selection) is
the fix.

**Scope, deliberately narrow:** overlap shape only, `alpha(N)` formula
only. Stage 4h's accepted `N=625`/`700` results (D-037) and Stage 4g's
`N=400`-`675` results are not re-litigated here.

## Fitting data

**Ten fitting points, not six or five.**

1. **Four unchanged coarse points** (`N = 300, 500, 600, 650`): reused
   verbatim from Stage 4e's own already-generated raw evidence
   (`results/generated/stage4e_candidacy_metric/raw_metrics.csv`,
   development replicates only), identical selection rule to Stage
   4g/4i (`compute_fitting_points`: argmax `conditional_accuracy`
   subject to true-edge FPR `<= .10` and candidacy rate `>= .80`). No
   new simulation for these four.

2. **Two unchanged boundary points already in hand** (`N = 700, 750`):
   also reused verbatim from Stage 4e's own raw evidence, same
   selection rule — Stage 4e already simulated a full alpha grid at
   both. No new simulation for these two either.

3. **Four new dense points** (`N = 710, 720, 730, 740` — evenly spaced
   inside the gap between `700` and `750`): **requires fresh
   simulation**, one full alpha-grid sweep at each `N`, mirroring Stage
   4e's own methodology exactly (identical alpha grid `[.50, .30, .20,
   .10, .05, .01, .005, .001, .0001]`, identical overlap DGP and seed
   derivation, `master_seed=20260830`, overlap's own shape index,
   `2,000` replicates per `N`: development `0`-`999` used for the
   fitting selection below, validation `1000`-`1999` retained for
   consistency with Stage 4e's own convention). Each `N`'s
   `alpha_star` is selected by the same argmax rule as the other eight
   fitting points, applied to this new development data.

## Held-out validation data (new simulation required for all nine)

**Nine held-out points, none previously simulated at their exact `N`,
all strictly between two fitting points:**

- **Coarse-region interpolation** (unchanged from Stage 4g/4i design):
  `N = 400, 550, 625, 675`.
- **Dense-region interpolation** (new — the actual test of this
  charter's hypothesis): `N = 705, 715, 725, 735, 745` — the midpoints
  between each pair of adjacent dense fitting points. `N=725` in
  particular is the exact point Stage 4i's refit broke; this is a
  direct re-test of it under a properly-supported curve.

Each held-out `N`: `2,000` fresh replicates (development `0`-`999`,
validation `1000`-`1999`), identical DGP/seed derivation to every prior
Stage 4 overlap charter.

## Fitting procedure

Identical candidate forms and selection rule to Stage 4g/4i's own
inheritance from `docs/stage1j_charter.md`: linear in `N`, linear in
`log(N)`, power law, inverse-sqrt; highest R² wins, with the inverse-
sqrt tiebreak preference within `0.005` R² of the best.

**Self-check (carried forward from Stage 4i, applied to all ten
fitting points this time):** before any gate is evaluated, confirm the
refit formula's predicted `alpha` is a valid probability, `0 < alpha_hat
< 1`, at every one of its own ten fitting `N`. Record pass/fail per
point regardless of outcome.

## Gate

For each of the nine held-out `N`, compute the single predicted
`alpha_hat = f(N)` and test it against that `N`'s validation
replicates (`1000`-`1999`):

1. `alpha_hat` itself must be a valid probability, `0 < alpha_hat < 1`
   — an automatic, explicitly-reported failure otherwise (Stage 4i's
   own repair to Stage 4g's gate, carried forward unmodified).
2. `conditional_accuracy >= .80` with margin `>= .02`.
3. True-edge retention FPR `<= .10` with margin `>= .02`.
4. Candidacy rate reported descriptively alongside (not gated).

**PROCEED** only if the fitting-point self-check passes at all ten
fitting points **and** `alpha_hat` clears all three gated criteria at
**every** held-out `N`, including all five dense-region points. If any
of these nine held-out N fails, the failure's `N` and criterion are
reported explicitly, mirroring Stage 1j/4g/4i's own reporting standard.

**Partial-success reporting requirement (new — this charter's own
hypothesis has a graded answer, not just pass/fail):** even under an
overall REASSESS, report each dense-region held-out point's individual
status separately. If the dense-region points closer to `700` PROCEED
while only the points closest to `750` still fail, that is itself
informative (density helps but does not fully cover the range) and
must not be collapsed into an undifferentiated REASSESS.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the Stage 4e raw-evidence SHA-256 (reused coarse+boundary
fitting data), raw per-replicate evidence for the four new dense
fitting `N`, the ten-point fitting table and each candidate form's R²,
the fitting-point self-check results, the selected formula and its
parameters, raw per-replicate evidence for all nine held-out `N`, the
nine-point held-out decision table, a plot of the refit curve overlaid
on all nineteen points (ten fitting, nine held-out) with Stage 4g's and
Stage 4i's original curves shown for comparison, and a report stating
plainly whether dense local support resolves the boundary gap, narrows
it, or leaves it unchanged.

## Consequences

If PROCEED: this refit formula becomes the sequential engine's
validated `alpha(N)` rule for the overlap shape across the full `[400,
750]` range, finally superseding both Stage 4g's original (`[400,
725]`, D-038) and Stage 4i's failed repair. The single predicted
`alpha_hat(750)` from this charter should then be used to re-run Stage
4h's `N=750` cell (reusing `stage4h.py`'s runner unmodified) to
complete the direct D-018 comparison that has been open since D-037.

If REASSESS: report which specific held-out points still fail per the
partial-success requirement above. If dense support narrows the gap
without closing it, that argues for even denser sampling in a future
charter (a genuine local floor is being approached, not an artifact).
If dense support makes no measurable difference at all, that would be
strong evidence the true relationship has a **structural discontinuity**
near `N=700`-`750` rather than a smooth curve merely under-sampled
there — in which case no continuous formula is the right artifact for
this region, and a lookup table (as D-038 already recommended for
`N=750` itself) should be adopted permanently for the entire `[700,
750]` neighborhood, not just the single point. Either outcome leaves
Stage 4h's accepted `N=625`/`700` results untouched.
