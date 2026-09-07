# Stage 1h Charter: Per-N Alpha Selection (R2h)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

`docs/stage1g_charter.md` validated a single alpha pair, `(0.14, 0.15)`,
required to pass simultaneously across the entire `N in [750, 1000, 1500,
2000]` range (`docs/decision_log.md`, D-008). That charter never asked
whether smaller `N` could pass with a *different* alpha, because its gate
structure required one pair to work everywhere at once.

Informal inspection of already-collected R2c/R2f evidence (not itself a
chartered result, but motivating this charter's design) suggests the
answer differs by sample size: `N = 300` and `N = 500` already show
several alpha values in the existing fine grid that individually meet both
criteria; `N = 200` shows a near-miss around `alpha = 0.20`; `N = 100`
shows what looks like a genuine, wide gap — no tested alpha's chain/fork
TPR range (roughly `alpha <= 0.2`) overlaps its triangle FPR range
(roughly `alpha >= 0.35`).

This charter tests directly, and formally, whether each sample size has
*its own* passing alpha region, rather than requiring one alpha to serve
every `N`. This is a deliberate, executive-level change in the gate's
structure, not a discovery to be made incidentally: **different `N` are
explicitly permitted to need different alpha pairs.** The resulting
per-`N` table is intended as the evidentiary basis for a future default
`alpha(N)` rule the production method could compute automatically from
sample size — designing that rule is explicitly out of scope for this
charter, which only gathers the per-`N` evidence a later design would
need.

## Data-generating process

`N = [100, 200, 300, 500, 750, 1000, 1500, 2000, 3000]` — R2g's range
extended downward with no change (`100`-`2000` already tested) and upward
with `3000`, newly added. Strengths `a = b = [.3, .5, .7]`, `balanced`/
`moderate`/`strong` triangle fixtures, master seed `20260829`, 2000
replicates (development 0-999, validation 1000-1999) — matching R2e
through R2g. This is a **fresh, self-contained simulation** rather than a
reuse of prior evidence: prior runs used different, mismatched alpha grids
per `N` (R2c's 9-point coarse grid; R2f/R2g's 20-point `[.06, .25]` fine
grid), and stitching them together would complicate provenance for no
benefit given how cheap this mechanism is to re-run.

## Mechanism

Unchanged: per-edge Fisher-z partial-correlation test. Alpha grid widened
to cover both the already-known-working region and the region needed for
smaller `N`, informed by the coarse-grid gap observed at `N = 100`:
`[.0001, .001, .005, .01, .02, .04, .06, .08, .10, .12, .14, .16, .18,
.20, .22, .24, .26, .28, .30, .35, .40, .45, .50]` (23 values).

## Selection and gate

**This is the structural change from every prior Stage 1 charter.**
Selection and validation are performed **independently for each sample
size `N`**, not pooled or required to hold across a range:

For a given `N`, an alpha is *N-eligible* if, for every strength (all
three triangle families), chain and fork indirect-edge TPR are each at
least 0.80 and triangle true-edge FPR is at most 0.10 — the same per-cell
definition R2d introduced, applied within one `N` instead of across a
range of `N`. Among adjacent `N`-eligible alpha pairs (in this `N`'s
grid), select the pair maximizing the worst-case margin (R2g's rule),
ties broken by the lexicographically lowest pair. If no adjacent eligible
pair exists for that `N`, that `N`'s result is REASSESS.

A selected pair for a given `N` must then pass validation (replicates
1000-1999) individually at every strength for that `N`, with no recorded
error, to PROCEED for that `N`.

**Output is a per-`N` table**, not one global status: each `N in [100,
200, 300, 500, 750, 1000, 1500, 2000, 3000]` gets its own PROCEED (with a
selected alpha pair) or REASSESS. This stage does not fit or select a
formula for `alpha(N)`, and does not authorize Stage 2 work; it produces
the evidence table a future default-alpha design would use.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence, aggregate metrics, the per-`N`
decision table, report, figures, and the exploratory calibration summary
(unchanged in purpose from R2b onward: non-gating).

## Consequences

If some `N` REASSESS while others PROCEED (the expected outcome given the
informal preview above): this is not a failure of the charter or the
mechanism — it is the answer to the question asked. Document which `N`
have a validated alpha and which do not; any `N` without one is out of
scope for the method until a further charter addresses it (e.g., a
different DGP assumption, a different test statistic, or an explicit
"insufficient data" boundary the production method reports rather than
guesses past).

If PROCEED at every tested `N`: still does not authorize Stage 2 by
itself, but substantially strengthens confidence that the method's
`N`-dependence is smooth and predictable rather than boundary-fragile.

Either way, the per-`N` table is required input to a later, separate
charter proposing a specific `alpha(N)` default rule for the production
method — fitting or freezing that rule is not part of this charter.
