# Stage 10a Charter: A Single, Densely-Interconnected Organic-Shaped Network -- Testing External Validity Beyond Isolated Motifs (mi-native)

Status: **FROZEN before results**
Date: 2026-09-15

## Background and objective

**Every mi-native DGP validated so far -- `chain_fork_hub` (Stage 4l),
`overlap` (Stage 2d), the isolated triangle variants -- is built the
same way: several small, disjoint 3-to-5-node motifs, concatenated
into one dataset alongside uncorrelated noise columns, purely so one
screening/search pass can test several structural challenges at once.**
Confirmed directly against the DGP registry (`stage5a._DGP_REGISTRY`,
`stage2d.py`, `stage4l.py`): `chain_fork_hub` is chain + fork + hub,
each its own disconnected component; `overlap` is chain + fork +
overlap-motif, likewise disconnected. **No DGP in this project's
evidence base has ever been a single, richly interconnected network**
-- the shape mi-native exists to be used on in practice (an
organization's actual relationship network, a real correlational
system), where dozens of variables sit in one connected structure with
hubs, bridges between sub-groups, local dense clusters, and multiple
paths between any two points, not three isolated triads sharing a
CSV file.

This gap was surfaced directly by the user reviewing Stage 9d's own
results: a real network diagram of `overlap` made visible that every
"network" tested to date is actually three independent components
tested in parallel for efficiency, not one organic graph. **This is
not a limitation of the search algorithm** -- screening and the
growing-subset search operate on whatever correlation structure is in
the data and do not know or care whether the true graph is three
disconnected pieces or one connected web. **It is a limitation of what
has been validated**: every existing PROCEED decision (D-040, D-044,
and the mi-native structured-density results through D-088) certifies
correctness on isolated motifs, not on the denser, cyclic, larger
candidate-pool regime a real organic network presents. Without this
test, every existing validated-range claim in `docs/validated_
operating_ranges.md` describes a regime meaningfully easier than actual
use, and that gap is exactly what makes the accumulated evidence weak
as a claim about real-world applicability.

## Mechanism

**Step 1 -- design a single, explicit, ground-truth-known topology**,
built by hand (matching this project's own precedent of hand-specified
precision matrices for `overlap`/triangle DGPs, not a randomly-generated
graph whose exact structure would need to be re-derived from the
generator each time). `p = 18`: 14 structural nodes plus 4 uncorrelated
noise columns (matching every existing DGP's own noise-column
convention). One connected component, with cycles (unlike every prior
DGP, which is either a tree-shaped motif or several disconnected
trees):

- **Cluster A** (nodes 0-3, a dense local group -- an "energizer"
  cluster): true edges `(0,1), (0,2), (1,2), (1,3), (2,3)` (near-complete
  on 4 nodes, one edge short of a clique).
- **Hub 1** (node 4, a "connector"): true edges `(3,4)` (bridge into
  Cluster A) and `(4,5)` (bridge into Cluster B). Degree 2 by itself,
  but node 3 (its bridge point) reaches degree 4 once the long-range
  tie below is added.
