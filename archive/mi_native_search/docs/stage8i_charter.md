# Stage 8i Charter: Population-Level Ground Truth for D-072's Own Flagged Decisive Subsets (main)

Status: **FROZEN before results**
Date: 2026-09-08

## Background and objective

An independent review of D-069 through D-073's own work (relayed by the
user) raised a methodologically sound gap: every diagnostic charter so
far (Stage 8f-8h) checked *sample* quantities (empirical rejection
rates, empirical marginal correlations) against synthetic or real
*finite-sample* data. None computed the **population-level** (true,
DGP-covariance-derived) partial correlation for the exact decisive
conditioning subsets D-072 flagged. That review also pointed out
`growing_subset_dpi`'s own search is fully exhaustive-by-size (not a
single greedy nested path, as the review's own hypothesized failure
mode assumed) -- verified directly against `src/mintnet/pipeline/
growing_subset_dpi.py`'s own loop structure, and further, that for
every one of D-072's own *wrongly-retained* flagged edges, the search
necessarily tested **every** subset at **every** size up to the cap
(a wrongly-retained edge, by construction, never triggers the
early-exit prune) -- so the known-correct separator, when in the pool,
was always tested alone at size 1 too, not skipped. This charter does
not re-litigate either of those two already-settled points; it acts on
the review's own remaining, genuinely new suggestion: compute the
*population* partial correlation for the actual flagged decisive
subsets, and classify what the *other* (non-separator) members of each
one structurally are.

**Why this is newly informative.** D-071/D-072/D-073 all measured
*empirical* quantities on finite samples. None asked the more basic
question this charter asks: for the exact conditioning subsets
`growing_subset_dpi` actually landed on in the flagged real-network
cases, is the **true, population-level** conditional relationship
between the tested pair actually zero (meaning any observed "failure"
is unambiguously a finite-sample/statistical-test artifact), or could
the added variable(s) be introducing a genuine, non-zero **population**
dependency this project's own prior structural argument (D-072's own
Background section: no true collider exists in either network) did not
fully rule out for every possible added-variable combination?

