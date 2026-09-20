# Stage 4l Charter: Composed Pipeline with Noise for Chain/Fork/Hub (Sequential Engine, p=15) (R6l)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

D-040 (Stage 4k) found that D-012's already-frozen `alpha(N)` formula
— reused unmodified, no new fitting — PROCEEDs cleanly across chain,
fork, and hub(2-children) motifs at four signal strengths and three
sample sizes, all tested **in isolation** (a single 3-column motif,
alone, no noise, no other variables). That isolated result does not
yet answer whether the same formula holds once real screening pressure
is added: many null pairs competing for candidacy, other motifs present
as potential confounds, noise columns diluting the candidate pool —
exactly the distinction this project drew for the conservative engine
between D-017 (isolated hub/overlap conditioning, both fine) and D-018
(composed, where overlap specifically REASSESSed at `N=750` due to
screening's own detection reliability, not the conditioning mechanism).

**Objective:** this charter is that step for chain/fork/hub, mirroring
`docs/stage4h_charter.md`'s own role after Stage 4g precisely — embed
the isolated-validated `alpha(N)` rule, unmodified, in a full, noisy,
`p=15` network, as an explicit hypothesis to test, not an assumption.
This is the composed/noisy sweep D-040's own consequences named as the
natural next step to close the isolated-vs-composed gap for these three
shapes the way Stage 4h closed it for overlap.

**Scope, deliberately narrower than Stage 4k's own isolated sweep.**
Two signal strengths, not four: `0.30` (Stage 4k's weakest, hardest,
and most informative cell — the one closest to overlap's own
historically-difficult correlation) and `0.50` (Stage 2d/4h's own
canonical value, enabling rough cross-charter comparison of the effect
of adding noise/composition at a signal strength already characterized
for overlap). This mirrors Stage 4h's own choice of a single
representative strength while still preserving the signal-strength axis
that was the entire point of Stage 4k, at a bounded simulation cost.

## Data-generating process

**A new `p=15` composed network**, built from the same three
structurally-symmetric motifs Stage 4k validated in isolation, plus
noise — deliberately **not** Stage 2d's own `p=15` network (which uses
chain, fork, and the shared-node-overlap shape, not hub):

- **Chain** (columns `0-2`): `mintnet.simulation.sample_chain(n,
  strength, rng)`. Direct edges `(0,1)`, `(1,2)`. Indirect pair `(0,2)`.
- **Fork** (columns `3-5`): `mintnet.simulation.sample_measured_fork(n,
  strength, rng)`. Direct edges `(3,4)`, `(4,5)`. Indirect pair `(3,5)`.
- **Hub, 2 children** (columns `6-8`): `mintnet.simulation.sample_hub(n,
  strength, children=2, rng)`, column `6` the hub. Direct edges `(6,7)`,
  `(6,8)`. Indirect pair `(7,8)`.
- **Noise** (columns `9-14`, `6` independent standard-normal columns):
  chosen so total `p=15`, matching Stage 2d/4h's own magnitude for a
  comparable screening-pressure regime, even though the specific
  composition differs (`9` signal + `6` noise here vs. Stage 2d's `11`
  signal + `4` noise).

**Ground truth:** `9` true candidate pairs (`3` within-motif pairs x `3`
motifs), `96` null pairs (`C(15,2) - 9`), `6` true direct edges, `3`
indirect edges (one per motif, matching Stage 4k's own structural
symmetry, extended here to the composed setting).

**`N = [750, 1000, 1500]`** — Stage 4k's own exact validated grid,
reused unchanged for direct before/after comparability against the
isolated result. All inside D-012's own validated `[700, 3000]`
interpolation range.

**`strength in [0.30, 0.50]`.** Master seed `20260830`, a new stream
tag distinct from every prior Stage 4 charter. `2,000` replicates per
cell (development `0`-`999`, validation `1000`-`1999`), matching Stage
2d/4h's own scale for a composed-pipeline charter.

