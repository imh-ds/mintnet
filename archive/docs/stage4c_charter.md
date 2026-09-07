# Stage 4c Charter: Cascading-Error Stress Test (R6g)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

Every Stage 4 charter so far has evaluated the sequential engine on its
*accuracy* — TPR, FPR, conditional accuracy. None has directly tested
its own central, distinguishing risk, flagged from the very first
planning discussion and repeated in every Stage 4 charter's
Consequences section since: **pruning is permanent and order-dependent.
An early confirmed edge — right or wrong — becomes available as a
conditioning variable for every pair processed after it.** A wrongly
confirmed edge (e.g., a pure noise variable that, by sampling chance,
looks correlated with a real network node) can therefore feed into, and
corrupt, decisions about *unrelated* pairs later in the same run — a
failure mode the conservative engine's composed pipeline structurally
cannot produce the same way, since it conditions on the full clique
simultaneously rather than sequentially, and refuses to prune anything
in an *incomplete* clique at all. This charter is the R6a milestone's
own precondition (`outline/information_network_technical_build_plan_v3_2026-08-30.md`):
no user-facing claim about the sequential engine is authorized until
this specific risk is characterized, not merely acknowledged.

**This is a descriptive stress test, not a pass/fail gate.** There is no
established "acceptable cascading-error rate" anywhere in this project
to gate against — inventing one here would be arbitrary. This charter
instead quantifies the effect precisely and reports it plainly; whether
the resulting number is acceptable for any given use is a judgment call
for a future decision, not resolved by this charter.

## Data-generating process

**Base structure**: Stage 1's `strong` triangle fixture (columns `0,1,2`,
precision `[[1,-.45,-.25],[-.45,1,-.08],[-.25,-.08,1]]`) — the same
deliberately asymmetric fixture used throughout Stage 1/4a, where pair
`(1,2)` is the weak-but-genuinely-real edge (partial correlation `-.08`,
the smallest of the three). This is the edge already known to be hardest
to retain correctly; a cascading-error mechanism should show up here
first, if anywhere.

**Two paired conditions, same triangle draw, only noise varies**: for
each replicate, sample the triangle from one RNG stream and, from a
*separate* stream (so the triangle draw is bit-identical whether noise
is added or not — isolating noise's causal effect cleanly), draw
`noise_count in {0, 5}` independent standard-Gaussian columns appended
after the triangle. `noise_count=0` is the control (matches Stage 4a's
own noise-free baseline exactly); `noise_count=5` is the stress
condition — 5 pure-noise variables, structurally unrelated to the
triangle, giving multiple independent chances per replicate for at
least one to spuriously correlate with a triangle node at small `N`.

`N = [100, 200, 300]` — Stage 1's smallest, hardest-case sample sizes,
where sampling noise is largest and contamination risk should be most
visible. `alpha in {.05, .10}` — Stage 4a's own selected development
pair, reused for direct comparability, not re-derived. Master seed
`20260830`, 2,000 replicates per `(N, alpha, noise_count)` cell.

## Mechanism

No engine change to either pipeline. Both engines run on the **identical
simulated data** each replicate (same triangle-plus-noise draw), so any
difference is attributable to composition logic, not sampling variance:

- **Sequential**: `mintnet.pipeline.sequential_screen_and_prune_detailed`
  — records, for the weak `(1,2)` pair specifically, whether it was a
  candidate, whether it was tested against any shared confirmed
  neighbor, **which specific neighbor indices it was tested against**,
  and the final confirmed/pruned outcome.
- **Conservative**: `mintnet.pipeline.compose_screen_then_prune` — records
  the `(1,2)` pair's final status and whether its connected component
  was judged a validated clique (`is_validated_shape`) at all.

## Predeclared sub-questions

**Q1 — Does noise contamination measurably increase the sequential
engine's weak-edge wrong-pruning rate?** Compare pooled `(1,2)`
wrong-pruning rate at `noise_count=5` vs. `noise_count=0`, per `N`/
`alpha`. **Predicted**: a real, non-trivial increase at small `N`,
concentrated in replicates where a noise column appears among the
pair's tested neighbors (see Q3).

**Q2 — Does noise contamination measurably increase the conservative
engine's weak-edge wrong-pruning rate the same way?** Same comparison,
conservative engine. **Predicted**: little to no increase — a noise
column spuriously connected to only one triangle node breaks the
`(1,2)` component's clique completeness, which disables DPI for that
whole component under the conservative engine's existing conservative
design (edges pass through unpruned when the component isn't a
validated clique), rather than producing a wrong answer.

**Q3 — When the sequential engine wrongly prunes `(1,2)` under
`noise_count=5`, was a noise column specifically implicated?** Among
replicates where `(1,2)` is wrongly pruned, compute the fraction where
at least one of the tested neighbor indices is a noise column (index
`>= 3`) rather than the triangle's own node `0`. **This is the direct,
mechanistic confirmation (or disconfirmation) of the cascading pathway**
this charter exists to check — a high fraction supports the originally
flagged risk precisely; a low fraction would mean contamination, if it
occurs, has some other cause.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence for both engines (status, weak-edge
outcome, tested-neighbor indices for the sequential engine, clique-
validity flag for the conservative engine), the Q1/Q2/Q3 summary tables
per `N`/`alpha`, and a report stating the three readings plainly without
forcing a verdict beyond what they show.

## Consequences

This charter cannot by itself authorize or forbid any future use of the
sequential engine — it only produces the missing number the R6a
milestone requires. If Q1 confirms a real, noise-attributable increase
in wrong-pruning (Q3 implicating noise columns specifically): the
cascading-error risk flagged since planning is real and quantified, not
hypothetical, and any future user-facing exposure of this engine must
disclose it, sized by this charter's own numbers, alongside whatever
`N`/`alpha` gains Stage 4b/4d/4g demonstrated. If Q1 shows no meaningful
effect: the permanent, order-dependent design is riskier in principle
than in practice for this specific stress condition, though this
charter tests only one DGP (a single asymmetric triangle plus pure
noise) and does not generalize to every shape or contamination pattern
untested here — a genuinely reassuring result here should not be read as
a blanket clearance.
