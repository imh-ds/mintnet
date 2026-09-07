# Stage 5b Charter: Noise-Column-Count Stress Test — Does MINT's Advantage Over EBICglasso Scale With Nuisance Variables? (R6)

Status: **FROZEN before results**
Date: 2026-09-01

## Background and objective

D-047 (Stage 5a) found that on two composed, noisy Gaussian `p=15`
networks (chain/fork/hub; shared-node overlap), MINT's conservative
engine clears a predeclared `F1>=.90` acceptable-recovery bar at
`N=400` and keeps improving, while EBICglasso (`gamma=.5`) never
clears it anywhere on `N in [400, 1750]` — retaining `2`-`3x` as many
false edges despite both methods achieving perfect recall. The stated
mechanism: MINT's per-edge Fisher-z screening step tests each candidate
pair against its own evidence before DPI conditioning runs, while
EBICglasso's single global L1 penalty must suppress every noise-driven
edge across the whole `p x p` matrix at once. On the noise-free
triangle fixtures (no nuisance variables), the two methods were
indistinguishable — consistent with that mechanism, since there was
nothing for MINT's screening step to filter.

**That mechanism makes a specific, falsifiable prediction: the gap
between the two methods should grow as the number of pure-noise
(nuisance) columns grows**, holding everything else fixed. D-047 tested
exactly one noise-column count per shape (`6` for chain/fork/hub, `4`
for overlap — each shape's own already-established composed-network
fixture). This charter tests that prediction directly, rather than
letting a single favorable data point stand as if it were general.

**Deliberately not swept here: signal strength.** D-047 also used one
fixed strength (`.5`) throughout. Varying strength and noise-count in
the same charter would conflate two separate questions and make a
REASSESS-shaped result (if one appears) impossible to attribute. This
charter isolates noise-count as the single manipulated variable,
per this project's own established paired/single-variable stress-test
discipline (Stage 4c/4m/4n). Strength is reserved for a follow-up
charter once this one's own result is in.

## Scope reduction, stated explicitly

This is a targeted mechanism check, not a full re-benchmark. Two
changes from Stage 5a's own grid, both to bound compute:

- **Only the two noisy shapes** (`chain_fork_hub`, `overlap`) — the
  triangle fixtures have no noise columns to vary and already showed no
  material difference in D-047, so they add nothing to this specific
  question.
- **`N in [500, 1500]`** (two points from Stage 5a's own seven-point
  grid, one low and one high) rather than the full grid — enough to
  check whether the noise-count effect interacts with `N`, without
  re-running every `N` for every noise level.

Everything else — strength (`.5`), MINT's screening `alpha`
(`.001`) and D-012's general `alpha(N)` formula (unmodified, same
scope note as Stage 5a: overlap's specialized formula is not
reproducible in this worktree), EBICglasso's `gamma=.5` and full
100-point regularization path, `2,000` replicates per cell
(development `0`-`999`, validation `1000`-`1999`) — is carried over
from `docs/stage5a_charter.md` unchanged.

## Manipulated variable: extra noise columns

Each shape's own existing composed-network sampler
(`mintnet.experiments.stage4l._sample_network`,
`mintnet.experiments.stage2d._sample_network`) is reused **unmodified**
to draw the structural + native-noise data, then extended by appending
independent, standard-normal noise columns drawn from the same `rng`
stream immediately after the native draw. Appending independent noise
columns cannot change the joint distribution of the original variables
or the ground-truth edge set — this is purely an addition of columns
with no population dependence on anything already drawn, so no new DGP
validity question is introduced.

**Noise multiplier grid: `[1, 2, 3]`**, applied to each shape's own
native noise-column count (`6` for chain_fork_hub, `4` for overlap) —
multiplier `1` is Stage 5a's own already-tested condition (zero extra
columns, included here as a direct link back to D-047, not a fresh
draw at a different seed), `2` doubles the nuisance-variable count,
`3` triples it. Total `p` at multiplier `3`: chain_fork_hub `9 + 18 =
27`; overlap `7 + 12 = 19`. Both remain well within the dimensionality
already exercised elsewhere in this project (Stage 2's own `p=30`
arc).

## Metrics and reporting

Identical per-cell metrics to Stage 5a (`precision`, `recall`, `F1`,
`SHD`, runtime, both methods), reported per `(dgp, N, noise
multiplier)` cell, full grid, no cell omitted. The primary reported
quantity is **the F1 gap between MINT and EBICglasso at each noise
multiplier**, since the prediction under test is about how that gap
moves, not about either method's absolute floor (already established
by D-047).

## Decision structure

Descriptive, not a gate — same standing as Stage 5a's own D-047 (this
tests an external comparator's behavior, not MINT's own correctness).
Predeclared reading, fixed now:

- **Confirms the mechanism** if the MINT-minus-EBICglasso F1 gap is
  monotonically non-decreasing in noise multiplier, at both tested
  `N`, for both shapes (allowing for ordinary sampling noise — a
  reversal at one cell out of many is not disqualifying, a systematic
  reversal across most cells is).
- **Complicates the mechanism** if the gap is flat or shrinks as noise
  multiplier grows — would mean the noise-column-count story from
  D-047 is incomplete or wrong, and needs its own diagnosis before
  being cited as an explanation going forward.
- Either outcome gets reported plainly per the project's own
  discipline against reinterpreting a result to fit the prior
  narrative.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate metrics for both methods at every `(dgp,
N, noise multiplier)` cell, and a report presenting the full grid plus
the F1-gap-by-noise-multiplier comparison explicitly.

## Consequences

If confirmed: strengthens D-047's own stated mechanism from a
plausible explanation of one data point into a tested, scaling
relationship — meaningful for the eventual paper's discussion of when
MINT's niche actually applies (networks with more nuisance variables,
not just "networks with some noise"). If complicated: D-047's own
mechanism explanation needs revision before further R6 charters build
on it, and the strength-sweep follow-up charter should wait until this
is resolved. Either way, this remains supplementary to, not a
retraction of, D-047's own PROCEED-adjacent descriptive verdict.
