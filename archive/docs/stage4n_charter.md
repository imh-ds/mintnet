# Stage 4n Charter: Cascading-Error Stress Test for Overlap (R6n)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

D-042 (Stage 4m) found that Stage 4c's clean cascading-error null
(D-036, one asymmetric triangle) does not generalize: chain, fork, and
hub(2-children), tested at a uniformly weak signal strength with no
"anchor" edge to out-rank noise for confirmation order, showed a small
but statistically robust cascading effect. **The overlap shape — the
shape with this whole engine's single largest claimed win (D-037:
`N=625` beating the conservative engine's own `N=1500`) — has never had
this specific pathway measured at all.** Stage 4h's own contamination
diagnostic checked whether a *wrongly-retained cross-branch (indirect)
pair* was tested against a non-shared node; it never checked whether
noise contamination can cause a *genuinely real direct edge* to be
wrongly pruned — the exact question Stage 4c/4m ask for every other
shape tested so far. This is the last named R6a-adjacent gap before the
sequential engine's headline result can be considered stress-tested the
same way every other shape now has been.

**Objective:** run Stage 4c/4m's exact mechanism — paired, same-draw
noise injection, both engines on identical data, quantify (not gate) —
on overlap's own DGP, tracking its `6` true direct edges (not the `4`
cross-branch indirect pairs, already covered by Stage 4h's own
diagnostic and out of scope here).

**This remains a descriptive stress test, not a pass/fail gate**, per
Stage 4c/4m's own established rationale.

## Data-generating process

