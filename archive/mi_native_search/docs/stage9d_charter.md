# Stage 9d Charter: Localized (Single-Edge) Bootstrap-Rescue -- Testing Whether Freezing Candidacy and Conditioning Set Preserves Calibration While Being Dramatically Cheaper (mi-native)

Status: **FROZEN before results**
Date: 2026-09-14

## Background and objective

D-087 validated `growing_subset_dpi_structured_density_with_stability_
rescue` for `chain_fork_hub` at `N in {750, 1500}` -- a real result,
not in question here. But trying the resulting `mintnet.api.discover`
wrapper against an actual `overlap`-shaped dataset with rescue enabled
(2026-09-14, this same session) confirmed in practice what D-085/D-086
already disclosed as a risk: the run exceeded 40 minutes and was
manually terminated, consistent with D-085's own measured heavy tail
(`overlap` mean `377s`, max `~14,548s` for a single point-estimate
search) multiplied by this mechanism's own `B=10` full resample
repeats. **A user cannot realistically be expected to wait hours for
rescue on exactly the dense network shape it is most needed for.**

**Root cause, confirmed directly against the actual code, not
assumed**: `mintnet.bootstrap.stability._run_one_growing_subset_
structured_density` re-runs the ENTIRE pipeline on every bootstrap
resample -- full re-screening (`compute_pairwise_screening_evidence`,
`screen_uncorrected`) across every possible pair, THEN the full
growing-subset search (`growing_subset_dpi_structured_density`) across
every pair that screens in. For a dense network where most pairs reach
deep conditioning, every one of the `B` resamples pays that same full
cost again, even though only a small number of specific edges were
ever actually ambiguous. **This charter asks whether a targeted
alternative -- resample the data, but only re-test the SPECIFIC edges
that were ambiguous in the point estimate, against their OWN
already-discovered conditioning set, skipping re-screening and
re-searching everything else -- preserves the same recall/removal
calibration D-087 achieved, at a fraction of the cost.**

**This is not assumed to be a free win.** The existing mechanism's own
full re-screening captures something the localized version discards:
whether an edge's own candidacy is itself stable under resampling (an
edge that easily drops out of the screened set on a resample is
informationally different from one that stays in but fails deeper
conditioning). Freezing candidacy and the conditioning set from the
original data is a real methodological simplification, not a neutral
optimization -- whether the resulting `pi_final` still discriminates
correct from incorrect decisions as well as the full-repeat version is
exactly the open, testable question this charter exists to answer, not
a premise it assumes.

## Mechanism

**Step 1 -- build the mechanism**, reusing the already-validated
single-test primitive rather than the full search:

