# Stage 2d Charter: Wiring Shared-Node Overlap into the Composed Pipeline (R3f)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

Stage 1L validated multi-variable conditioning on shared-node overlap
topology, in isolation — DPI handed a clean, hand-fed 5-node component
directly (D-017). It explicitly deferred the question of whether
screening reliably *produces* that clean component in the first place,
flagging a closed-form power calculation showing detection of the weak
(`~.135`) cross-branch correlation is only `~66%` at `N=750` vs. `~98%`
at `N=1500`. This charter answers that deferred question directly, mirroring
how Stage 2c followed Stage 1k.

**A predeclared expectation, checked by simulation before writing this
charter, not assumed:** because the candidate component needs *all four*
cross-branch pairs detected simultaneously to form a clean, DPI-eligible
clique, and each is individually detected only `~66%` of the time at
`N=750`, a 500-replicate pre-check found the clean-clique rate is only
`~26%` at `N=750` (vs. `~89%` at `N=1500`). Running the full composed
pipeline through this same pre-check predicted an overlap-specific
indirect-edge pruning TPR of **`~.59` at `N=750`** (below the `.80` gate)
and **`~.82` at `N=1500`** (above it). **This charter is expected to
REASSESS at `N=750` and PROCEED at `N=1500`, and that split outcome, if
it occurs, is the informative finding this charter exists to confirm, not
a failure to be avoided or explained away.**

## Mechanism (code change)

Extend `mintnet.pipeline.compose.VALIDATED_CLIQUE_SIZES` from `{3, 4}` to
`{3, 4, 5}`, justified by D-017's evidence that the general conditioning
rule is not topology-specific (validated now on a hub/star and on
shared-node overlap, two structurally different shapes, both using the
same unmodified `alpha(N)` formula) — the code cannot distinguish *which*
5-node topology a clean candidate clique represents (screening only
reveals which pairs are candidates, not why), so trusting "clean 5-node
clique" in general, not just this one DGP's shape, is the only
implementable extension. Verified before use: this change is inert on
every existing recorded charter's evidence, since no prior DGP ever
produces a 5-node candidate component.

## Data-generating process

`p = 15`: chain (0-2), measured fork (3-5), the shared-node-overlap motif
(6-10, node 8 shared), and 4 noise columns (11-14). Screening at
`alpha=.001` (D-013), DPI at `alpha=f(N)` (D-012), `N = [750, 1500]`,
master seed `20260829`, 2000 replicates (development 0-999, validation
1000-1999).

**Ground truth**: true candidate pairs (nonzero correlation) = chain's 3
+ fork's 3 + overlap's `C(5,2)=10` = **16**; null pairs = `C(15,2) - 16`
= **89**. True direct edges = chain's 2 + fork's 2 + overlap's 6 = **10**.
Indirect/prunable edges = chain's 1 + fork's 1 + overlap's 4 cross-branch
pairs = **6**.

## Selection and gate

No selection step. Per `N`, on validation replicates (1000-1999),
computed **separately per motif** rather than pooled (pooling would risk
exactly the D-004 blind spot this project has already been burned by
once):

1. Chain indirect-edge TPR `>= .80`.
2. Fork indirect-edge TPR `>= .80`.
3. **Overlap indirect-edge TPR `>= .80`** (the one expected to fail at
   `N=750`).
4. True-edge retention FPR `<= .10`, all three motifs pooled (retention
   is not expected to be the constraint here, per D-014/D-016/D-017's
   consistent `FPR ~ 0` pattern; pooling this specific metric is
   reasonable since nothing so far suggests it hides a per-motif
   problem).
5. Final false-edge rate does not exceed screening-alone's rate by more
   than `.01` (the same no-regression check as D-014/D-016).

**PROCEED** for a given `N` only if all five hold with no recorded error.
Descriptive: the clean-clique formation rate for the overlap component,
to compare against the pre-charter prediction (`~26%`/`~89%`).

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (per-motif indirect TPR, pooled
true-edge FPR, screening/final false-edge rates, overlap clean-clique
indicator), aggregate metrics, the per-N decision table, report, and
figures.

## Consequences

If the predicted split outcome occurs (REASSESS at `750`, PROCEED at
`1500`): this establishes that extending `VALIDATED_CLIQUE_SIZES` to
include size 5 is only safe to rely on at `N` where the specific DGP's
signal is strong enough for screening to reliably produce a clean
candidate clique — a property of the *screening step's power*, not the
conditioning mechanism, which D-017 already showed works correctly
whenever it gets the chance to run. The practical floor for trusting this
extension would need its own further characterization (e.g., locating
the crossover the way D-010 did for the `N` floor), not assumed from two
data points.

If the outcome differs from the prediction (e.g., PROCEED at both, or
REASSESS at both): treat this as evidence the pre-charter simulation
missed something, and investigate before drawing conclusions either way.