**Overlap's own fixed DGP**, `mintnet.simulation.
sample_overlapping_triangles(n, rng)` — unlike chain/fork/hub, this
motif has no `strength` parameter; its two `balanced`-style triangles
(columns `0-4`, column `2` shared) are fixed at `-0.25` per direct edge.
This is **not** the uniformly-weak condition Stage 4m deliberately
constructed (chain/fork/hub at `strength=0.15`) — overlap's own direct
edges (`-0.25`) are comparable in magnitude to Stage 1's triangle's
*strongest* edges, not its weakest. **This charter therefore tests a
third, structurally distinct condition**, neither Stage 4c's asymmetric-
strong-anchor design nor Stage 4m's uniform-weak design: overlap's
`6` direct edges are uniformly `moderate`-strength, but its DGP also
contains `4` additional weak, spurious, shared-cause-induced cross-
correlations (the indirect pairs) that could plausibly serve as
alternative candidates competing for early confirmation — a
configuration not tested by either prior charter.

**Two paired conditions, same draw, only noise varies** (identical
design to Stage 4c/4m): for each replicate, sample the two-triangle
overlap structure from one RNG stream and, from a *separate* stream,
draw `noise_count in {0, 5}` independent standard-Gaussian columns
appended after the `5` real columns (indices `5` onward). `noise_count=0`
is the control; `noise_count=5` is the stress condition, identical in
magnitude to Stage 4c/4m's own.

**`N = [100, 200, 300]`**, **`alpha in {.05, .10}`** — Stage 4c/4m's
exact grid, reused directly for three-way comparability across all
cascading-error charters. **Deliberately not using Stage 4g/4i/4j's
fitted `alpha(N)` formula**, which is validated only for `N in [400,
735]` and would be invalid (or unvalidated) at this charter's smaller,
harder `N` values — matching Stage 4c/4m's own precedent of a fixed,
reused `alpha`, not a fitted one, for this specific stress-test purpose.
Master seed `20260830`, a new stream tag distinct from every prior Stage
4 charter, `2,000` replicates per `(N, alpha, noise_count)` cell.

## Mechanism

No engine change to either pipeline, identical to Stage 4c/4m. Both
engines run on the **identical simulated data** each replicate:

- **Sequential**: `mintnet.pipeline.sequential_screen_and_prune_detailed`
  — records, for all `6` true direct edges
  (`mintnet.experiments.stage1l.TRUE_EDGES`), whether each was a
  candidate, whether it was tested against any shared confirmed
  neighbor, **which specific neighbor indices it was tested against**,
  and the final confirmed/pruned outcome. A tested-neighbor index `>= 5`
  identifies a noise column (overlap's own `5` real columns occupy
  indices `0`-`4`, unlike Stage 4c/4m's `3`).
- **Conservative**: `mintnet.pipeline.compose_screen_then_prune` —
  records each direct edge's final status and whether its connected
  component was judged a validated clique (`is_validated_shape`) at
  all.

**Unit of analysis**: wrong-pruning pooled across all `6` true direct
edges (mirroring Stage 4m's pooling across chain/fork/hub's `2` edges
each, extended here to overlap's `6` — overlap has no single designated
"weakest" edge among its direct edges either; all `6` share the same
`-0.25` precision entry by construction).

## Predeclared sub-questions

**Q1 — Does noise contamination measurably increase the sequential
engine's true-direct-edge wrong-pruning rate?** Compare the pooled
(all `6` direct edges) wrong-pruning rate at `noise_count=5` vs.
`noise_count=0`, per `N`/`alpha`. **No directional prediction is made in
advance** — this charter deliberately sits between Stage 4c's clean
null and Stage 4m's small-but-real effect on a DGP unlike either prior
one, and forcing a prediction here would not be justified by either
result.

**Q2 — Does noise contamination measurably increase the conservative
engine's true-direct-edge wrong-pruning rate the same way?** Same
comparison, conservative engine. **Predicted**: little to no increase,
consistent with both Stage 4c's and Stage 4m's own Q2 findings and the
same structural reason (a noise column spuriously connected to one node
breaks clique completeness, disabling DPI for that component rather
than producing a wrong answer) — this part of the mechanism is DGP-
independent and has held in both prior tests.

**Q3 — When the sequential engine wrongly prunes a true direct edge
under `noise_count=5`, was a noise column specifically implicated?**
Among replicates where a direct edge is wrongly pruned, compute the
fraction where at least one tested-neighbor index is a noise column
(index `>= 5`). The direct, mechanistic check, unchanged in form from
Stage 4c/4m.

**Q4 — Does the presence of overlap's own weak, spurious cross-branch
correlations change the picture relative to Stage 4c/4m?** Specifically,
report separately whether a wrongly-pruned direct edge's tested
neighbors more often include one of the **other real nodes from the
opposite triangle** (indices belonging to overlap's own structure, not
noise) versus a noise column — a pathway with no analog in Stage 4c
(single triangle, no "opposite branch") or Stage 4m (no induced
cross-branch correlation at all). This is new to this charter and
directly tests whether overlap's own structure, independent of noise,
contributes to cascading risk.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence for both engines (status, per-
direct-edge outcome, tested-neighbor indices for the sequential engine,
clique-validity flag for the conservative engine), the Q1/Q2/Q3/Q4
summary tables per `N`/`alpha`, a direct three-way comparison table
against Stage 4c's (triangle) and Stage 4m's (chain/fork/hub) own
numbers at matching `N`/`alpha`, and a report stating all readings
plainly without forcing a verdict beyond what they show.

## Consequences

This charter cannot by itself authorize or forbid any future use of the
sequential engine for the overlap shape — it produces the one measured
number still missing for this project's headline result (D-037). If Q1
confirms a real, noise-attributable increase (Q3 implicating noise
columns specifically): overlap's cascading-error risk is now
quantified, and D-037's own `N=625`/`700` result must be reported
alongside this number, not in isolation, in any future user-facing
context. If Q4 finds the opposite-triangle pathway is *also* implicated
independent of noise: that would be a new, overlap-specific finding —
evidence the shape's own structure (not just noise) carries some
cascading risk, worth its own follow-up. If Q1 shows no meaningful
effect, consistent with Stage 4c's own triangle result rather than
Stage 4m's: that would suggest overlap's moderate, uniform direct-edge
strength (`-0.25`, well above Stage 4m's deliberately weaker `0.15`)
keeps it closer to Stage 4c's protected regime than Stage 4m's exposed
one — informative either way, and, combined with D-037/D-038/D-039,
would leave the overlap shape's own arc as thoroughly stress-tested as
chain/fork/hub's now is.
