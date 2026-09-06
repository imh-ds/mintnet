# Stage 7e Charter: Structured-Density Growing-Subset DPI — Retrying Stage 7's Isolation Gate (mi-native)

Status: **FROZEN before results**
Date: 2026-09-06

## Background and objective

Stage 7 (docs/stage7_charter.md) composed the calibrated CMIknn/local-
permutation test into `growing_subset_dpi`'s own search architecture
and REASSESSed (D-059, revised): a structural conflict on the
`strong` triangle fixture's own weak edge (`target_rho=-0.08`) meant
no `alpha` simultaneously satisfied the chain/fork pruning floor and
the triangle retention floor. Stage 7b (D-060) mapped how that limit
shrinks with `N`; Stage 7c (D-061) found a calibrated `k_CMI=80`
retuning that narrows the gap substantially without closing it.

**Stage 7d (D-062) changes the picture.** Head-to-head against the
CMIknn baseline on the identical `weak_edge_triangle` family (the same
generative structure as the `strong` fixture, with the weak edge swept
continuously), the structured conditional-density estimator resolves
`target_rho=0.08` outright at `degree=1`: at `N=3000`, a feasible
`alpha` exists from as low as `.02` (pruning rate `.98`, power `.90`);
at `N=1500`, feasible from `alpha=.19` (pruning rate `.82`, power
`.90`). This is precisely the case CMIknn could never resolve at any
tested `k_CMI` (D-061's own best attempt needed `alpha=.5` — the most
permissive setting tested — and still failed the pruning side
simultaneously).

**This charter asks the direct question that finding motivates**: does
composing the structured-density estimator into the same growing-
subset search architecture let Stage 7's own isolation-tier gate
PROCEED, where the CMIknn version REASSESSed? Same architecture, same
gate, same fixtures — one substitution, mirroring exactly how Stage 7
itself substituted CMIknn for Fisher-z.

**Explicit caveat, stated up front rather than assumed away**: D-062's
own resolution of `target_rho=0.08` was measured on
`sample_weak_edge_triangle`, not on the `strong` **named** fixture's
own exact precision matrix used by Stage 7's isolation tier (the two
are numerically identical at `target_rho=0.08` — see
`test_weak_edge_triangle_matches_strong_fixture_at_target_rho_point_
zero_eight` — but Stage 7's own gate also requires chain/fork/
`balanced`/`moderate` performance, none of which D-062 directly
tested, and D-062 swept `degree` only against the weak-edge pair in
isolation, not inside a full growing-subset search). **This charter
does not assume D-062's `degree=1` finding transfers untested** — see
the up-front calibration-transfer check below.

## Mechanism