New function, `mintnet.bootstrap.stability.compute_edge_stability_
localized_structured_density(data, qualifying_pairs, conditioning_
sets, dpi_alpha, bootstraps, master_seed, degree, ridge_lambda, cv_
folds, k_perm, permutations, rng, *, n_jobs="auto")` -- `qualifying_
pairs` and `conditioning_sets` (a `dict[(i,j), tuple[int,...]]`) come
from the CALLER's own already-completed point estimate, frozen for
every resample. Per resample: row-resample `data` (identical resample
construction to the existing mechanism's own `bootstrap_resample`), then
for each qualifying pair call `mintnet.mi.structured_density.local_
permutation_test(resample[:, i], resample[:, j], resample[:, list(S)],
degree=..., ridge_lambda=..., cv_folds=..., k_perm=..., permutations=
...)` directly against its OWN frozen conditioning set `S` -- no
re-screening, no re-running the growing-subset search, no
recomputation for any non-qualifying pair. `pi_final[(i,j)]` = fraction
of resamples where this direct test rejects independence (retains the
edge). Reuses `_resolve_n_jobs`/`_AUTO_N_JOBS_CAP` (D-081) unchanged.

New function, `mintnet.pipeline.stability_rescue.growing_subset_dpi_
structured_density_with_localized_rescue(...)` -- identical wiring to
the existing `..._with_stability_rescue`: run the point estimate once,
identify qualifying pairs (`conditioning_size_used >=
UNRESOLVED_CONDITIONING_SIZE`), call the new localized bootstrap
instead of the existing full-repeat one, flip retain -> prune below
`pi_min`. Purely additive; the existing mechanism is NOT removed or
replaced -- both remain available, this charter decides whether the
localized one is trustworthy enough to prefer for practical use.

**Step 2 (REQUIRED before any evidence run) -- measure the actual
speedup directly**, on the same real `overlap` dataset/conditions that
triggered this charter (a fresh sample, `N=750`, `strength=0.5`,
`enable_rescue`-style conditions matching `mintnet.api.discover`'s own
call pattern), comparing wall-clock cost of the existing full-repeat
mechanism against the new localized one, same `B`, same hardware, same
`n_jobs="auto"`. **This charter's entire premise is a cost claim; that
claim gets measured before anything else is built on top of it, not
asserted from the mechanism's own design.**

**Step 3 -- calibrate `pi_min` fresh, not inherited from D-087.** The
localized statistic is a different quantity computed a different way
than the full-repeat `pi_final` D-087 calibrated against -- there is no
basis to assume the same threshold, or even the same shape of
threshold behavior, transfers. Reuse the established procedure exactly
(development/validation split by replicate parity, grid `{.50, .60,
.70, .80, .90}`, smallest value clearing recall `>=.95`/removal
`>=.85` on development, confirmed on validation, per-`(dgp, N)` cell
using `calibrate_and_validate_per_cell` -- D-086's own fix, applied
from the start this time, not discovered as a bug after the fact).

**Step 4 -- validate recall/removal on fresh evidence, on BOTH DGPs,
not just the one that already PROCEEDed.** Mirrors D-087's own
end-to-end design (fresh, disjoint seed range from every prior
charter's own usage) -- but critically, **`overlap` is tested head-on
this time, not deferred as evidence-scarce.** The entire point of this
charter is making `overlap`'s own rescue calibration tractable; a
charter that PROCEEDs for `chain_fork_hub` alone while still failing
to gather enough `overlap` evidence would not have answered the
question it was chartered to answer.

## Data-generating processes

`chain_fork_hub`, `overlap` (`stage5a._DGP_REGISTRY`), `strength=0.5`,
`N in {750, 1500}` -- same scope as Stage 9c/D-087, deliberately
unchanged so any difference in outcome is attributable to the
mechanism, not a moved target. Replicate count and any further scope
narrowing decided after Step 2's own real cost measurement, exactly
as Stage 9c's own precedent required and this charter repeats
deliberately.

## Compute-cost disclosure

**The entire premise of this charter is an unconfirmed cost claim.**
Step 2 is a hard prerequisite: if the localized mechanism's own actual
measured speedup on a real `overlap` dataset is not substantial
(provisionally: at least an order of magnitude faster than the
existing full-repeat mechanism under the same conditions), this
charter reports that directly as a REASSESS reason and does not
proceed to Steps 3-4, rather than validating a mechanism that solves a
problem too small to matter. If Step 2 confirms a real speedup, this
charter's own evidence generation should still use the sharded GitHub
Actions workflow per this project's own standing precedent, not local
multiprocessing, at whatever `B`/replicate count Step 2's own
measurement supports.

## Selection and gate

**PROCEED** only if, at EVERY tested `(dgp, N)` cell (`chain_fork_hub`
AND `overlap`, both tested `N`) with at least `10` qualifying
instances in both the development and validation halves (D-086's own
corrected per-cell, per-half requirement -- not the pooled check an
earlier draft of Stage 9c's own report generator mistakenly used
before that bug was caught), the calibrated `pi_min` achieves recall
`>= 0.95` and removal `>= 0.85` on held-out evidence, AND Step 2's own
real cost measurement shows a substantial (provisionally `>= 10x`)
speedup over the existing full-repeat mechanism. **REASSESS**
otherwise -- explicitly including the case where calibration succeeds
but the speedup does not materialize, and the case where the speedup
is real but calibration fails (meaning freezing candidacy/conditioning
set actually did discard information the mechanism needed). Both are
informative, disclosed outcomes, not failures to hide.

## Explicit non-goals

- **No assumption that discarding re-screening is informationally free.**
  This charter treats that as the central open risk, not a premise --
  see Background.
- **No claim beyond `chain_fork_hub`/`overlap` at `strength=0.5`,
  `N in {750, 1500}`** -- identical scope boundary to D-087, for the
  same reasons.
- **No re-tuning of `degree`, `k_perm`, or any other structured-density
  estimator parameter** -- `degree=1` inherited unchanged from D-063,
  matching Stage 9c's own non-goal.
- **No removal or deprecation of the existing full-repeat mechanism**,
  even on a full PROCEED -- both remain available; this charter only
  decides whether the localized one is ALSO trustworthy, as a cheaper
  option for cases (like dense real networks) where the existing one is
  impractical.
- **No production deployment authorization.**

## Required evidence

This charter's SHA-256, commit and runtime metadata, Step 2's own
head-to-head timing measurement (both mechanisms, same conditions,
reported even if the charter REASSESSes on cost alone), Step 3's own
calibration procedure and selected `pi_min` per cell, Step 4's own raw
per-edge evidence and recall/removal table for all four `(dgp, N)`
cells, the gate decision, and a report.

## Consequences

**If PROCEED**: `mintnet.api.discover`'s own `enable_rescue` path can
switch to the localized mechanism as its default rescue implementation
(a separate, later decision -- this charter only validates that it
CAN be trusted, not that it automatically becomes the default), making
rescue practical for real, densely-connected networks for the first
time -- directly closing the usability gap this session's own attempt
to demo `discover()` surfaced.

**If REASSESS on calibration**: freezing candidacy/conditioning set
discards information the mechanism actually needs, meaning the
existing full-repeat mechanism's own cost is not an accident of
implementation but reflects real necessary work -- motivating a search
for a different cost-reduction strategy (e.g. reducing `B` further,
or a smarter resampling scheme that partially re-screens) as separate
future work, not a smaller version of this same design.

**If REASSESS on cost** (the speedup does not materialize): the
re-screening/re-search step was not, in fact, the dominant cost driver
for a dense network -- an informative, surprising result in its own
right, redirecting the search for a cheaper mechanism toward whatever
step actually dominates (measured directly in Step 2, not guessed).
