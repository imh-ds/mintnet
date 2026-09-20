# Stage 9b Charter: Wiring Tier-1 Bootstrap-Stability Into an Opt-In Pipeline Feature (main)

Status: **FROZEN before results**
Date: 2026-09-09

## Background and objective

D-076 established a precise, actionable asymmetry: `growing_subset_
dpi`'s own retain decisions are reliable at every conditioning depth;
its own prune decisions are reliable only at `conditioning_size_used
<= 1` and genuinely broken (not merely miscalibrated) at `>= 2`. D-077
through D-079 then validated, entirely retrospectively (post-hoc
analysis of already-generated evidence), that bootstrap edge-stability
(`pi_final`, `B=500` row bootstraps) separates correctly- from
incorrectly-resolved decisions specifically within that broken regime,
and that a `pi_min=0.90` filter recovers `.99` removal of wrongly-
retained false edges at a `.998` recall cost on true edges.

**What does not exist yet: a single function a caller can actually
use.** Every piece is validated in isolation --
`mintnet.pipeline.growing_subset_dpi.growing_subset_dpi` (the base
decision), `mintnet.bootstrap.compute_edge_stability_growing_subset`
(the stability check) -- but nothing wires them together. A caller
today would have to manually: run `growing_subset_dpi`, inspect
`conditioning_size_used` per edge, decide which ones qualify, call
`compute_edge_stability_growing_subset` themselves with the right
arguments, and apply the `pi_min` cut by hand. This charter builds and
validates that wiring as one function, end-to-end, on fresh evidence --
not a re-analysis of data Stage 9a already scored.

**Why fresh evidence, not a re-analysis.** D-077/D-078's own numbers
came from evidence Stage 8c generated for an unrelated purpose,
filtered and analyzed after the fact. This charter's own job is
different: confirm that calling the new wired function directly,
end-to-end, on data it has never seen scored before, reproduces
comparable recall/removal numbers -- the actual claim a future caller
would rely on, not merely "the underlying statistic works when
computed carefully by hand."

## Mechanism

**Step 1 -- implement the wired function (additive, no change to
`growing_subset_dpi`'s own existing behavior or return type).**

New function, `growing_subset_dpi_with_stability_rescue` (module TBD at
implementation time, e.g. `mintnet.pipeline.stability_rescue`):

```
growing_subset_dpi_with_stability_rescue(
    data, flagged, alpha, *,
    max_conditioning_size=4, motif_family=None,
    screening_alpha, bootstraps=500, pi_min=0.90, rng,
) -> StabilityRescueResult
```

Internally: (1) run `growing_subset_dpi` once, exactly as today; (2)
identify every edge with `conditioning_size_used >= 2` (D-076's own
"unresolved" boundary) -- these are the ONLY edges ever bootstrapped,
matching Stage 9a's own already-validated efficiency design (a
replicate with multiple qualifying edges pays the `B` resample cost
once, not once per edge, since `compute_edge_stability_growing_subset`
returns the full `p x p` matrix in one pass); (3) for datasets with at
least one qualifying edge, run `compute_edge_stability_growing_subset`
once and read off `pi_final` for each qualifying pair; (4) build a
`final_adjacency`: identical to the original for every edge that never
qualified (unresolved-tier edges only), and flipped to pruned for any
qualifying edge whose `pi_final < pi_min`.

`StabilityRescueResult` exposes, per edge: the original decision, the
final (possibly corrected) decision, `conditioning_size_used`,
`pi_final` (`NaN` if never bootstrapped), and a `rescued: bool` flag
(`True` only for edges the filter actually flipped) -- full
transparency about what changed and why, not a silent correction.

