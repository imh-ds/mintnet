# Stage 1i Charter: Locating the N=500-750 Crossover (R2i)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

`docs/stage1h_charter.md` established a per-N table showing `N=500` as a
near-miss (no adjacent alpha pair passes both criteria in the tested grid,
but the closest values — `alpha=.18` for TPR, `alpha=.20` for FPR — each
individually clear their own threshold by less than `.003`) and `N=750`
as a clean PROCEED with real margin (`docs/decision_log.md` D-009). No
sample size between `500` and `750` has ever been tested. Given how close
`500` came, the actual minimum viable `N` is very likely somewhere in this
untested gap, not at `750` itself — `750` was chosen in `docs/stage1c_charter.md`
as a conservative round-number step away from `500`'s known risk, not as
a located threshold.

This charter tests four new sample sizes inside the gap to locate the
crossover more precisely, using the same per-N, margin-robust selection
rule as R2h/R2g (`docs/stage1g_charter.md`, `docs/stage1h_charter.md`).

## Data-generating process

New sample sizes: `N = [550, 600, 650, 700]`. Strengths `a = b = [.3, .5,
.7]`, `balanced`/`moderate`/`strong` triangle fixtures, master seed
`20260829`, 2000 replicates (development 0-999, validation 1000-1999) —
unchanged from R2h. `N=500` and `N=750` are not re-simulated: this
charter reuses those two sample sizes' raw evidence directly from
`results/generated/stage1h_dpi/raw_metrics.csv` as the gap's bookends, and
generates fresh data only for the four new, previously-untested sample
sizes. (`N=500` and `N=750` were themselves already established as
byte-identical across R2c through R2h via positional seed derivation; the
four new values here use their own fresh seed positions, since no prior
data exists for them to reproduce.)

## Mechanism

Unchanged: per-edge Fisher-z partial-correlation test. Alpha grid
identical to R2h: `[.0001, .001, .005, .01, .02, .04, .06, .08, .10, .12,
.14, .16, .18, .20, .22, .24, .26, .28, .30, .35, .40, .45, .50]` (23
points), for direct comparability with the R2h bookend values.

## Selection and gate

Unchanged from R2h: selection and validation are performed independently
per sample size (not pooled). For each `N` in `[500, 550, 600, 650, 700,
750]`, an alpha is *N-eligible* if every strength (all three triangle
families) individually passes chain/fork TPR `>= .80` and triangle FPR
`<= .10`. Among adjacent N-eligible pairs, select the one maximizing the
worst-case margin (R2g's rule). A selected pair must then pass validation
individually at every strength for that `N`, with no recorded error, to
PROCEED for that `N`.

**Output is a six-row per-N table** spanning the full gap plus both
bookends, not a single global status — same reporting shape as R2h.

## Required evidence

Resolved configuration, this charter's SHA-256, a pointer to (and hash
of) the reused `N=500`/`750` rows from R2h's raw evidence, commit and
runtime metadata, raw per-replicate evidence for the four new sample
sizes, aggregate metrics, the six-row per-N decision table, report,
figures, and the exploratory `1 - p_value` score tracking (non-gating,
not a calibration claim, consistent with every prior round).

## Consequences

If the table shows a clean, monotonic transition (e.g., REASSESS through
some point, then PROCEED from some `N` onward): that `N` becomes the
tightened floor, replacing `750` as the practical minimum, and
`docs/validated_operating_ranges.md` should be updated accordingly.

If the table is not monotonic (e.g., an isolated PROCEED surrounded by
REASSESS, echoing R2d/R2f's earlier near-miss patterns): treat it as
evidence of noise near a genuine boundary rather than a located
threshold, and do not tighten the floor below `750` without further
investigation (finer alpha resolution or more replicates at the specific
ambiguous `N`, each its own charter as before).

Either way, this charter does not itself authorize Stage 2 work; it
refines the already-validated `N >= 750` scope from D-008/D-009, it does
not revisit whether the mechanism works.
