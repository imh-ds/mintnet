# Stage 7 Charter: MI-Based Growing-Subset DPI — the First End-to-End MI Mechanism (mi-native)

Status: **FROZEN before results**
Date: 2026-09-03

## Background and objective

This is `mi-native`'s own Stage-1-equivalent: the first mechanism
charter that composes previously-validated pieces into an actual
conditional-independence retain/prune decision, rather than validating
a piece in isolation. D-053, D-054, and D-056 each named this as the
explicit next step once their own prerequisites were met:

- **The estimator and significance test** (`mintnet.mi.cmiknn`):
  point-estimate accuracy confirmed (D-054), local-permutation
  Type-I error control confirmed after a construction fix (D-056),
  power confirmed with one disclosed operating-range caveat (D-057).
  Calibrated operating setting: `k_CMI=40`, `k_perm=3`,
  `permutations=199`.
- **The conditioning-set architecture** (`mintnet.pipeline.growing_
  subset_dpi`): a PC-style growing-conditioning-set search (size 1,
  escalate only on non-rejection, OR-rule) validated on
  `main`/partial-correlation to match-or-beat full-component
  conditioning with zero measured recall cost, using conditioning
  dimension up to `3` in a real minority of cases (D-053).

This charter combines them: **the same growing-subset search
architecture D-053 validated, with the per-subset conditional-
independence test replaced by the calibrated CMIknn/local-permutation
test instead of Fisher-z partial correlation.** Screening stays
Fisher-z (unchanged) — see the explicit scope note below for why.

**Scope note — this is a Gaussian-equivalence check, structurally
identical to Stage 1b's own framing.** Under jointly Gaussian data,
`I(X;Y|Z)` is a strictly monotonic function of partial correlation
(`I = -0.5*ln(1 - r_XY.Z^2)`), and every DGP available in this
project's own validated motif/network registry is Gaussian. This
charter therefore cannot, and does not claim to, test MI's actual
value proposition (nonlinear/non-Gaussian dependence the Fisher-z
mechanism would miss) — it tests whether a *correctly implemented*
CMI-based version of the same architecture reproduces the
mathematically-expected equivalent performance on data where the two
approaches should agree. A materially worse result here would mean
something is wrong with the composition (estimator noise, permutation-
test resolution, an interaction between the search architecture and
the new test's own coarser p-value granularity), not that MI is
inferior in principle. A nonlinear/non-Gaussian validation charter,
where MI's actual claim gets tested, remains separate future work,
contingent on this charter's own PROCEED.

## Why screening stays Fisher-z

Screening (`compute_pairwise_screening_evidence`, bivariate) is left
unchanged for two reasons stated up front, not discovered after the
fact: (1) mechanism-by-mechanism discipline — this charter changes one
thing (DPI) at a time, mirroring how Stage 1 originally built DPI on
top of an already-fixed screening step; (2) on Gaussian data, bivariate
MI and Fisher-z correlation are the same monotonic test (Stage 0/D-001
already operates in this regime), so swapping screening now would
produce numerically equivalent results to Fisher-z screening and
teach nothing — the same reasoning that has kept every prior R6/mi-
native charter Gaussian-only. An MI-based screening swap is separate,
smaller future work, useful primarily once a non-Gaussian DGP is in
scope.

## Mechanism

A new function, structurally identical to `growing_subset_dpi`'s own
search logic (same connected-component pooling, same size-1-first
OR-rule, same search-depth cap, same `cap_reached` bookkeeping) with
one substitution: each per-subset conditional-independence test calls
`mintnet.mi.cmiknn.local_permutation_test(data[:,i], data[:,j],
data[:,subset], k=40, k_perm=3, permutations=199, rng=...)` in place
of `compute_partial_correlation_evidence`, retaining the edge if
`p_value <= alpha`. `growing_subset_dpi` itself is not modified —
this is additive, mirroring how Stage 6a added its own module beside
`compose_screen_then_prune` rather than editing it.

**RNG determinism**: every per-subset permutation test needs its own
reproducible seed (unlike Fisher-z, which is a deterministic function
of the data alone). Each test's `rng` is derived from
`SeedSequence([master_seed, replicate, i, j, sorted(subset)])` — a
pure function of already-known, full-grid quantities, not of search
order or which shard runs it, so a sharded run's results are
bit-identical to an unsharded run's for the same cell (the same
requirement every prior sharded runner in this project has satisfied).

