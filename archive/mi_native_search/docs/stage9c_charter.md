# Stage 9c Charter: Adapting Bootstrap-Rescue to the Structured-Density Engine (mi-native)

Status: **FROZEN before results**
Date: 2026-09-11

## Background and objective

D-085 (Stage 7h) confirmed that `growing_subset_dpi_structured_density`
-- the genuinely MI-based engine, not the older Fisher-z one -- shows
the SAME retain/prune asymmetry D-076 first found: retain decisions
are essentially perfectly reliable (`99.96%`, matching D-076's own
Fisher-z finding almost exactly), while prune decisions degrade
catastrophically with conditioning depth (`.906 -> .793 -> .332 ->
.119` across depth `1`-`4`, nearly the same shape as D-076's own
`.91 -> .625 -> .095 -> .008`). Stage 9's own bootstrap-rescue
mechanism (`growing_subset_dpi_with_stability_rescue`, D-077-D-081)
was built and validated specifically against this signature for the
Fisher-z engine, achieving `>99%` recall/removal on fresh evidence
(D-080). **This charter asks whether an analogously-built rescue
mechanism works for the structured-density engine too.**

**A critical cost difference, disclosed up front rather than assumed
away.** Fisher-z's own per-subset test is closed-form and effectively
free; `compute_edge_stability_growing_subset`'s own `B=500` bootstrap
cost (Stage 9's own measured range, `~80s`-`280s` TOTAL per qualifying
dataset) reflects that. The structured-density engine's own per-
*replicate* cost -- not per resample, per whole growing-subset search
-- is `~40s`-`65s` (`chain_fork_hub`) to `~172s`-`264s` (`overlap`),
measured directly for Stage 7h (D-085). **Bootstrapping this engine
means running that same expensive search once per resample.** At
Stage 9's own `B=500` default, a single qualifying `overlap`-like
dataset would cost on the order of `500 x 200s ~= 28 hours` --
completely infeasible. **This charter cannot inherit `B=500`, `pi_
min=0.90`, or any other Fisher-z-tuned constant without re-deriving
them under this engine's own, much higher, per-resample cost.**

## Mechanism

**Step 1 -- build the mechanism, mirroring Stage 9's own design
exactly, with `n_jobs` parallelism from the start (not retrofitted
later the way D-081 added it to the Fisher-z version).**

