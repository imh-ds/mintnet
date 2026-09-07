# Stage 8b Charter: Chain/Fork Margin Recalibration (main)

Status: **FROZEN before results**
Date: 2026-09-07

## Background and objective

D-066 (Stage 8a) found the Tier-0 margin score monotonic everywhere
but numerically calibrated (ECE `<= 0.10`) only for retain-dominant
fixtures (`triangle`, `weak_edge_triangle`); `chain`/`fork` failed
tolerance (`.111`-`.146` across `N`), traced to a specific, isolable
cause: below margin `0.9`, every scored decision is the indirect-pair
prune, whose empirical accuracy sits roughly flat (`~0.80`-`0.93`
depending on `N`) rather than climbing with margin. This charter asks
the direct follow-up D-066 itself named as an open option: can an
explicit recalibration mapping bring `chain`/`fork` within tolerance,
without touching raw margin or degrading the fixtures that already
pass?

**No new evidence collection.** Stage 8a's own `raw_metrics.csv`
(`R=5000` per condition/`N`, 1,260,000 scored decisions) already
contains everything a calibration mapping needs: `margin`, `n`,
`correct`. This charter fits and validates a mapping entirely from
that already-collected evidence — the same "compute once, threshold
many times" reuse this project has relied on since Stage 1b, applied
here to fitting rather than re-thresholding.

## Mechanism

**Method**: isotonic regression (`sklearn.isotonic.IsotonicRegression`,
already a declared project dependency, `increasing=True`) — a
monotonic, non-parametric fit of `P(correct | margin)`. Chosen because
D-066 already confirmed monotonicity holds; isotonic regression adds
no shape assumption beyond that, unlike a sigmoid (Platt) fit.

**One curve per `(motif_family, N)`**, not pooled across either axis:

- **Per `N`**: D-066 showed the flat-accuracy level itself shifts with
  `N` (`~0.80` at `N=300` to `~0.93` at `N=3000`); a single curve
  would misfit both ends. Six curves per motif family, one per Stage
  8a's own tested `N in {300,500,750,1000,1500,3000}`.
- **Per motif family**: checked directly, not assumed — `weak_edge_
  triangle`'s own null (`target_rho=0`) is structurally the same
  single-conditioning-variable test as chain/fork's indirect pair, and
  it is already well-calibrated (ECE `.03`-`.037`). The flat-accuracy
  artifact is specific to chain/fork's own null p-value distribution,
  not a general property of prune decisions. Pooling would risk
  distorting an already-passing fixture's own calibration or diluting
  the correction chain/fork actually needs.

Curves are fit for all four motif families (`chain`, `fork`,
`triangle`, `weak_edge_triangle`) for a uniform code path and a direct
consistency check — `triangle`/`weak_edge_triangle`'s own fitted curves
are expected to come out close to the identity line, since D-066
already found them within tolerance; this is reported, not assumed.

**Development/validation split**: replicate index `0`-`2499`
(development, curve fitting) and `2500`-`4999` (validation, the gate
below) — a fixed, non-data-driven contiguous split decided before
looking at any per-replicate accuracy pattern, mirroring Stage 1b's
own dev/val split discipline exactly (not a new convention introduced
post-hoc to fit this result).

**Out-of-range behavior, disclosed rather than silently handled**: a
query at an `N` not exactly matching one of the six tested values
snaps to the *nearest* tested `N`'s own curve — no interpolation
between tested `N` values, since an interpolated curve's own
calibration has not itself been validated at any untested `N`. A query
at `N < 300` or `N > 3000` raises, rather than extrapolating past the
tested range (mirrors D-065's `N>=1500`-only precedent).

**API**: `mintnet.confidence.recalibration.calibrated_margin(margin,
n, motif_family)`, additive alongside `mintnet.confidence.edge_margin`
— raw margin remains available everywhere for ordinal use; this is an
opt-in correction, not a replacement.

## Selection and gate

**PROCEED**: on the validation replicates (`2500`-`4999`, never used
for fitting), the recalibrated output's own ECE is `<= 0.10` for
`chain` and `fork` at every tested `N` — the same tolerance Stage 8a
itself used, applied now to the corrected score rather than raw
margin.

**REASSESS**: the fitted mapping does not generalize to validation at
some `(motif, N)` cell — a real, not assumed-away, possible outcome.
Would indicate the development half's own margin-accuracy relationship
does not transfer even within the same `N`, a different and more
concerning finding than D-066's own.

## Explicit non-goals

- **No change to `edge_margin` or raw Tier-0 output.** This is a
  separate, optional correction, not a redefinition.
- **No interpolation across untested `N`.** Nearest-tested-`N`
  snapping only, disclosed as a real approximation at any `N` between
  tested points.
- **No claim outside `N in [300, 3000]`.**
- **No recalibration of CMIknn or structured-density margins.** Same
  scope restriction as Stage 8a itself (D-053-only, unrestricted
  `PROCEED`).
- **No new significance-test evidence.** Every input to this charter
  already exists in Stage 8a's own `raw_metrics.csv`.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the fitted
isotonic curves (serialized per `(motif_family, N)`), the
development-set fit diagnostics, the validation-set ECE table (the
gate's own direct evidence), the gate decision, and a report.

## Consequences

**If PROCEED**: chain/fork's own indirect-edge prune decisions gain a
validated, N-aware recalibrated confidence score — the Tier-0
diagnostic's practical caveat from D-066 (ordinal-only for that
decision type) narrows to specifically querying it at an `N` outside
`[300, 3000]`, or for a motif this mapping was never fit for.

**If REASSESS**: raw margin remains the only available score for
chain/fork's prune decision, explicitly ordinal-only per D-066 — this
charter's own failure would itself be a finding worth a decision-log
entry (the development/validation gap would need its own diagnosis
before any further recalibration attempt).
