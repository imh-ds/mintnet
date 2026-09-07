# Stage 4m Charter: Cascading-Error Stress Test for Chain/Fork/Hub (R6m)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

D-040/D-041 (Stage 4k/4l) validated D-012's existing `alpha(N)` formula
for chain, fork, and hub(2-children) — isolated and composed, across a
signal-strength range — leaving only one named R6a milestone
precondition untested for these three shapes: **the cascading-error
stress test Stage 4c already ran, but only on Stage 1's asymmetric
triangle.** The risk is unchanged from Stage 4c's own framing: pruning
under the sequential engine is permanent and order-dependent, so a
spurious noise variable that happens to correlate with both endpoints
of a **genuinely real but weak** edge could get confirmed early and
then wrongly explain that real edge away during conditioning — a
failure mode with no analog in the conservative engine (which requires
a complete, simultaneously-validated clique before pruning anything).

**Objective:** run Stage 4c's exact mechanism — paired, same-draw noise
injection, both engines on identical data, quantify (not gate) the
wrong-pruning rate difference — for chain, fork, and hub(2-children)
separately, closing the last named precondition for these three shapes.

**This remains a descriptive stress test, not a pass/fail gate**, per
Stage 4c's own established rationale: there is still no established
"acceptable cascading-error rate" anywhere in this project to gate
against.

## Data-generating process

**A weak-signal condition, deliberately below anything Stage 4k/4l
tested.** Stage 4k/4l's strength floor was `0.30`; this charter uses
**`strength = 0.15`** for all three motifs — genuinely weaker, chosen
so the motifs' own true direct edges are themselves borderline
detectable, the exact condition under which a spurious noise variable
has the best chance of tipping a conditioning decision (mirroring Stage
4c's own choice of the asymmetric triangle's weakest, `-0.08`, edge as
the place a cascading effect should show up first, if anywhere).
**Unlike Stage 4c's asymmetric triangle, chain/fork/hub's two direct
edges per motif are structurally symmetric** (equal `strength`, no
single "weakest" edge) — this charter therefore pools wrong-pruning
across **both** direct edges per motif as the unit of analysis, rather
than tracking one designated weak pair.

**Three motifs, tested separately** (not composed together — isolating
per-motif mechanism attribution cleanly, mirroring Stage 4c's own
single-triangle scope): chain (`0-2`), fork (`0-2`), hub-2-children
(`0-2`), identical to Stage 4k's own definitions.

**Two paired conditions, same motif draw, only noise varies**: for each
replicate, sample the motif from one RNG stream and, from a *separate*
stream (so the motif draw is bit-identical whether noise is added or
not), draw `noise_count in {0, 5}` independent standard-Gaussian
columns appended after the motif's own 3 columns. `noise_count=0` is
the control; `noise_count=5` is the stress condition, identical in
spirit and magnitude to Stage 4c's own.

**`N = [100, 200, 300]`**, **`alpha in {.05, .10}`** — Stage 4c's own
exact grid, reused directly for comparability. Master seed `20260830`,
a new stream tag distinct from every prior Stage 4 charter, `2,000`
replicates per `(motif, N, alpha, noise_count)` cell (`3 x 3 x 2 x 2 =
36` cells).

## Mechanism

No engine change to either pipeline, identical to Stage 4c. Both
engines run on the **identical simulated data** each replicate:

- **Sequential**: `mintnet.pipeline.sequential_screen_and_prune_detailed`
  — records, for both direct edges of the motif, whether each was a
  candidate, whether it was tested against any shared confirmed
  neighbor, **which specific neighbor indices it was tested against**,
  and the final confirmed/pruned outcome.
- **Conservative**: `mintnet.pipeline.compose_screen_then_prune` —
  records each direct edge's final status and whether its connected
  component was judged a validated clique (`is_validated_shape`) at
  all.

## Predeclared sub-questions (per motif)

**Q1 — Does noise contamination measurably increase the sequential
engine's true-direct-edge wrong-pruning rate?** Compare the pooled
(both direct edges) wrong-pruning rate at `noise_count=5` vs.
`noise_count=0`, per motif/`N`/`alpha`. **Predicted**: consistent with
Stage 4c's own finding (no meaningful increase, D-036), given the
mechanism identified there — a noise column must spuriously correlate
with *both* endpoints of the same real edge to matter, a much stronger
filter than a single spurious correlation.

**Q2 — Does noise contamination measurably increase the conservative
engine's true-direct-edge wrong-pruning rate the same way?** Same
comparison, conservative engine. **Predicted**: little to no increase,
same structural reason as Stage 4c's own Q2 — a noise column spuriously
connected to one motif node breaks clique completeness, disabling DPI
for that component rather than producing a wrong answer.

**Q3 — When the sequential engine wrongly prunes a true direct edge
under `noise_count=5`, was a noise column specifically implicated?**
Among replicates where a direct edge is wrongly pruned, compute the
fraction where at least one tested-neighbor index is a noise column
(index `>= 3`) rather than the motif's own third node. **The direct,
mechanistic confirmation (or disconfirmation) of the cascading pathway,
per motif** — a high fraction supports the flagged risk precisely; a
low fraction means contamination, if it occurs, has some other cause.

**Cross-motif question (new, not in Stage 4c, since that charter only
had one motif):** do Q1/Q3's answers differ meaningfully **by motif** —
i.e., is chain, fork, or hub structurally more (or less) susceptible to
this pathway than the others, at matching `N`/`alpha`/`strength`? Report
this explicitly rather than only pooling across motifs, mirroring Stage
4j/4k/4l's own full-grid reporting discipline.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence for both engines and all three
motifs (status, per-direct-edge outcome, tested-neighbor indices for
the sequential engine, clique-validity flag for the conservative
engine), the Q1/Q2/Q3 summary tables per motif/`N`/`alpha`, a cross-
motif comparison table, a direct comparison against Stage 4c's own
triangle-shape numbers at matching `N`/`alpha` (same stress condition,
different DGP), and a report stating all readings plainly without
forcing a verdict beyond what they show.

## Consequences

This charter cannot by itself authorize or forbid any future use of the
sequential engine for chain/fork/hub-type shapes — it only produces the
missing number the R6a milestone requires for them, the way Stage 4c
did for the triangle shape. If Q1 confirms a real, noise-attributable
increase in wrong-pruning for any motif (Q3 implicating noise columns
specifically): that motif's cascading-error risk is real and
quantified, and any future user-facing exposure of the sequential
engine for that shape must disclose it, sized by this charter's own
numbers. If Q1 shows no meaningful effect across all three motifs,
consistent with Stage 4c's own triangle result: this would be the
second independent DGP family confirming the same reassuring pattern,
substantially strengthening (not merely repeating) D-036's own finding
— though this charter, like Stage 4c, tests only one signal strength,
one noise-column count, and one contamination pathway (independent
noise, not noise correlated with a real node), so a genuinely
reassuring result here should still not be read as a blanket clearance
for every DGP or contamination pattern. Combined with D-040/D-041, a
clean result here would leave chain/fork/hub with every named R6a
milestone precondition addressed, for the first time for any shape
other than through the overlap-specific route (Stage 4a-4j) or the
triangle-specific route (Stage 4a/4c) alone.