## Mechanism

No code change. `mintnet.pipeline.sequential_screen_and_prune_detailed`
run on the **full 15-column data** each replicate — all `C(15,2)=105`
pairs ranked and processed together, not the isolated 3-column motifs
Stage 4k tested. `alpha` at each `N` is D-012's single formula-predicted
value, identical to Stage 4k's own (re-derived via
`mintnet.experiments.stage1j_fit.fit_candidate_forms`/`select_form`,
unmodified) — the same formula, the same three `alpha` values, reused
again without any new fitting. The `screened` matrix (which pairs
cleared initial marginal candidacy, mirroring Stage 4h's own
reconstruction from the sequential engine's returned `PairDecision`
list) and the `final` matrix are scored by a generalized version of
`mintnet.experiments.stage2d._score`, adapted from `(chain, fork,
overlap)` indirect-edge categories to `(chain, fork, hub)`.

## Selection and gate

Identical five-part gate structure to `docs/stage4h_charter.md`, on
validation replicates:

1. Chain indirect-edge TPR `>= .80`.
2. Fork indirect-edge TPR `>= .80`.
3. Hub indirect-edge TPR `>= .80`.
4. True-edge retention FPR `<= .10`.
5. Final false-edge rate (fraction of the `96` null pairs wrongly
   present in the final graph) does not exceed the engine's own
   screening-stage false-edge rate by more than `.01`.

**PROCEED** for a given `(strength, N)` cell only if all five hold with
no recorded error. **REASSESS** otherwise.

**Full-grid reporting requirement (mirrors Stage 4j/4k's own
requirement):** report every one of the `6` cells (`2` strengths x `3`
`N`) individually regardless of the overall outcome, so any pattern —
failures concentrated at low strength, low `N`, or one motif
specifically — is visible directly. **If any cell fails, additionally
report, per motif, the isolated-vs-composed comparison directly against
that same `(strength, N)` cell's own Stage 4k result** — the same
candidacy/conditional-accuracy decomposition Stage 4e/4h used for
overlap, so a REASSESS here can be attributed to screening pressure
specifically (candidacy dropping) rather than conflated with a
conditioning-mechanism regression (which Stage 4k already ruled out in
isolation and this charter does not re-test).

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (per-motif indirect-pair
candidacy/confirmation detail, aggregate metrics per cell), the
six-cell decision table, a direct comparison table against Stage 4k's
own isolated results at matching `(strength, N)` cells, report, and
figures.

## Consequences

If PROCEED across the whole grid: this closes the isolated-vs-composed
gap for chain/fork/hub the way Stage 4h closed it for overlap — D-012's
existing formula, still unmodified, generalizes to embedded, noisy use
for these three shapes too, not just isolated use. Combined with D-040,
this would leave **Stage 4c's cascading-error stress test** (tested
only on the triangle shape so far) as the one still-open R6a
precondition before any user-facing recommendation for chain/fork/hub-
type shapes specifically. Overlap remains its own separate case,
requiring its own dedicated `alpha(N)` treatment regardless of this
charter's outcome.

If REASSESS at some cells: report exactly which, per the full-grid and
comparison requirements above. **If failures concentrate at low
strength** (`0.30`) specifically, and the required comparison shows
candidacy (not conditional accuracy) dropping relative to Stage 4k's
isolated result, that would mirror D-018's own diagnosis for overlap
exactly — screening detection reliability, not the conditioning
mechanism, becomes the limiting factor once real competition from `96`
null pairs is present — and would motivate the same kind of dedicated
`alpha(N)` recalibration treatment Stage 4e-4j built for overlap,
extended to whichever of chain/fork/hub fails here. **If failures
instead concentrate at one specific motif** regardless of strength,
that would point to a structural difference between that motif and the
other two worth its own dedicated investigation. Either outcome leaves
Stage 4k's own isolated results (D-040) untouched, and does not
retroactively change Stage 4h's overlap-specific composed result
(D-037).
