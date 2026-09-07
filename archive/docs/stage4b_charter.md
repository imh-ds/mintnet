# Stage 4b Charter: Sequential/Greedy Conditioning Engine — Hub and Overlap Components (R6b)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-030 (Stage 4a) validated the sequential/greedy engine's basic
correctness on three-node motifs, reproducing the conservative engine's
own numbers almost exactly and diverging favorably at small `N`. That
charter deliberately deferred any component larger than three nodes —
the setting this whole engine exists to help with. This charter takes
that next step, mirroring how the conservative engine's own arc moved
from three-node motifs (`docs/stage1b_charter.md`) to a 4-node hub
(`docs/stage1k_charter.md`, D-015) and a 5-node shared-node overlap
(`docs/stage1L_charter.md`, D-017) — both DGPs generated **in isolation,
with no extra noise columns**, exactly as those two charters did.

**Why this charter already tests the motivating question, not just a
mechanism-generalization check.** Stage 1k/1L handed the conservative
DPI mechanism a *pre-flagged, guaranteed-clean* candidate component
directly, deliberately separating "does conditioning work on this
topology" from "does screening reliably produce a clean component in
the first place" (the latter is what D-018/D-026's `N` floor is actually
about, per D-030's own framing). The sequential engine has no equivalent
of that separation: it does not accept a pre-flagged input at all —
ranking, candidacy, and conditioning are one fused procedure operating
directly on raw data (`mintnet.pipeline.sequential_screen_and_prune`).
**Testing it on the isolated overlap DGP therefore already engages the
exact mechanism this initiative is about**: an edge is confirmed or
pruned the moment its own evidence is strong enough, never gated on
whether three *other*, independently weak pairs also happened to clear
the bar in the same replicate. If the sequential engine PROCEEDs at
`N=750` on this isolated overlap DGP — the same `N` and DGP where D-017
already showed the conservative *mechanism* works fine once handed a
clean clique, but D-018 showed the *composed* pipeline fails because
that clean clique rarely forms — that would be direct evidence the
conjunctive all-pairs-simultaneously requirement, not the conditioning
test itself, is the removable bottleneck.

**A second, distinct predicted mechanism, worth separating from the
first:** Stage 1k/1L's conservative mechanism conditions each edge on
*every other node in the component* (hub: 2 other children; overlap: 3
other nodes) — a deliberate, general engineering choice, not a claim
that every one of those conditioning variables is individually
necessary. The sequential engine instead conditions each edge only on
already-confirmed **shared neighbors** — for a hub child-child pair,
typically just the hub itself; for an overlap cross-branch pair,
typically just the shared node — never on irrelevant siblings. Since an
irrelevant conditioning variable costs statistical power without adding
information, this predicts the sequential engine's conditioning test
itself may be *more* powerful at fixed `N`, independent of the
conjunctive-requirement effect above. Both mechanisms point the same
direction; this charter's evidence does not by itself distinguish which
one dominates, and should not claim to.

**Predeclared expectation:** hub PROCEEDs comfortably at both `N`
(mirroring D-015, with plausibly wider margins per the targeted-
conditioning argument above). Overlap is the genuinely open question:
this charter predicts a real possibility of **PROCEED at `N=750`**,
which would contradict D-018's composed-pipeline finding at the same
`N` and same DGP — an explicitly stated, falsifiable prediction, not a
foregone conclusion.

## Data-generating process

Identical to Stage 1k/1L, reused unmodified for direct comparability:

- **Hub** (`sample_hub(n, .5, children=3, rng)`): hub node 0, children
  1-3. True edges: `(0,1)`, `(0,2)`, `(0,3)`. Indirect edges: `(1,2)`,
  `(1,3)`, `(2,3)`.
- **Overlap** (`sample_overlapping_triangles(n, rng)`): two triangles
  sharing node 2 (`{0,1,2}`, `{2,3,4}`). True edges (6): `(0,1)`,
  `(0,2)`, `(1,2)`, `(2,3)`, `(2,4)`, `(3,4)`. Indirect edges (4):
  `(0,3)`, `(0,4)`, `(1,3)`, `(1,4)`.

Neither DGP has any noise columns — this charter tests the fused
screen-and-condition mechanism on the target structure alone, exactly as
Stage 1k/1L tested conditioning alone. Embedding either shape in a
larger, noisy candidate network (Stage 2c/2d's own next step after Stage
1k/1L) is explicitly deferred to a later charter.

