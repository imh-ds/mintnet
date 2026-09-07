# Stage 4p Charter: Canonical N-Grid Public Benchmark — Both Engines, Both Shape Families, Side-by-Side (R6p)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

`docs/stage4o_recommendation.md`'s own `N`-threshold matrix (Section 2)
is accurate but deliberately ragged — every cell traces to whichever
`N` its own originating charter needed for its own falsification
question (`750/1000/1500` for chain/fork/hub, a dense `400`-`750` grid
for overlap's own calibration, `100/200/300` for cascading-error stress
tests). That raggedness is a feature for internal record-keeping — each
charter tested exactly what it needed — but it makes external,
side-by-side comparison across shapes and engines harder than it should
be.

**Objective:** produce one additional, deliberately narrow benchmark —
**both engines, both shape families, run on identical paired data,
across one fixed canonical `N` grid** — as a public-facing comparison
table. This charter does **not** re-litigate, replace, or supersede
any prior charter's own finding. `docs/stage4a_charter.md` through
`docs/stage4o_recommendation.md` remain the authoritative internal
validation record; this charter's own deliverable is explicitly
supplementary.

**Canonical grid: `N = [400, 500, 600, 750, 1000, 1500]`.** Chosen to
deliberately span both engines' own established floors (`400`-`600`
sit below the conservative engine's own `N=750` recommended default,
D-011, and below chain/fork/hub's own tested floor under the sequential
engine, D-040/D-041) through their shared validated range (`750`-
`1500`) — the sub-floor points are included specifically to make the
floor visible in the benchmark table, not because either engine is
expected to pass there.

## Data-generating processes (both reused unmodified, no new DGP)

1. **Overlap-based `p=15`**: `mintnet.experiments.stage2d._sample_network`
   — chain (`0-2`), fork (`3-5`), shared-node overlap (`6-10`), `4`
   noise columns. Identical to every prior overlap-composed charter
   (Stage 2d, Stage 4h).
2. **Hub-based `p=15`**: `mintnet.experiments.stage4l._sample_network`
   — chain (`0-2`), fork (`3-5`), hub-2-children (`6-8`), `6` noise
   columns. Identical to Stage 4l.

**`strength = 0.5`** for both networks — Stage 2d/4h/4l's own shared
canonical default. **No new strength sweep in this charter**; D-040/
D-041 already cover strength variation for chain/fork/hub, and overlap
has no tunable strength.

## Mechanism: both engines, same alpha, same data, every cell

**The single most important design choice in this charter**: both
engines use **the exact same alpha selection procedure** at every `N`
— D-012's already-frozen general formula
(`mintnet.experiments.stage1j_fit.fit_candidate_forms`/`select_form`,
re-derived deterministically, not re-fit), **not** overlap's own
specialized `alpha(N)` formula (Stage 4g/4i/4j, valid only on `[400,
735]`). This is deliberate: a benchmark comparing two engines and two
shapes side by side needs one consistent alpha-selection rule to be a
fair comparison, and D-012's formula is the one rule already shown to
generalize across every shape tested so far except overlap under the
sequential engine specifically (D-037-D-039 is exactly the case where
it does not — this benchmark is expected to show that divergence
directly, which is itself the informative part, not an error).

- **Conservative engine**: `mintnet.pipeline.compose_screen_then_prune`,
  screening `alpha=.001` (Stage 2d's own established default, reused
  unmodified), DPI `alpha=f(N)` from D-012's formula.
- **Sequential engine**: `mintnet.pipeline.
  sequential_screen_and_prune_detailed`, single fused `alpha=f(N)` from
  the same D-012 formula.

**Paired, same-draw design**: both engines run on the **identical**
simulated data each replicate, for each `(DGP, N)` cell — mirroring
Stage 4c/4m/4n's own paired-comparison precedent, extended here from a
single tracked pair to the full composed-pipeline score.

Master seed `20260830`, a new stream tag distinct from every prior
Stage 4 charter, `2,000` replicates per `(DGP, N)` cell (development
`0`-`999`, validation `1000`-`1999`).

## Gate

Identical five-part gate to `docs/stage2d_charter.md`/
`docs/stage4h_charter.md`/`docs/stage4l_charter.md`, applied **separately
to each engine's own output**, per `(DGP, N)` cell:

1. Chain indirect-edge TPR `>= .80`.
2. Fork indirect-edge TPR `>= .80`.
3. Third-shape indirect-edge TPR `>= .80` (composite overlap TPR for
   the overlap-based network; hub TPR for the hub-based network).
4. True-edge retention FPR `<= .10`.
5. Final false-edge rate does not exceed that engine's own
   screening-stage false-edge rate by more than `.01`.

**PROCEED** per `(DGP, N, engine)` cell only if all five hold with no
recorded error. **REASSESS** otherwise. This produces a `2 (DGP) x 6
(N) x 2 (engine) = 24`-cell decision table — every cell reported
regardless of outcome, per this project's now-established full-grid
reporting discipline (Stage 4j/4k/4l/4m/4n).

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, D-012's re-derived formula and its parameters (confirming it
was not altered), raw per-replicate evidence for both engines and both
DGPs at all `6` canonical `N`, the full `24`-cell decision table
presented side-by-side (both engines' PROCEED/REASSESS status visible
in the same row, per `DGP`/`N`), and a report that explicitly
cross-references `docs/stage4o_recommendation.md`'s own `N`-threshold
matrix, stating plainly where this benchmark's results agree with the
specialized per-shape findings and where they diverge (expected at
overlap under the sequential engine, `N < 750`, since this charter
deliberately does not use overlap's own dedicated formula there).

## Consequences

This charter's own deliverable is a second, narrower table alongside
`docs/stage4o_recommendation.md`'s own — not a replacement. If the
overlap/sequential cells diverge from Stage 4g/4i/4j's own specialized
results (expected, since this charter uses the general formula, not the
overlap-specific one), that divergence itself demonstrates *why* the
specialized calibration work in Stage 4e-4j was necessary, and should
be stated that way in the report, not treated as a contradiction between
two "competing" results. If the conservative engine REASSESSes at
`N=400`-`600` on both DGPs (expected, below its own established
floor) and the sequential engine also REASSESSes there for chain/fork/
hub (untested territory, per `docs/stage4o_recommendation.md`'s own
Section 5 boundary), that is new information this project has not
previously had in one place, and should be recorded as such. No prior
charter's PROCEED/REASSESS/descriptive finding is altered, retracted,
or superseded by this charter's own results.
