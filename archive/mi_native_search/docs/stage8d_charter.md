# Stage 8d Charter: Diagnosing the Composed-Tier False-Edge Margin Reversal (main)

Status: **FROZEN before results**
Date: 2026-09-07

## Background and objective

D-068 found that for false (should-be-pruned) edges on composed `p=15`
networks, raw margin is not merely uninformative in its low-to-mid
range (D-066's own isolated-tier finding) — it actively **reverses**:
the highest-margin bin (`~0.95`) is *less* reliable than several
middle bins (`chain_fork_hub`/`N=1750`: bin `9` accuracy `.782` vs.
bins `0`-`8` at `.88`-`.93`). This charter diagnoses *why*, and tests
whether a specific, disclosed limitation this project already
identified — not a new, unexplained phenomenon — is the cause, and
whether removing it fixes the symptom.

**Leading hypothesis, grounded in prior evidence, not invented here**:
D-052 found a material share of this project's own residual false
positives are edges that never got properly conditioned on; D-053
(Stage 6a) built `growing_subset_dpi` specifically to search
conditioning subsets up to a disclosed, fixed cap
(`max_conditioning_size=4`), with its own `cap_reached` flag recording
exactly the case where a component's own pool exceeded that cap and
larger, untested subsets might have revealed independence. **A false
edge whose true blocking conditioning set requires more than 4 other
variables will never find it** — every subset up to size `4` may
reject independence (small p-value throughout), producing a
confidently-*retained*-margin-formula reading (`(alpha - p) / alpha`
close to `1`) for an edge that is, in truth, false. This charter tests
whether exactly this — `cap_reached` and/or a large
`conditioning_size_used` — explains D-068's own reversal, rather than
assuming it does.

## Mechanism

**Step 1 — enrich, not replace, Stage 8c's own evidence.** Re-run
Stage 8c's exact frozen design (identical seeds, identical config,
`configs/stage8c_composed_calibration.yaml`) — a deterministic
reproduction, not new randomness or a new DGP — capturing two fields
`growing_subset_dpi` already computes but Stage 8c's own runner never
persisted: `conditioning_size_used` and `cap_reached`, per edge.
Framed explicitly as completing Stage 8c's own raw evidence with a
diagnostic dimension it lacked, not a second independent experiment.

