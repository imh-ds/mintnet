# Stage 7c Charter: Estimator Retuning Against the Mapped Operating Frontier (mi-native)

Status: **FROZEN before results**
Date: 2026-09-04

## Background and objective

D-059's own revision explicitly deferred estimator retuning until
Stage 7b's own frontier mapping existed, to avoid overfitting `k_CMI`/
`k_perm` against a single hard fixture. Stage 7b (D-060) has now
mapped that frontier at the current default (`k_CMI=40`, `k_perm=3`):
detection limit `|partial correlation| = .20/.15/.12` at
`N=750/1500/3000`, with the original `strong` fixture's own edge
(`0.08`) still out of reach at every tested `N`.

**This charter asks the specific question Stage 7b's own consequences
section named as the legitimate next step**: does varying `k_CMI`
shift that frontier favorably (a lower detection limit at the same
`N`), without breaking D-056's own Type-I error calibration? This is
motivated by a concrete user-facing consideration, not curiosity for
its own sake: `N < 750` accessibility is explicitly a "nice-to-have,
not a need-to-have" for this project's own current use case, so this
charter is scoped modestly (one parameter, bracketing the existing
default) rather than an open-ended search.

**Single-parameter discipline**: `k_perm` is held fixed at `3`
(D-056's own selected value) throughout. Varying two parameters
simultaneously here would both multiply the compute grid and make it
impossible to attribute any frontier shift to a specific cause — a
`k_perm`-specific power investigation, if this charter's own findings
motivate one, is separate future work.

## Design

**Swept**: `k_CMI in {10, 20, 30, 40, 60, 80, 100}` — brackets the
current default in both directions, not just larger values (Stage
6c's own Stage A found larger `k_CMI` reduces null-variance
monotonically up to `40`, the largest value tested there; this
charter checks whether that trend continues, plateaus, or reverses
due to over-smoothing bias against real signal, which Stage 6c's own
null-only study could not distinguish).

**DGP**: reuses `mintnet.simulation.motifs.sample_weak_edge_triangle`
unchanged. `target_rho in {0, 0.08, 0.12, 0.15}` — the in-family null
check plus the three most diagnostic points from D-060's own findings
(the original hard case, and the two values nearest the mapped
frontier at `N=1500`/`3000`). Values already comfortably feasible at
every `N` (`0.20`, `0.25`) are not retested here — not informative for
this charter's own question.

**`N in {750, 1500, 3000}`** — identical to Stage 7b's own grid, for
direct frontier comparability.

**Scope reduction from Stage 7b, disclosed here**: only the weak edge
`(1, 2)` pair's own CMI/p-value is computed per replicate, not all
three pairs. The two dominant edges' own near-certain retention was
already established in Stage 7b and is not in question here; omitting
them is a real, roughly `3x` cost reduction per replicate, not a
shortcut that risks missing something this charter is trying to
measure.

**`alpha` grid**: Stage 7b's own frozen `50`-value grid (`.01` to
`.50`, step `.01`), for direct comparability with the already-mapped
`k_CMI=40` frontier.

**`replicates`**: provisionally `R=400`, matching Stage 7b — subject
to the same up-front timing-measurement requirement below.

## Compute-cost disclosure

Per this project's own standing discipline: before finalizing
`batch_size`/shard count, measure real per-replicate cost at the
grid's own `k_CMI` extremes (`10` and `100`) at `N=3000` directly —
not assumed to match the already-measured `k_CMI=40` cost, since
larger `k` means larger neighbor queries and cost is not guaranteed
`k`-invariant (an early spot-check in this session found `k=40`
roughly comparable to or cheaper than `k=20` at `N=750`, but that
does not establish invariance across the full `10`-`100` range at
`N=3000`). A provisional shard plan (subject to that measurement):
combine `(k_CMI, target_rho)` into one composite shard label (`28`
combinations) crossed with `N` (`3` values) and a `batch` dimension
sized to keep every shard under GitHub Actions' `6`-hour job timeout
at the *measured* worst-case per-replicate cost — target a single
dispatch under the `256`-job matrix cap, as Stage 7b achieved.

## Selection structure (two stages, mirroring D-056 -> D-057's own pattern)

**Stage A — calibration filter.** For each swept `k_CMI`, check the
`target_rho=0` cells at every tested `N` against D-056's own
defensibility criterion (empirical rejection rate at `alpha in {.05,
.01}` falls in the frozen band, or its Wilson 95% CI overlaps the
nominal rate). A `k_CMI` value that fails this filter at any `N` is
**excluded from Stage B entirely** — an uncalibrated test's own power
numbers are not meaningful, exactly as D-056 established for
`k_perm`. Report which `k_CMI` values survive this filter, and why
any that fail do so (over- or under-rejecting).

**Stage B — frontier comparison, calibrated survivors only.** For
each `k_CMI` that passes Stage A, compute its own detection limit per
`N` using the same feasibility definition as D-060
(`operating_frontier`/`detection_limit_summary`, reusing
`mintnet.experiments.stage7b_frontier_reporting`'s own logic where the
schema allows). Compare directly against D-060's own recorded
`k_CMI=40` baseline: does any surviving `k_CMI` achieve a *lower*
detection limit at the same `N`? Report the full comparison table,
not just the best performer — a null result (nothing beats `40`) is
as reportable as a positive one.

## Explicit non-goals

- **No `k_perm` sweep.** Held fixed at `3`; separate future work if
  motivated by this charter's own findings.
- **No change to `permutations=199`.** Same resolution floor as every
  prior mi-native charter.
- **No new estimator.** This charter tunes CMIknn's own existing
  parameter, not a different mechanism (RCoT, copula-transformed MI,
  etc. remain separate, larger future options, as discussed but not
  chartered).
- **No composition into DPI.** Purely a significance-test
  characterization, like Stage 6c/6d/7b before it.
- **No re-validation of the dominant edges or the composed tier.**
  Out of scope, per the disclosed single-pair scope reduction above.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the up-front `k_CMI in {10,100}`/`N=3000` timing measurement
and its own resulting batch-size decision, raw per-replicate evidence,
the Stage A calibration-filter table (per `k_CMI`, per `N`, per
`alpha in {.05,.01}`), the Stage B frontier-comparison table against
the D-060 baseline, and a report.

## Consequences

**If a calibrated `k_CMI` is found with a lower detection limit at one
or more `N`**: that becomes the new candidate default for a future
composition charter at that `N`, contingent on no other regression —
a concrete, evidence-based improvement, not a re-opening of D-056's
own already-settled calibration question.

**If no surviving `k_CMI` improves on `40` anywhere tested**: `40`
stands as the best already-identified value, and further small-`N`/
small-effect-size accessibility would need a different lever than
`k_CMI` alone — the other options this session already discussed
(more permutations, a different estimator entirely such as RCoT, or a
copula-transform preprocessing step) become the live candidates, each
a separate, larger charter of its own, not an automatic next step.
