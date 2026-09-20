# Stage 9a Charter: Tier-1 Bootstrap-Stability for `growing_subset_dpi`'s Own Unresolved (`conditioning_size_used >= 2`) Decisions (main)

Status: **FROZEN before results**
Date: 2026-09-08

## Background and objective

D-076 established, on already-collected evidence, that `growing_
subset_dpi`'s own retain decisions are `100%` accurate at every
conditioning depth, but its own prune decisions degrade from `91%`
(`conditioning_size_used <= 1`, the large majority of cases) to `62.5%`
/ `9.5%` / `0.8%` at sizes `2`/`3`/`4` — and that roughly `17%` of
"retained" decisions at size `4` are themselves hidden false positives,
indistinguishable from true edges by margin alone. Six mechanism-
diagnosis charters (D-069, D-071 through D-075) failed to identify
*why*. Per D-075's own explicit consequence, no seventh mechanism
charter is planned. This charter takes the alternative path named at
the close of both D-075 and D-076: **detect** unreliable decisions
directly, without needing to explain them, using a mechanism this
project has already validated for exactly this kind of problem on a
different engine.

**This is not a new idea invented here.** D-019 (Stage 3) and D-020
(Stage 3b) already validated bootstrap edge-stability (`pi_final`,
`B=500` nonparametric row bootstraps, `mintnet.bootstrap.stability.
compute_edge_stability`) for `mintnet.pipeline.compose_screen_then_
prune` — a **different** DPI engine (the sequential screen-then-prune
pipeline, not `growing_subset_dpi`'s own OR-rule search): true edges
show `pi_final ~1.0`; null pairs show `~0.02`; and, critically, a
**wrongly-retained edge showed intermediate, not high, stability**
(`~0.74`, separable from true edges via a calibrated `pi_min=.80`) —
directly rescuing a known failure mode (D-018's overlap-DGP
under-detection at `N=750`) with zero cost to true-edge retention
(FPR `0` throughout). **This charter asks whether the same kind of
separation holds for a different engine's different, newly-identified
failure**: does `pi_final` separate correctly- from incorrectly-
resolved `growing_subset_dpi` decisions specifically within the
`conditioning_size_used >= 2` regime D-076 identified?

**Why `compute_edge_stability` cannot answer this today.** It is
hardwired to call `compose_screen_then_prune` per resample
(`mintnet.bootstrap.stability.py`, line-level, not merely
configuration) — it has never been run against `growing_subset_dpi` at
all. This charter's own first step is a purely additive extension, not
a re-run of anything already validated.

## Mechanism

**Step 1 — extend the bootstrap module (additive, no behavior change
to existing code).** Add a new function, `compute_edge_stability_
growing_subset(data, screening_alpha, dpi_alpha, max_conditioning_size,
bootstraps, rng)`, that runs, per resample: `compute_pairwise_
screening_evidence` -> `screen_uncorrected` -> `growing_subset_dpi`
(`motif_family=None`, matching `stage8c_composed_calibration.py`'s own
usage) — the same three-call sequence Stage 8c's own runner already
uses on the point estimate, now repeated per bootstrap resample.
Reuses `bootstrap_resample` and the existing degenerate-resample
handling (`ValueError` -> excluded, not counted as edge-absent)
unchanged. Does not modify `compute_edge_stability` (the existing,
`compose_screen_then_prune`-based function) or any of its own already-
validated Stage 3/3b behavior.

**Step 2 — targeted, compute-efficient case selection (zero new base-
DGP randomness).** Rather than a blind fresh sweep (conditioning_size
`>= 2` decisions are a small minority — `~2.2%` of all edge decisions
per D-076's own count, `7,203` of `333,507`), reuse Stage 8c's own
already-collected enriched evidence (`chain_fork_hub`/`overlap`,
`N in {400,...,1750}`, `strength=0.5`) to identify specific `(dgp, n,
replicate)` instances already known to contain a `conditioning_size_
used >= 2` decision, and draw a stratified sample of a fixed, disclosed
count (see Data-generating processes) across three outcome categories:
**(a)** true edges correctly retained at size `>= 2`, **(b)** false
edges wrongly retained at size `>= 2`, **(c)** false edges correctly
pruned at size `>= 2`. Regenerate each selected instance's own original
data from its already-recorded seed (deterministic, `stage5a._
condition_seed`/`_DGP_REGISTRY`, matching D-072's/D-074's own
precedent) — no new base-network sampling, only new *bootstrap*
resampling of already-determined datasets.

**Step 3 — H9 (stability separates correct from incorrect, D-019's own
question, asked of a different engine and a different failure).** For
each selected instance, run `B=500` bootstrap resamples through Step
1's new function and record `pi_final` for the specific pair that
resolved at `conditioning_size_used >= 2` in the original point
estimate. Compare `pi_final` distributions across the three categories.
**Confirmed** if category (b) (wrongly retained) shows a `pi_final`
distribution that is both (i) reliably lower than category (a)
(correctly retained true edges) — non-overlapping or clearly separated
medians, mirroring D-019's own `.74` vs. `~1.0` gap — and (ii) not
simply indistinguishable from category (a), even if (mirroring D-019's
own "intermediate, not low" finding) it is not as low as a null pair's
own stability either.

**Step 4 — calibrate a filter, only if H9 is confirmed (mirrors D-020's
own gate design exactly).** Development/validation split of the
selected instances (matching this project's own fixed, non-data-driven
convention). Candidate grid `pi_min in {.70, .80, .90, .95}`. Per the
`conditioning_size_used >= 2` population only: select the smallest
eligible `pi_min` on development meeting **recall on category (a)
`>= .90`** (true edges must mostly survive the filter) and **category
(b)'s own removal rate `>= .50`** (the filter must meaningfully catch
wrongly-retained edges, not just theoretically separate them) —
confirm both criteria again on validation to PROCEED.

## Data-generating processes

Identical DGPs to Stage 8c's own (`chain_fork_hub`, `overlap`,
`strength=0.5`, `screening_alpha=0.001`, `max_conditioning_size=4`,
`N in {400,...,1750}`) — no new DGP. Selected-instance count: up to
`60` per category per `(dgp, N)` cell with enough qualifying instances
available (mirrors D-019's own `30` development `+` `30` validation
convention), capped by however many distinct qualifying `(dgp, n,
replicate)` instances actually exist in Stage 8c's own evidence for
that cell — reported, not assumed, since category (a) at small `N` may
be sparse (D-076's own count: only `1,972` true edges at size `2`
across the *entire* dataset, versus `79,790` at size `3`).