**Search-depth cap**: `4`, unchanged from Stage 6a/D-053's own
disclosed choice (one step of headroom beyond the largest validated
dimension, `3`).

## Data-generating processes

Two tiers, mirroring Stage 6a's own isolation-then-composed structure
and Stage 1/1b's own original falsification suite, for direct,
three-way comparability (this mechanism vs. Stage 1's original
partial-correlation DPI vs. Stage 6a's growing-subset partial-
correlation DPI):

**Isolation tier (falsification core, this charter's own PROCEED/
REASSESS gate):**
- Chain (`X1 -> X2 -> X3`) and measured fork (`X1 <- X2 -> X3`):
  retain `(1,2)`/`(2,3)`, prune `(1,3)`. Identical to Stage 1's own
  chain/fork fixtures.
- Triangle (`balanced`/`moderate`/`strong` precision fixtures):
  retain all three edges. Identical to Stage 1's own triangle
  fixtures.
- `N in {750, 1500}` (D-057's own operating-range floor — `|S|=1`
  conditioning, as these motifs need, already had 100% power at
  `N=300` per D-057, but `N=750` is used here anyway for consistency
  with Stage 6a's own isolation-tier grid and this charter's own
  composed tier, not because chain/fork specifically demand it).
  Strengths `a=b=[.3,.5,.7]`, matching Stage 1's own grid.

**Composed tier (required evidence, comparative, non-gating — mirrors
Stage 6a's own composed tier, which was descriptive, not a second
gate):** `chain_fork_hub` and `overlap`, `p=15`, `N in {750, 1000,
1500, 1750}` (D-057's own floor applied: the `400`-`600` range Stage
5/6a tested is dropped here, since `overlap`'s own true edges include
`|S|=3`-depth pairs that D-057 found underpowered below `N=750`),
paired against D-053's own growing-subset partial-correlation
baseline and, where available, D-051's PC baseline — same DGP
registry, `alpha(N)` formula, and condition-seed derivation as
D-047/D-051/D-052/D-053 (unchanged, not re-derived).