`N = [750, 1500]` (Stage 1/2's shared validated regime, and specifically
D-017/D-018's own values for the overlap shape, for direct
comparability). Master seed `20260830`, 2000 replicates (development
0-999, validation 1000-1999) — matching Stage 1k/1L's own scale.

## Mechanism

Unchanged from `docs/stage4a_charter.md`: `mintnet.pipeline.
sequential_screen_and_prune(data, alpha)` — rank candidate pairs by
marginal `|z|`, confirm the strongest immediately, test the rest by
conditioning on already-confirmed shared neighbors (testing every
qualifying neighbor singly, per Stage 4a's exact rule; pruning
permanently if any one explains the edge away). No code change from
Stage 4a; this charter is new evidence on a new DGP, not a new
mechanism.

## Selection and gate

A new alpha grid selection is required — D-012's `alpha(N)` formula was
fit for the conservative engine's conditioning-only step and does not
apply to this engine's single fused alpha. Reuse Stage 4a's own grid and
selection procedure per shape and `N`: candidate `alpha in [.50, .30,
.20, .10, .05, .01, .005, .001, .0001]`. On development replicates
(0-999), a given `alpha` is eligible if:

1. Indirect-edge pruning TPR (child-child pairs for hub; cross-branch
   pairs for overlap) `>= .80`, with margin `>= .02`.
2. True-edge retention FPR `<= .10`, with margin `>= .02`.

Select the largest eligible `alpha` (unlike Stage 1b/4a's "smallest
adjacent pair" tiebreak — there is no adjacent-pair robustness check
here, and a larger `alpha` is the more permissive, easier-to-clear
candidacy threshold; ties broken toward the value closest to the
already-validated conditioning-alpha region if more than one clears by
equal margin). Validation replicates (1000-1999) confirm the selected
`alpha` at the same two thresholds, individually, per `N`, per shape.
**PROCEED** for a given `(shape, N)` cell only if both criteria hold on
validation with no recorded error.

**Direct comparison, not just an independent gate**, per Stage 4a's own
established practice: report this engine's per-`(shape, N)` indirect
TPR and true-edge FPR alongside the conservative engine's own recorded
numbers at the same DGP and `N` — D-015 (hub) and D-017 (isolated
overlap mechanism) for the "does conditioning work here at all"
question, **and D-018 (composed overlap pipeline) for the motivating
question** of whether this engine's `N=750` result differs from the
composed conservative pipeline's own `N=750` REASSESS on the identical
shape and signal strength.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate per-pair evidence (which shared neighbors
were tested, per-neighbor conditional `p`-values, final retain/prune
decision), aggregate metrics, the alpha-selection table, the per-
`(shape, N)` decision table, report, and figures.

## Consequences

If hub PROCEEDs at both `N` and overlap PROCEEDs at **`N=750`**: this is
the first direct evidence that removing the conservative pipeline's
all-pairs-simultaneously requirement (or the targeted-conditioning
effect, or both) meaningfully lowers the `N` this weak shape needs — the
central premise this whole engine was built to test. It does **not** yet
authorize any user-facing recommendation (Stage 4c's cascading-error
stress test remains a precondition per the R6a milestone in
`outline/information_network_technical_build_plan_v3_2026-08-30.md`),
and it is evidence from an isolated, noise-free DGP — a composed,
screening-realistic version (mirroring Stage 2d after Stage 1L) would
still be needed before claiming this transfers to a real, larger
dataset.

If overlap REASSESSes at `N=750` (matching D-018's composed-pipeline
result): the conjunctive-requirement and targeted-conditioning
hypotheses would both be contradicted at this `N`, at least for this
exact signal strength — meaning the weak cross-branch correlation
itself (not the composition logic around it) is the binding constraint,
and the greedy engine's structural advantage does not help here. This
would be a genuinely informative negative result, not a failure to
avoid: it would mean this initiative's next move is to check whether the
underlying single-edge conditioning test *itself* needs a different
approach (e.g., a one-sided or effect-size-aware test tuned for
detecting a known-weak signal) rather than assuming a different
composition strategy alone is sufficient.

If hub REASSESses at either `N`: this would be a genuine regression
against D-015's validated conservative-engine result on the easiest
tested multi-node shape, and should block any further Stage 4 work
until diagnosed — a shape the conservative engine already handles
comfortably should not become harder under the new engine.