New function, `mintnet.bootstrap.stability.compute_edge_stability_
growing_subset_structured_density(data, screening_alpha, alpha, max_
conditioning_size, bootstraps, master_seed, degree, ridge_lambda, cv_
folds, k_perm, permutations, rng, *, n_jobs="auto")` -- identical
resampling and degenerate-resample handling to `compute_edge_
stability_growing_subset`'s own, calling `growing_subset_dpi_
structured_density` per resample instead of `growing_subset_dpi`.
Reuses the already-validated `_resolve_n_jobs`/`_AUTO_N_JOBS_CAP`
machinery (D-081) unchanged -- each resample's own search is itself
expensive enough that parallelizing across resamples matters even
more here than it did for the Fisher-z engine.

New function, `mintnet.pipeline.stability_rescue.growing_subset_dpi_
structured_density_with_stability_rescue(...)` -- identical logic to
`growing_subset_dpi_with_stability_rescue`'s own: run the point-
estimate search once, identify edges with `conditioning_size_used >=
UNRESOLVED_CONDITIONING_SIZE` (`2`, D-076's own boundary, unchanged),
bootstrap only if at least one such edge exists, flip retain -> prune
for any qualifying edge whose `pi_final < pi_min`. Purely additive,
mirrors the existing function's own file/module placement pattern.

**Step 2 (REQUIRED before any evidence run) -- measure real per-
resample cost directly, under GitHub Actions' own thread limits, with
`n_jobs="auto"` engaged**, on at least one known-qualifying `overlap`
dataset (reuse a `conditioning_size_used >= 2` case from Stage 7h's
own evidence, `results/generated/stage7h_composed/exploded_qualifying.
csv`, for a real rather than synthetic test case) and one `chain_fork_
hub` case. This measurement determines the maximum feasible `B` for
this charter -- **provisionally planned at `B=20`-`50`, roughly `10x`-
`25x` smaller than Stage 9's own `500`, an order-of-magnitude
reduction disclosed as a real, open risk (see Explicit non-goals), not
assumed adequate by analogy.**

**Step 3 -- calibrate `pi_min` fresh, not inherited from D-079.**
`pi_min=0.90` was selected for `B=500`'s own resolution; at a much
smaller `B`, `pi_final` is a coarser statistic (e.g. `B=20` only
resolves to multiples of `.05`) and the same threshold may no longer
be the right one. Reuse Stage 9a's own calibration procedure exactly
(development/validation split by replicate parity, grid `{.50, .60,
.70, .80, .90}` -- extended downward from Stage 9a's own `{.70, .80,
.90, .95}` since a coarser `pi_final` may need a more lenient cut,
smallest value clearing recall `>=.90`/removal `>=.50` on development,
confirmed on validation).

**Step 4 -- validate recall/removal on fresh evidence**, mirroring
Stage 9b's own end-to-end design: call the new wired function directly
(not the individual pieces by hand) on NEWLY drawn replicates (a fresh
seed range, disjoint from Stage 7h's own `master_seed=93000` and every
prior charter's usage), compare against Stage 9b's own `>=.95`/`>=.85`
tolerance.

## Data-generating processes

`chain_fork_hub`, `overlap` (`stage5a._DGP_REGISTRY`), `strength=0.5`
only (not the full `{0.3, 0.5, 0.7}` sweep Stage 7h used -- narrower
scope given this charter's own much higher per-resample cost; the
strength sweep is separate future work if this charter PROCEEDs),
`N` restricted to a SUBSET of Stage 7h's own grid -- **exact subset
decided after Step 2's own cost measurement**, not committed here;
provisionally `N in {750, 1500}` (the two values every prior mi-native
composed-tier charter has treated as its own minimum comparison pair)
unless Step 2 shows even this is infeasible at any reasonable `B`.

## Compute-cost disclosure

**Not assumed to transfer from Stage 9's own `B=500`/Fisher-z cost in
any form.** Step 2 is a hard prerequisite, not a formality: this
charter's own `N` range, DGP scope, `B`, and replicate cap are ALL
provisional pending that direct measurement, and this charter's own
author commits to revising every one of them downward (or, if
Step 2 shows the mechanism is infeasible at any usable `B`, to
reporting that as a direct REASSESS rather than forcing a run) before
any GitHub Actions dispatch. This repeats, deliberately, the exact
discipline Stage 9a's own two cancelled multi-hour dispatches forced
this project to learn the hard way -- here, applied preemptively.

**This charter's evidence, once Step 2 fixes a feasible scope, MUST be
generated via the sharded GitHub Actions workflow, not local
multiprocessing.**

## Selection and gate

**PROCEED** only if, at every tested `(dgp, N)` cell with at least
`10` qualifying (`conditioning_size_used >= 2`) true-and-originally-
retained and false-and-wrongly-retained instances (mirrors Stage 9b's
own `min_count=10` sparse-cell handling), the calibrated `pi_min`
(Step 3) achieves recall `>= 0.95` and removal `>= 0.85` on Step 4's
own fresh, held-out evidence. **REASSESS** otherwise -- including if
Step 2's own cost measurement makes even a minimally-informative `B`
infeasible within a reasonable shard budget, in which case this
charter reports that constraint directly as its own REASSESS reason,
not a silently abandoned attempt.

## Explicit non-goals

- **No assumption that a `10x`-`25x` smaller `B` has comparable
  resolving power to Stage 9's own `B=500`.** Bootstrap estimation
  variance generally decreases with `B`; a much smaller `B` may
  produce a noisier `pi_final` that a `pi_min` cut resolves less
  cleanly, independent of whether the underlying separating signature
  (D-085's own confirmed transfer of D-076's asymmetry) is real. This
  charter treats that as an open, testable risk, not a solved problem.
- **No claim beyond `chain_fork_hub`/`overlap` at `strength=0.5`**,
  narrower than Stage 9's own `{0.3, 0.5, 0.7}` scope for the Fisher-z
  mechanism and Stage 7h's own composed-tier sweep -- extending to
  other strengths is separate future work, only worth chartering after
  this narrower question is answered.
- **No resolution of D-085's own still-unexplained finding** that the
  structured-density confidence score's own trend with `N` is
  significantly NEGATIVE on composed networks. That is a separate,
  not-yet-chartered question this charter does not depend on or
  address -- the rescue mechanism here uses `pi_final` (bootstrap
  retention frequency), not the point-estimate `confidence` field, so
  the two are not mechanically coupled, but a future reader should not
  assume this charter's own PROCEED (if reached) resolves that other
  open question.
- **No production deployment authorization**, even on a full PROCEED
  -- unchanged from every prior bootstrap-rescue charter's own
  non-goal (D-077 through D-081).
- **No re-tuning of `degree`, `k_perm`, or any other structured-
  density estimator parameter.** `degree=1` inherited unchanged from
  D-063.

## Required evidence

This charter's SHA-256, commit and runtime metadata, Step 2's own
timing measurement and the resulting `B`/`N`/scope decision (with
explicit reasoning if narrower than the provisional plan above), Step
3's own calibration procedure and selected `pi_min`, Step 4's own raw
per-edge evidence and recall/removal table, the gate decision, and a
report.

## Consequences

**If PROCEED**: a second, estimator-specific bootstrap-rescue function
becomes available (`growing_subset_dpi_structured_density_with_
stability_rescue`), giving the structured-density engine the same
disclosed, opt-in fix for D-076's asymmetry that Stage 9 gave the
Fisher-z engine -- within this charter's own narrower tested scope
(`strength=0.5` only, a `B` far smaller than `500`). Extending to
other strengths, or attempting to close the gap to `B=500`-level
resolving power via a cheaper resampling scheme, become separate,
not-yet-decided future steps.

**If REASSESS**: either the mechanism itself does not transfer (the
smaller feasible `B` cannot resolve `pi_final` well enough to separate
correct from incorrect decisions at an acceptable recall/removal
tradeoff), or the per-resample cost is infeasible at any usable `B`
within a reasonable compute budget -- both are informative, disclosed
outcomes. In the latter case, this project would have learned that
bootstrap-based rescue, while validated as a *concept* on the cheaper
Fisher-z engine, is not automatically portable to a genuinely more
expensive estimator, motivating a search for a cheaper diagnostic
(e.g. a subsampling scheme requiring fewer full re-searches) as a
distinct future direction rather than a smaller `B` on the same design.