**Step 2 -- end-to-end validation on fresh replicates.** Using the
same `chain_fork_hub`/`overlap` DGPs, `strength=0.5`, `screening_
alpha=0.001`, `max_conditioning_size=4`, `N in {400,...,1750}` this
whole investigation has used throughout, draw **new** replicates (a
disjoint seed range from every prior Stage 8/9 charter's own usage, so
this is not the same data re-scored) and call the wired function
directly. Compare, per `(dgp, N)`: (a) raw point-estimate accuracy at
`conditioning_size_used >= 2` (should reproduce D-076's own
degraded-accuracy numbers, confirming the fresh evidence behaves like
the old); (b) `final_adjacency`'s own accuracy in that same population
after rescue (should show the same order-of-magnitude improvement
D-077/D-078 already found: recall near `1.0` on true edges, most
wrongly-retained false edges corrected). **Confirmed** if the wired
function's own end-to-end numbers land within a predeclared tolerance
(recall `>= .95`, removal rate `>= .85`, chosen slightly looser than
D-079's own `.998`/`.99` to allow for fresh-sample noise) of D-079's
own retrospective figures, on this new evidence.

**Step 3 -- measure the wired function's own real per-call cost.**
Not every dataset will contain a qualifying edge (D-076's own count:
roughly `2%` of edge decisions reach `conditioning_size_used >= 2`);
report, separately, the function's own typical call cost (i) when no
edge qualifies (should be indistinguishable from plain `growing_
subset_dpi`) and (ii) when at least one does (pays the full `B=500`
cost once). Reuse Stage 9a's own hard-won lesson: measure under
whatever execution environment the reported number is meant to
represent, not an unthrottled convenience measurement.

## Data-generating processes

`chain_fork_hub`, `overlap` (`stage5a._DGP_REGISTRY`), `strength=0.5`,
`screening_alpha=0.001`, `max_conditioning_size=4`, `N in {400, 500,
600, 750, 1000, 1500, 1750}` -- identical to every prior Stage 8/9
charter, on newly-drawn replicates only (a fresh seed range,
disclosed and reported, disjoint from every replicate index any prior
charter has used for these DGPs at this `strength`).

## Compute-cost disclosure

Per-call cost is now known to be highly variable and not well-predicted
by `N` (Stage 9a's own measured range: `~18s` to `~280s` per `B=500`
bootstrap run, depending on execution environment and how tangled the
specific replicate's own screened component happens to be) --
**measure this charter's own realistic per-call cost distribution
directly (Step 3) rather than assuming a number**, and report it
plainly as part of this feature's own documentation, not just this
charter's own evidence.

## Selection and gate

**PROCEED**: Step 2's own tolerance is met at every tested `(dgp, N)`
cell with enough qualifying edges to evaluate (mirrors this project's
own precedent for sparse-cell handling: report, don't force, cells
without enough data). The wired function becomes an available,
documented, **opt-in** pipeline feature -- default `growing_subset_
dpi` behavior is unchanged; a caller must explicitly choose to call the
new function.

**REASSESS**: Step 2's own tolerance is not met somewhere -- the
retrospective Stage 9a findings do not reproduce end-to-end on fresh
data as directly as expected, and the wired function is not released
as a documented feature until that gap is understood.

## Explicit non-goals

- **No change to `growing_subset_dpi`'s own default behavior or return
  type.** The new function is entirely additive; existing callers are
  unaffected.
- **No claim beyond `chain_fork_hub`/`overlap` at `strength=0.5`, `N in
  [400, 1750]`** -- identical scope discipline to every prior Stage 8/9
  charter. No claim for isolated-tier motifs, other strengths, other
  `max_conditioning_size` values, or arbitrary real (non-synthetic)
  data.
- **No automatic/default-on deployment**, even on a full PROCEED. This
  charter authorizes the function's own existence as an opt-in tool a
  caller can choose to use, scoped to the tested conditions -- it does
  not authorize making stability-rescue the default behavior of any
  existing pipeline entry point, and does not resolve whether the
  `B=500` cost is acceptable for any particular caller's own use case.
- **No new statistical claim about `pi_final`'s own separating power or
  the `pi_min=0.90` threshold's own recall/removal rate** -- those are
  D-077/D-078/D-079's own findings; this charter only tests whether
  wiring them into one callable function reproduces those findings
  end-to-end, on fresh data.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the fresh
replicate seed range used (disclosed, disjoint from every prior
charter's own usage), raw per-edge evidence (original decision, final
decision, `conditioning_size_used`, `pi_final`, `rescued`, ground
truth) for every swept `(dgp, N)` cell, the Step 2 comparison table
against D-079's own retrospective numbers, the Step 3 timing
measurement, the gate decision, and a report.

## Consequences

**If PROCEED**: `growing_subset_dpi_with_stability_rescue` becomes a
documented, opt-in feature -- the first concrete answer to "how do I
actually use this" for the asymmetry D-076 identified, within its own
tested scope. Motivates (as a separate, not-yet-decided future step) a
production-integration decision for whichever downstream tool or
report currently calls `growing_subset_dpi` directly, weighing the
`B=500` cost this charter measures but does not resolve.

**If REASSESS**: the retrospective findings do not transfer cleanly to
a direct, end-to-end call on fresh data -- worth understanding why
before releasing anything as a usable feature, since a caller would be
relying on the wired function's own real behavior, not the underlying
statistic's own already-demonstrated validity in isolation.

## Addendum (post-freeze, 2026-09-09 -- does not alter anything above)

This charter's own text above is frozen and unedited; PROCEED was
recorded in D-080 before this note was added. Recorded here only as a
pointer, per this project's own "corrections are appended, not silent
edits" discipline: D-081 (a separate, non-chartered engineering change
-- `n_jobs` cannot affect any result, only wall-clock time) added
opt-in local parallelism to `growing_subset_dpi_with_stability_rescue`
and its own underlying bootstrap functions, defaulting to
`n_jobs="auto"` (`min(os.cpu_count(), 8)`, measured at `~5x` speedup on
a 20-core machine). This charter's own Step 3 compute-cost disclosure
(`~80-280s` per qualifying dataset, measured sequentially under GitHub
Actions' thread limits) is unaffected and remains the correct sequential
figure -- D-081 only gives a caller who wants it a documented, opt-in
way to reduce that wall-clock cost locally. See D-081 in
`docs/decision_log.md` and its own entry in
`docs/validated_operating_ranges.md`.
