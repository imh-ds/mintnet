# Stage 5c Charter: p-Adjusted Screening Alpha — Re-Test the Noise-Column-Count Mechanism (R6)

Status: **FROZEN before results**
Date: 2026-09-01

## Background and objective

D-048 (Stage 5b) found the MINT-minus-EBICglasso F1 gap D-047
established **shrinks**, not grows, as noise-column count rises —
the opposite of the predicted direction. Diagnosis offered there,
**not yet separately tested**: Stage 5b's own MINT configuration held
screening `alpha` fixed at `.001` across every noise multiplier, even
as `p` grew from `15` (multiplier `1`) to `27` (chain_fork_hub,
multiplier `3`). EBICglasso's own extended-BIC criterion has a
built-in `ln(p)` penalty term that automatically compensates for
growing `p`; MINT's fixed per-pair `alpha` received no analogous
adjustment, which plausibly explains its declining precision (and
EBICglasso's improving precision) as noise columns were added. This
project's own Stage 2 arc already established that screening `alpha`
must be re-derived per `p` (`.001` at `p=15`, `.0001` at `p=30`,
outline Section 16's own v3 revision note) — Stage 5b simply did not
carry that established practice into the noise-multiplier sweep.

**Objective:** re-run Stage 5b's identical grid with a `p`-adjusted
screening `alpha` for MINT, to test directly whether that adjustment
restores, weakens, or has no effect on the shrinking-gap finding.

## p-adjusted alpha: a disclosed interpolation, not a fresh calibration

Truth-informed calibration of a new `alpha` at each new `p` (the way
Stage 2's own `.001`/`.0001` anchors were originally derived) is itself
a nontrivial exercise and is explicitly **out of scope** for this
targeted diagnostic charter — doing it here would also violate this
project's own fair-comparison discipline against fresh truth-informed
tuning inside a comparator-benchmark charter. Instead, this charter
uses a **disclosed, deterministic interpolation** between Stage 2's own
two already-calibrated anchor points, log-linear in `ln(p)`:

\[
\log_{10}\alpha(p) = \log_{10}(.001) + \frac{\log_{10}(.0001) -
\log_{10}(.001)}{\ln(30) - \ln(15)} \times (\ln(p) - \ln(15))
\]

which reproduces `alpha(15) = .001` and `alpha(30) = .0001` exactly and
interpolates/extrapolates log-linearly elsewhere. This is an
implementation-time approximation, stated plainly as such — not a
claim that this is the *correct* alpha(p) form, only a principled,
non-truth-informed way to test whether *some* p-adjustment in roughly
the right direction changes Stage 5b's own finding. **Only the
screening `alpha` changes.** DPI's own pruning `alpha(N)` (D-012's
general formula, a function of `N` only) is left exactly as in D-047/
D-048, per this project's own precedent that D-012's formula has never
itself been made `p`-dependent, including throughout Stage 2's own
`p in [5, 30]` arc.

## Grid: identical to Stage 5b, one substitution

Same two shapes (chain_fork_hub, overlap), same noise multipliers
`[1, 2, 3]`, same `N in [500, 1500]`, same strength (`.5`), same
EBICglasso settings (`gamma=.5`, `n_lambda=100`,
`lambda_min_ratio=.01`), same `2,000` replicates per cell (development
`0`-`999`, validation `1000`-`1999`). The only change: MINT's screening
`alpha` is `alpha(p)` (above) instead of the fixed `.001`. New,
disjoint seed stream (this charter draws fresh data, not a re-score of
Stage 5b's own draws, since a different `alpha` requires re-running the
screening step, not just re-scoring existing output).

## Sharding: three dimensions, not two

Stage 5b's own single-machine-then-CI run exposed a concrete
inefficiency: shards were split only by `(dgp, noise multiplier)`,
leaving `N` unsplit inside each shard. On a 2-vCPU GitHub-hosted
runner, `run_stage5b`'s auto worker-count (`min(tasks, cpu_count-1)`)
computed `min(2, 1) = 1` for the two `N` values inside each shard,
so they ran **serially** rather than in parallel — the single slowest
shard (`chain_fork_hub`, multiplier `3`, both `N`) dominated the run's
total wall-clock. This charter's own runner shards by `(dgp, N, noise
multiplier)` — three dimensions, each shard exactly one cell — and
`.github/workflows/sharded_benchmark.yml` is extended with an optional
third dimension (`dim3_flag`/`dim3_values`, unset preserves Stage
5a/5b's own two-dimension behavior) to support this.

## Decision structure

Descriptive, not a gate, same standing as D-047/D-048. Predeclared
reading:

- **Restores the mechanism** if, under `alpha(p)`, the
  MINT-minus-EBICglasso F1 gap is non-decreasing in noise multiplier
  (within the same `.01`-F1 tolerance D-048 used) at both `N`, both
  shapes.
- **Confirms the confound but not the mechanism** if the gap still
  shrinks with noise multiplier, but MINT's own F1 no longer declines
  with `p` (precision holds steady) — meaning `alpha(p)` fixed MINT's
  own precision problem but EBICglasso's `ln(p)`-driven improvement
  still outpaces it.
- **Neither** if `alpha(p)` changes little relative to D-048's own
  fixed-`alpha` result — would suggest the interpolation is too weak an
  adjustment, or the diagnosis itself needs revisiting.

## Required evidence

Resolved configuration (including the realized `alpha(p)` value at
every cell's own `p`), this charter's SHA-256, commit and runtime
metadata, raw per-replicate metrics for both methods at every `(dgp,
N, noise multiplier)` cell, and a report presenting the same F1-gap-
by-noise-multiplier comparison as Stage 5b's own report, plus a direct
side-by-side against D-048's fixed-`alpha` numbers.

## Consequences

Resolves D-048's own open diagnosis one way or another before any
further claim is made about how MINT's niche over EBICglasso scales
with network size. The signal-strength sweep flagged in
`docs/stage5a_charter.md`'s own recommendation remains deferred until
this is resolved (per D-048's own consequences section) — strength and
`p`-adjustment should not be conflated in one charter.