**Step 2 — test H1 (cap-reached hypothesis).** Restrict to false
edges in margin bin `9` (`>= 0.9`, D-068's own reversal region).
Compare empirical accuracy (Wilson 95% CI) between `cap_reached=True`
and `cap_reached=False` subsets, per `(dgp, N)`. **Confirmed** if
`cap_reached=True`'s own accuracy is materially and consistently lower
(non-overlapping CIs, or a clearly one-directional pattern across
every cell) than `cap_reached=False`'s own accuracy in that same bin.

**Step 3 — test H2 (conditioning-size-graded hypothesis, broader than
H1's binary cut).** Re-derive D-068's own monotonicity/ECE check,
restricted separately to each `conditioning_size_used` value
(`0`-`4`). **Confirmed** if the reversal is concentrated at large
`conditioning_size_used` (e.g. `3`-`4`) and attenuates or disappears
when restricted to small sizes (`0`-`1`) — a graded, not merely
binary, version of the same mechanism.

**Step 4 — candidate fix, only if H1 or H2 is confirmed.** Re-run
*only* the flagged cells/components (those with `cap_reached=True` in
the original evidence) at a larger `max_conditioning_size` (disclosed
value chosen after a fresh timing check, not assumed — see below), and
check whether the previously-reversed bin's own accuracy improves
toward monotonic. This directly tests "does removing the suspected
cause fix the symptom," not just correlate with it.

## Data-generating processes

Identical to Stage 8c's own (`chain_fork_hub`, `overlap`, `p=15`,
`strength=0.5`, `screening_alpha=0.001`, `N in
{400,500,600,750,1000,1500,1750}`, `master_seed=80200`, `R=2000`) for
steps 1-3, since this charter's own job is to explain that evidence,
not generate different evidence. Step 4's own candidate-fix re-run is
restricted to `cap_reached=True` cells/components only (a minority
subset per D-053's own "real minority of cases" framing), at whatever
larger `max_conditioning_size` the fresh timing check in that step
supports.

## Compute-cost disclosure

**Steps 1-3**: no new compute-cost risk — identical grid, identical
per-replicate cost already measured for Stage 8c (`~11-14ms`);
recording two additional already-computed dictionary fields per edge
adds no meaningful overhead.

**Step 4 is not assumed cheap.** A larger `max_conditioning_size`
means testing more, and larger, candidate subsets per edge — the
combinatorial cost of `growing_subset_dpi`'s own search grows with the
cap, and Stage 8c's own `~11-14ms` figure was measured at
`max_conditioning_size=4` specifically. Per this project's own
standing discipline: **measure real wall-clock cost of the search at
the candidate larger cap, on at least one flagged component, before
committing to a specific value or a full re-run plan.**

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** —
unchanged, hard requirement, per this project's established practice.

## Selection and gate

Diagnostic charter — no PROCEED/REASSESS gate on the whole (mirrors
this project's own precedent for mechanism-diagnosis charters, e.g.
D-052). Three separate, predeclared verdicts instead:

1. **H1 (cap-reached)**: Confirmed / Not confirmed, per the Step 2
   criterion above.
2. **H2 (conditioning-size-graded)**: Confirmed / Not confirmed, per
   the Step 3 criterion above.
3. **Candidate fix (only attempted if H1 or H2 confirmed)**: Effective
   / Partially effective / Not effective, based on whether Step 4's
   own re-run at a larger cap restores monotonicity (or materially
   narrows the reversal) in the previously-flagged cells.

If neither H1 nor H2 is confirmed, Step 4 is not run, and this
charter's own consequence is naming the leading hypothesis eliminated
— itself a useful, disclosed result — not a failure to reach a verdict.

## Explicit non-goals

- **No claim about the true-edge case.** D-068 already confirmed that
  transfers cleanly; this charter is scoped entirely to the false-edge
  reversal.
- **No deployment of any fix.** Even a confirmed, effective candidate
  fix (e.g. raising `max_conditioning_size` for composed networks) is
  a production-pipeline decision for a separate future charter, not
  decided here.
- **No claim beyond `cap_reached`/`conditioning_size_used` as
  candidate mechanisms.** If both H1 and H2 are eliminated, this
  charter does not attempt to invent or test further hypotheses beyond
  reporting the elimination — a follow-up charter would need to
  propose the next candidate explanation.
- **No re-litigation of D-053's own accuracy findings** or the
  original `max_conditioning_size=4` choice's own general defensibility
  — this charter only asks whether it explains one specific, already-
  measured calibration anomaly.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the enriched raw
evidence (Steps 1-3) and its own H1/H2 cross-tabulation tables, the
Step 4 timing measurement and (if run) its own before/after comparison
on the flagged cells, the three verdicts above, and a report.

## Consequences

**If H1 or H2 confirmed and the candidate fix is effective**: the
composed-tier false-edge reversal has an identified, fixable cause —
motivates a future production-decision charter (raise
`max_conditioning_size` for composed networks, or use `cap_reached`/
`conditioning_size_used` as an explicit input to a future composed-
tier recalibration mapping alongside margin itself, per D-068's own
named option (a)).

**If confirmed but the fix is not effective or only partial**: the cap
is A cause but not the whole story — the fresh-curve recalibration
result from D-068 (still descriptive, not deployed) becomes the more
promising path forward instead of a search-depth change.

**If neither H1 nor H2 is confirmed**: the reversal's cause remains
open — a genuinely more surprising outcome, since it would mean this
project's own best-supported prior hypothesis for this class of error
does not explain a new instance of it. Would warrant a fresh, wider
diagnostic pass (not scoped or predetermined here) before any fix is
attempted.