- **Cluster B** (nodes 5-7, a triangle): true edges `(5,6), (6,7), (5,7)`.
- **Broker** (node 8, pure bridge, degree 2, matching the "brokers link
  sub-groups" role): true edges `(4,8), (8,9)`.
- **Hub 2** (node 9, the highest-degree connector, degree 5): true edges
  `(9,10), (9,11), (9,12)` (into Cluster C) and `(9,13)` (a pendant).
- **Cluster C** (nodes 10-12, a chain rather than a triangle, for
  topological variety): true edges `(10,11), (11,12)` -- deliberately no
  `(10,12)`, so Cluster C's own indirect pair is a genuine mediation
  test alongside Cluster A/B's denser mediation structure.
- **Pendant** (node 13, a peripheral, minimally-connected "challenger"):
  true edge `(9,13)` only (already listed above), degree 1.
- **Long-range shortcut** (`(3,12)`): ties Cluster A directly to
  Cluster C, independent of the Hub-1/Broker/Hub-2 path -- this is what
  makes the graph genuinely cyclic (e.g. `3-4-8-9-12-3` is a 5-cycle)
  rather than a tree, and is the single most realistic feature relative
  to an actual organic network, where redundant paths are the norm, not
  the exception.
- **Noise** (nodes 14-17): independent standard-normal, uncorrelated
  with everything, matching every existing DGP's own noise convention.

19 true direct edges total among the 14 structural nodes. Precision
matrix: identity plus `-0.15` at each true-edge off-diagonal position
(and its symmetric counterpart), which keeps every row diagonally
dominant (worst case, node 9's degree-5 row sums to `0.75 < 1`) and
therefore guaranteed positive definite without needing per-edge tuning;
covariance is the matrix inverse, sampled the same way as every
existing precision-matrix DGP (`sample_precision_triangle`'s own
pattern). No `strength` parameter -- matching the triangle DGPs'
existing precedent of a fixed precision matrix rather than a
continuously-tunable knob, since this charter's question is about
topology, not signal strength.

**Step 2 (REQUIRED before any full evidence run) -- measure real cost
first, at a single moderate `N` (750, this project's own established
workhorse size), dispatched via the sharded GitHub Actions workflow
from the very first measurement, not locally and not as an unsharded
single job.** This charter's own central open risk is combinatorial: a
single connected, cyclic, 18-column network will screen in a much
larger, much more interconnected candidate pool than any disconnected
motif has ever produced, and nodes 3 and 9 in particular (degree 4 and
5) may require conditioning sets deep enough to be expensive well
beyond anything measured in D-085 or Stage 9d. Sharding here must be
by **candidate-pair batches** within this single `(dgp=organic_
network, N=750)` cell, not by the existing `(dgp, N)` grid dimensions
`sharded_benchmark.yml` already supports -- this is a new sharding
axis this charter's own evidence-generation step must add, learning
directly from D-088's own disclosed sharding miss (a single expensive
job run unsharded exceeded GitHub's 6-hour job limit and was cancelled
with no result). If Step 2 shows the point estimate alone is
impractical even sharded by pair-batch, this charter reports that
directly as REASSESS-on-cost and does not proceed to Step 3.

**Step 3 -- run screening, then `growing_subset_dpi_structured_density`
(D-063's own `degree=1` default, unchanged), then score recall
(fraction of the 19 true edges retained) and removal (fraction of
every indirect/false pair correctly pruned) against the known ground
truth above.** No rescue mechanism (D-088's localized or the existing
full-repeat one) is invoked in this charter -- this charter tests the
point-estimate search's own behavior on a genuinely organic topology
first, in isolation from the separate, already-open question of
bootstrap-rescue calibration (Stage 9d). Whether rescue is *also*
needed on this topology's own qualifying edges is a natural follow-on
charter, not this one.

**Step 4 -- if Step 2/3 support it, extend to a small `N` grid**
(candidates: `{500, 750, 1500}`, matching this project's own typical
range) to check whether recall/removal on this topology holds across
sample size the same way it does on every existing isolated-motif DGP,
or degrades faster given the larger candidate pool and deeper required
conditioning.

## Compute-cost disclosure

**This charter's central, honestly-disclosed risk is combinatorial
blowup, not a hoped-for convenience.** Every prior DGP kept the
candidate pool small by construction (disconnected 3-to-5-node
components); this one deliberately does not. Screening pressure alone
(more real correlations propagating transitively through one connected
graph, versus zero cross-component correlation in every prior DGP)
will likely flag a much larger candidate set, and the growing-subset
search's own cost is combinatorial in conditioning depth
(`max_conditioning_size`) -- nodes 3 and 9's own higher degree are the
specific, named risk points most likely to demand deep conditioning.
Step 2 exists precisely to measure this before committing to a full
`N`-grid evidence run, exactly as Stage 9d's own Step 2 did for the
bootstrap-rescue cost question -- and this time, sharded from the
first measurement, not after a 6-hour timeout discloses the miss
after the fact.

## Selection and gate

**PROCEED** only if, at every tested `N` with at least 10 replicates
generating usable evidence, recall `>= 0.95` and removal `>= 0.85` on
held-out replicates -- the same bar used throughout this project's
mi-native evidence base (D-087, D-088's own prerequisite work), not a
weaker one invented for this charter. **REASSESS** otherwise,
explicitly including: recall/removal failing on this topology despite
passing on every isolated motif (meaning the isolated-motif evidence
base does not generalize to organic topology, a first-order finding in
its own right); or Step 2 showing the cost is impractical even sharded
by pair-batch (meaning this topology's scale needs to shrink, or the
search itself needs a cost-reduction mechanism, before external
validity can be tested this way at all).

## Explicit non-goals

- **No claim about real organizational network data.** This is still a
  synthetic Gaussian graphical model with a hand-specified, fully known
  true structure -- necessary for exact recall/removal scoring, per
  this project's own confirmatory discipline (`docs/decision_log.md`'s
  own repeated insistence on known ground truth over unverifiable real
  data). It is a step toward external validity, not external validity
  itself.
- **No re-tuning of `degree`, `k_perm`, `screening_alpha`, or any other
  already-validated parameter** -- D-063's `degree=1` and this
  project's existing `screening_alpha=0.001` convention carry over
  unchanged, so any difference in outcome is attributable to topology,
  not a moved target.
- **No bootstrap-rescue mechanism invoked** (see Step 3) -- deliberately
  isolated from Stage 9d's own separate, still-open calibration
  question.
- **No claim about networks larger than `p=18`** -- if this charter
  PROCEEDs, a larger/denser follow-on (closer to dozens or hundreds of
  real-world variables) is a natural next charter, not assumed here.
- **No production deployment authorization.**

## Required evidence

This charter's SHA-256, commit and runtime metadata; Step 2's own
sharded cost measurement (reported even if the charter REASSESSes on
cost alone, per this project's own standing disclosure convention);
Step 3/4's raw per-edge evidence and recall/removal table for every
tested `N`; the gate decision; and a report.

## Consequences

**If PROCEED**: this becomes the first mi-native evidence that
correctness holds on a topology resembling actual use, materially
strengthening (not just supplementing) every existing validated-range
claim in `docs/validated_operating_ranges.md`, which until now
describes only the isolated-motif regime. A natural larger/denser
follow-on charter becomes worth chartering.

**If REASSESS on calibration** (recall/removal fails here despite
passing on every isolated motif): this is a first-order, high-priority
finding -- it would mean the entire existing validated-range evidence
base has been measuring a regime that does not represent real use, and
every existing PROCEED decision needs its own claim narrowed
accordingly in `docs/validated_operating_ranges.md`, not treated as
still-general.

**If REASSESS on cost**: the search's own combinatorial cost on a
genuinely connected topology is confirmed as a real barrier to testing
external validity this way, motivating either a smaller/sparser
organic topology as a next attempt, or a cost-reduction mechanism for
the growing-subset search itself (a new, separate charter) before
external validity can be tested at all.