**`alpha` selection**: reuses Stage 1b's own frozen grid `[.50, .30,
.20, .10, .05, .01, .005, .001, .0001]` and development/validation
split structure (development selects the lexicographically lowest
adjacent pair meeting the gate pooled across strengths/motifs at
`N>=750`; validation replicates cannot alter selection). **Disclosed
limitation, inherited from D-054/D-055's own**: `permutations=199`
gives a minimum resolvable p-value of `1/200=.005` — grid points below
that (`.001`, `.0001`) cannot be distinguished from each other by this
test at this `B`, and will show identical or near-identical behavior
by construction, not a finding about those specific alpha values.
This is stated up front so it is not later mistaken for evidence about
extremely small alphas specifically.

## Compute-cost disclosure and required infrastructure

**This charter's single largest risk is compute cost, disclosed here
rather than discovered mid-run**, per this session's own recent,
direct experience: a single `local_permutation_test` call at the
calibrated setting costs single-digit-to-tens of seconds depending on
`N` (measured directly in Stage 6c/6d: ~9s at `N=750`, `k_CMI=40`).
Growing-subset DPI calls this **once per tested subset, per candidate
edge** — Stage 6a's own isolation-tier grid (`2,000` replicates) was
sized for a test costing microseconds (Fisher-z); repeating that scale
here is not assumed affordable and is not this charter's own starting
plan.

**Before any full grid is run**: measure real per-replicate wall-clock
cost of the *entire* growing-subset-DPI-with-CMI pipeline (not just a
single significance test) on each isolation-tier motif and at least
one composed-tier cell, at the smallest and largest `N` in scope, and
use that measurement — not an assumption — to size the actual
replicate count. A provisional planning figure (not a commitment):
isolation tier `100`-`300` replicates per cell (an order of magnitude
below Stage 6a's `2,000`, matching Stage 6c/6d's own null-calibration
scale), composed tier sized after the same measurement, likely lower
still given `p=15`'s larger candidate graphs. Any reduction from a
larger, previously-assumed figure must be disclosed in the runner's
own module docstring, exactly as Stage 6b/6c disclosed their own
scope reductions — never silently substituted.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow (`sharded_benchmark.yml`), not local multiprocessing,
from the first run — not as a fallback after a local attempt runs into
trouble.** This is a hard requirement, not a preference, given this
session's own direct experience with both severe multi-process
contention on a single machine and the basic issue of a multi-hour
local run occupying the user's own machine regardless of speed. Every
runner this charter's implementation produces must satisfy the
existing generic shard-aggregation contract
(`load_config`/`expected_row_count`/`expected_combinations`/
`COMBINATION_COLUMNS` plus a `<module>_reporting` companion) from the
start.

## Selection and gate

**PROCEED** (isolation tier only — the falsification core, mirroring
Stage 1's own original gate exactly) only if the selected `alpha`
meets every validation-replicate cell at each `N in {750, 1500}` and
strength:

1. Chain and fork indirect-edge (`X1`,`X3`) pruning TPR each at least
   `0.80`.
2. Triangle true-edge retention FPR (each of the three edges, all
   three families) at most `0.10`.
3. No estimator, DGP, permutation-construction, or numerical error is
   recorded.

**REASSESS** otherwise. This stage does not select a public default
`alpha` or authorize any production pipeline change on its own.

**Composed tier is required evidence, not a second gate** (mirrors
Stage 6a's own composed tier): report, per shape and `N`, (a) F1
comparable-to-or-better than D-053's own growing-subset partial-
correlation baseline (within `.01`, majority of tested `N` — this
project's own established tolerance), (b) an explicit recall-cost
sentence regardless of the answer (mirroring D-051's own PC finding
and Stage 6a's own recall check), (c) the conditioning-set-size
distribution actually used, compared directly to D-053's own recorded
distribution for the same shapes — a real divergence here (not just a
similar one) would itself be a finding worth its own discussion, since
the two mechanisms are expected to agree closely under Gaussian data.

## Explicit non-goals

- **No screening change.** See "Why screening stays Fisher-z" above.
- **No nonlinear or non-Gaussian DGP.** This charter's own scope note
  states plainly why: no closed-form reference exists for this
  project's own validated Gaussian-equivalence framing to check
  against on such data. Separate future work, contingent on PROCEED.
- **No claim about production readiness.** Even a clean PROCEED here
  validates the mechanism's own correctness on Gaussian data — it does
  not, on its own, authorize replacing `compose_screen_then_prune` in
  any live pipeline. That would be a separate, explicit decision.
- **No resolution of the `alpha<.005` permutation-resolution limit.**
  Disclosed above, unchanged from D-054/D-055's own deferral.
- **No `N<750` claim for any `|S|>=3`-dependent shape.** Per D-057.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the up-front timing/feasibility measurement and its own
resulting (possibly reduced) replicate-count decision, raw per-
replicate evidence for both tiers, the isolation tier's own gate
decision, the composed tier's own comparison tables/figures against
D-053, and a report.

## Consequences

**If PROCEED (isolation tier)**: `mi-native` has a validated, working
end-to-end conditional-independence mechanism on Gaussian data. Next
named steps become live: (a) a nonlinear/non-Gaussian validation
charter, where MI's actual advantage over correlation would finally be
tested; (b) an MI-based screening charter, completing the swap this
charter deliberately deferred; (c) a decision (separate from this
charter) about whether/how to eventually offer this as a production
alternative alongside the `v1-partial-correlation-baseline`.

**If REASSESS**: diagnose whether the failure is in the search
architecture (already validated independently in Stage 6a on Fisher-z
— unlikely to be the cause) or in an interaction between the
architecture and the CMI test's own properties (coarser p-value
resolution, permutation noise compounding across a multi-subset
search) — the composed tier's conditioning-size-distribution
comparison against D-053 is the most direct diagnostic for
distinguishing these before writing a follow-up charter.