## Compute-cost disclosure

**This is disclosed as likely the most expensive Stage 8/9-series
charter to date, not assumed cheap.** `B=500` bootstrap resamples, each
requiring a full `growing_subset_dpi` search (materially more expensive
per call than `compose_screen_then_prune`, which D-020 already
disclosed as "roughly `500x` the base pipeline's own per-dataset cost"
at `B=500`) — multiplied across however many selected instances Step 2
produces (up to `3` categories `x` `7` `N` values `x` `2` DGPs `x` `60`
`=` `2,520` instances at the cap, `x` `500` resamples `=` up to
`1,260,000` `growing_subset_dpi` calls). Per this project's own
standing discipline, stated even more emphatically here given this
precedent: **measure real wall-clock cost of `B=500` resamples on at
least one real selected instance (at the largest `N`) before
finalizing the instance count, `B`, or shard plan** — if the measured
cost makes the capped instance count infeasible within a reasonable
shard budget, reduce the per-cell cap (disclosed, not silently) rather
than reduce `B` below `500` (the value D-019/D-020 already validated;
changing it would be a new, unvalidated resampling scheme).

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** —
unchanged, hard requirement, per this project's established practice.

## Selection and gate

**H9 (stability separates correct from incorrect)**: Confirmed / Not
confirmed / Inconclusive, per the Step 3 criterion above — a diagnostic
verdict, no PROCEED/REASSESS framing (mirrors D-019's own diagnostic
framing before D-020's own separate filter-validation step).

**Step 4 filter (only attempted if H9 confirmed)**: PROCEED / REASSESS,
per the Step 4 criterion above — mirrors D-020's own gate structure
exactly, scoped to the `conditioning_size_used >= 2` population only.

## Explicit non-goals

- **No change to `compose_screen_then_prune`'s own already-validated
  Stage 3/3b bootstrap-stability behavior.** `compute_edge_stability`
  is not modified; `compute_edge_stability_growing_subset` is a new,
  separate function.
- **No claim about `conditioning_size_used <= 1`.** D-076 already
  established this regime is reliable; this charter does not test
  whether stability filtering changes anything there (it should not
  need to).
- **No production deployment**, even on a full PROCEED — mirrors
  D-020's own explicit non-authorization: adding a stability-filter
  stage to any pipeline as a production default is a separate
  architecture decision, not authorized by this charter's own result,
  and the `B=500` cost is a real, unresolved practical concern for that
  future decision regardless of this charter's own outcome.
- **No claim beyond `chain_fork_hub`/`overlap` at `strength=0.5`.** Not
  validated for other composed shapes, strengths, `max_conditioning_
  size` values, or isolated-tier fixtures.
- **No re-litigation of D-069/D-071 through D-076's own findings.**
  This charter does not attempt to explain *why* `conditioning_size_
  used >= 2` decisions are unreliable — it tests whether that
  unreliability is *detectable* via resampling, a different and
  mechanism-agnostic question, exactly as D-075/D-076 both named as the
  recommended next angle.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the up-front
timing measurement and resulting instance-count/shard decision, the
selected-instance manifest (dgp, n, replicate, pair, category), raw
per-instance `pi_final` values, the Step 3 category-comparison table,
the H9 verdict, the Step 4 development/validation gate tables (if run),
and a report.

## Consequences

**If H9 confirmed and Step 4 PROCEEDs**: a genuinely new, mechanism-
agnostic detector exists for `growing_subset_dpi`'s own least reliable
decisions — a practical answer to D-076's own recommendation ("treat
`conditioning_size_used >= 2` decisions as unresolved") that goes
beyond a blanket flag, since it could in principle rescue *some*
correctly-retained true edges. Motivates (as a separate, not-yet-
decided future step) an architecture charter on whether and how to
integrate this into a production-facing tier, weighing the `B=500`
compute cost this charter does not resolve.

**If H9 confirmed but Step 4 does not reach PROCEED (poor recall/
removal tradeoff)**: stability separates the two populations
descriptively but not cleanly enough for a safe, calibrated filter at
this scale of evidence — a real, disclosed limit, not a failure to
find something.

**If H9 is not confirmed**: unlike `compose_screen_then_prune`'s own
already-validated case, `growing_subset_dpi`'s own conditioning_size
`>= 2` failures do not show a stability signature separating them from
correct decisions — a genuinely informative negative result (this
project's own established bootstrap-stability mechanism, validated on
one engine, does not automatically transfer to another), and would
leave D-076's own blanket "treat as unresolved" recommendation as the
best available practical guidance, with no known refinement.