A new function, `mintnet.pipeline.growing_subset_dpi_structured_
density`, structurally identical to `growing_subset_dpi_mi`'s own
search logic (same connected-component pooling, same size-1-first
OR-rule, same search-depth cap of `4`, same `cap_reached` bookkeeping)
with one substitution: each per-subset conditional-independence test
calls `mintnet.mi.structured_density.local_permutation_test(data[:,i],
data[:,j], data[:,subset], degree=<calibrated>, rng=...)` in place of
CMIknn's own `local_permutation_test`, retaining the edge if `p_value
<= alpha`. Neither `growing_subset_dpi` nor `growing_subset_dpi_mi` is
modified — this is additive, mirroring how Stage 7 itself added a
module beside `growing_subset_dpi` rather than editing it.

**RNG determinism**: identical requirement and construction to Stage
7's own — each per-subset test's `rng` derives from
`SeedSequence([master_seed, replicate, i, j, sorted(subset)])`, a pure
function of already-known, full-grid quantities.

**Search-depth cap**: `4`, unchanged from Stage 6a/Stage 7's own
disclosed choice.

## Up-front calibration-transfer check (required before the main run)

Before committing to `degree=1` (D-062's own best performer on the
`weak_edge_triangle`/linear family) as this charter's operating
setting, run Stage 6c/7c's own calibration-filter check —
`target_rho=0`-equivalent null cells (chain/fork's own indirect-edge
null structure, and the triangle families' own null-adjacent
behavior) — directly on Stage 7's isolation-tier fixtures
(`sample_chain`, `sample_measured_fork`, `sample_precision_triangle`
at `balanced`/`moderate`/`strong`), not re-derived from
`weak_edge_triangle`. Bracket `degree in {1, 2, 3}` (D-062's own
finding that higher degrees add no benefit on linear/curvature data
justifies not re-testing `4`). If `degree=1` fails this check on
Stage 7's own fixtures, the next calibrated value (per D-056's own
established defensibility criterion) becomes this charter's operating
setting instead — disclosed in the report either way, exactly as
Stage 7c disclosed `k_CMI=40`'s own surprising calibration failure.

## Data-generating processes

Identical to Stage 7's own two tiers, unchanged, for direct three-way
comparability (this mechanism vs. Stage 7's own CMIknn version vs.
Stage 6a's growing-subset partial-correlation DPI vs. Stage 1's
original):

**Isolation tier (falsification core, this charter's own PROCEED/
REASSESS gate):** chain and measured fork (retain adjacent edges, prune
the indirect pair); triangle `balanced`/`moderate`/`strong` (retain
all three edges); `N in {750, 1500}`; strengths `a=b=[.3,.5,.7]`.

**Composed tier (required evidence, comparative, non-gating):**
`chain_fork_hub` and `overlap`, `p=15`, `N in {750, 1000, 1500, 1750}`,
paired against D-053's own growing-subset partial-correlation baseline
and Stage 7's own CMIknn-based composed-tier evidence where available.

**`alpha` selection**: Stage 1b's own frozen grid `[.50, .30, .20,
.10, .05, .01, .005, .001, .0001]` and development/validation split
structure, unchanged from Stage 7's own. **Disclosed limitation,
inherited unchanged**: `permutations=199` gives a minimum resolvable
p-value of `1/200=.005`; grid points below that cannot be distinguished
from each other by this test at this `B`.

## Compute-cost disclosure

**Isolation tier**: real per-replicate cost already measured this
session for the 3-node case (D-062's own evidence run) — `degree in
{1,2,3}` at `N in {750,1500,3000}` cost `5.6s`-`9.3s` per 3-pair
evidence computation, roughly `10-15x` cheaper than CMIknn's own
equivalent. Since a chain/fork/triangle motif's own isolation-tier
search has pool size `1` per pair (no combinatorial subset search,
identical to Stage 7's own isolation tier), this cost transfers
directly — no new isolation-tier timing measurement is required,
unlike Stage 7's own charter (which had no prior structured-density
timing data to draw on).

**Composed tier**: cost is NOT assumed to transfer from the isolation
tier — a `p=15` network's own growing-subset search visits many more
candidate subsets per replicate than a 3-node motif's fixed single
subset, and this charter's own new `growing_subset_dpi_structured_
density` function has never been run at that scale. Per this project's
own standing discipline: measure real per-replicate wall-clock cost of
the *entire* growing-subset-DPI-with-structured-density pipeline
(not just a single significance test) on at least one composed-tier
cell, at the smallest and largest `N` in scope, before finalizing the
composed tier's own replicate count or shard plan. A provisional
planning figure (not a commitment): comparable order of magnitude to
Stage 7's own composed-tier plan, likely somewhat cheaper given the
structured-density estimator's own lower per-test cost — resolved
after direct measurement, not assumed.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** —
unchanged, hard requirement, per this project's own established
practice.

## Selection and gate

**PROCEED** (isolation tier only, mirroring Stage 7's own gate
exactly) only if the selected `alpha` meets every validation-replicate
cell at each `N in {750, 1500}` and strength:

1. Chain and fork indirect-edge pruning TPR each at least `0.80`.
2. Triangle true-edge retention FPR (each of the three edges, all
   three families) at most `0.10`.
3. No estimator, DGP, permutation-construction, or numerical error is
   recorded.

**REASSESS** otherwise.

**Composed tier is required evidence, not a second gate**, mirroring
Stage 7's own: F1 comparable-to-or-better than D-053's own baseline
(within `.01`, majority of tested `N`), an explicit recall-cost
sentence regardless of the answer, and the conditioning-set-size
distribution compared against both D-053's own and, where available,
Stage 7's own CMIknn-composed-tier distribution.

## Explicit non-goals

- **No screening change.** Unchanged from Stage 7's own reasoning —
  mechanism-by-mechanism discipline, and bivariate MI/Fisher-z are the
  same monotonic test on Gaussian data, so nothing would be learned.
- **No nonlinear or non-Gaussian DGP.** Every fixture here remains
  Gaussian, exactly as Stage 7's own scope note explains — this
  charter tests whether the composition mechanism itself works, using
  the estimator D-062 found more sample-efficient on this data, not
  MI's own nonlinear value proposition (Stage 7d already tested that
  question directly, separately, via the U-shape diagnostic).
- **No re-litigation of D-062's own head-to-head finding.** That
  comparison stands; this charter only asks whether its result
  transfers into the full search architecture and Stage 7's own exact
  gate fixtures.
- **No claim about production readiness**, even on a clean PROCEED —
  a separate, explicit decision, unchanged from Stage 7's own framing.
- **No resolution of the `alpha<.005` permutation-resolution limit.**
- **No `N<750` claim for any `|S|>=3`-dependent shape.**

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the up-front calibration-transfer check and its resulting
`degree` decision, the composed tier's own up-front timing measurement
and resulting replicate-count decision, raw per-replicate evidence for
both tiers, the isolation tier's own gate decision, the composed
tier's own comparison tables against D-053 and (where available)
Stage 7's own CMIknn-composed-tier evidence, and a report.

## Consequences

**If PROCEED (isolation tier)**: `mi-native` has its first validated,
working end-to-end MI-based conditional-independence mechanism —
succeeding specifically where Stage 7's own CMIknn version REASSESSed,
on the identical gate and fixtures. Next named steps become live: (a)
a nonlinear/non-Gaussian validation charter (this project has still
never tested MI's actual nonlinear advantage inside the full DPI
mechanism, only in Stage 7d's own isolated diagnostic); (b) an
MI-based screening charter; (c) a separate decision about production
availability alongside `v1-partial-correlation-baseline`.

**If REASSESS**: diagnose whether the failure is in the search
architecture (already validated independently in Stage 6a/Stage 7 —
unlikely) or in an interaction specific to embedding the structured-
density test inside a multi-subset search (e.g. cross-fitting fold
noise compounding across repeated calls the way permutation noise did
for CMIknn) — the up-front calibration-transfer check's own result is
the most direct diagnostic for distinguishing an estimator-transfer
problem from a search-architecture problem before writing a follow-up
charter.