**Why this is analytically tractable without new randomness.**
`chain_fork_hub` (`stage4l.py`) and `overlap` (`stage2d.py`) are both
built by column-stacking **mutually independent** motif blocks (chain,
fork, hub or overlap-triangles, noise) -- confirmed directly from each
module's own `_sample_network` (separate `rng` calls, no cross-block
term). Each block's own population covariance is fully known in closed
form (chain/fork: `Cov(X_a, X_b) = strength^{|position difference|}`
along the block's own 3-node path; hub: `Cov(hub, child)=strength`,
`Cov(child_i, child_j)=strength^2`; overlap: `inverse` of the already-
committed `_OVERLAPPING_TRIANGLES_PRECISION` matrix in `mintnet.
simulation.motifs`). The full `p=15` population covariance matrix for
either network is therefore exactly known, block-diagonal, and requires
no sampling to construct -- this charter computes it once, analytically,
and evaluates it against every flagged decisive subset D-072 already
recorded (zero new stochastic evidence, the same "compute once,
threshold many times" reuse this project has used since Stage 8b).

## Mechanism

**Step 1 -- build the exact population covariance matrix.** For each
of `chain_fork_hub` and `overlap`, construct the full `15x15`
population covariance matrix at `strength=0.5` (Stage 8c's own fixed
value) directly from each block's own known closed-form structure
above -- a deterministic, testable function, not derived from any
sampled data.

**Step 2 -- compute the population partial correlation for every
flagged decisive subset.** Reusing D-072's own already-collected
`chance_correlation_candidates` (`stage8g_structural_audit.py`'s own
`enrich_with_chance_correlation` output -- every false edge with
`conditioning_size_used >= 2`, its own `(i, j)`, and its own
`decisive_conditioning_subset`), compute, for each row, the
**population** partial correlation of `(i, j)` given that exact
subset, using the standard Gaussian conditional-covariance formula
(`Sigma_ij - Sigma_iS @ inv(Sigma_SS) @ Sigma_Sj`) against Step 1's own
covariance matrix -- no sampled data involved in this computation at
all.

**Step 3 -- H6 (population-level conditioning-set error): is the true
conditional relationship actually zero for these subsets?** Report the
distribution of `|population partial correlation|` across every
flagged row, separately for named-indirect-pair edges (which have a
known separator) and cross-motif/noise edges (which do not). **Refutes
prior claims of "no population-level error"** if any row shows a
population partial correlation *materially* different from zero
(threshold: `0.05`, a predeclared, disclosed tolerance, not derived
from the math -- large enough to exclude floating-point noise, small
enough to catch a real non-trivial population relationship). Given
this project's own already-established block-independence, this
charter's own working expectation is that **all** flagged rows will
show population partial correlation indistinguishable from `0` -- but
this charter computes and checks that directly, per row, rather than
asserting it from the block-independence argument alone.

**Step 4 -- structural classification of every decisive subset's own
non-separator members.** For each flagged row (named-indirect-pair
edges only, where a separator is defined), classify every OTHER member
of the decisive subset (besides the known separator) into exactly one
of: **same-block** (a member of the tested pair's own motif block,
besides the separator itself -- structurally impossible for chain/fork/
hub's own 3-node blocks since the separator IS the only third member,
but relevant for overlap's own 5-node block, where a pair like `(6,9)`
has a 5-node block containing other members besides the shared node)
or **different-block** (any other motif's own member, or a noise
column). Report the frequency of each category across every flagged
row -- directly answering the review's own classification request,
scoped to what is actually structurally possible given each network's
own known block composition (no colliders or cross-block relationships
exist to classify, per D-072's own already-established Background,
so "mediator/common-cause/collider/descendant" collapses to this
project's own simpler same-block/different-block distinction here).

## Data-generating processes

None -- this charter computes population quantities analytically and
evaluates them against D-072's own already-collected evidence
(`chain_fork_hub`, `overlap`, `strength=0.5`, the same flagged rows
Stage 8g's own `enrich_with_chance_correlation` already produced from
the enriched Stage 8c raw evidence). No new samples are drawn.

## Compute-cost disclosure

Purely analytic (matrix inversion on small, `<=15x15`, matrices,
computed once per subset) -- no sampling, no GitHub Actions dispatch
needed. Runs locally against D-072's own already-downloaded evidence.

## Selection and gate

Diagnostic charter -- no PROCEED/REASSESS gate. One predeclared
verdict:

1. **H6 (population-level conditioning-set error exists)**: Confirmed
   / Not confirmed, per the Step 3 criterion above (`0.05` tolerance).
   **Not confirmed** is this charter's own working expectation, given
   already-established block-independence -- reported as a positive,
   checked result either way, not assumed.

Step 4's own classification table is reported descriptively, not
gated.

## Explicit non-goals

- **No re-litigation of D-069/D-071/D-072/D-073's own findings.** All
  stand as recorded.
- **No re-derivation of `growing_subset_dpi`'s own search-order
  behavior** -- already directly verified against the code in this
  charter's own Background (exhaustive-by-size; every subset tested for
  a wrongly-retained edge). Not re-tested here.
- **No test of the "post-screening selection effect" candidate** the
  same external review raised as a third possibility alongside
  population-level error and finite-sample power loss (D-073 already
  eliminated pure random-decoy power loss; selection-biased added
  variables -- ones that passed MINT's own screening threshold, unlike
  D-073's own uniformly random decoys -- are a distinct, not-yet-
  chartered hypothesis, named here as the most likely next step but not
  attempted in this charter).
- **No production deployment or fix.**

## Required evidence

This charter's SHA-256, the constructed population covariance
matrices for both networks (with a unit test confirming each is
positive definite and matches the known closed-form block values), the
per-row population partial correlation table, the Step 4 classification
table, the H6 verdict, and a report.

## Consequences

**If H6 not confirmed (expected)**: the composed-tier reversal is
conclusively pinned as a finite-sample/statistical-test phenomenon, not
a real population-level relationship introduced by the added
conditioning variables -- directly motivates chartering the
"post-screening selection effect" hypothesis next (the one remaining,
disclosed, not-yet-tested candidate from the original external review).

**If H6 confirmed for any row**: a real population-level dependency was
introduced by an added variable this project's own block-independence
argument did not anticipate -- would require identifying exactly which
motif/column combination produces it and revisiting the "no colliders
exist in either network" claim from D-072's own Background for that
specific case.
