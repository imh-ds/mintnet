# Stage 2i Charter: Locating the Overlap Shape's N Floor at p=30 (R3k)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-026 found the shared-node-overlap DGP's composed pipeline REASSESSes
at both tested `N` under `p=30`'s stricter, automatically-selected
screening threshold (D-023: `alpha=.0001`) — `N=750` decisively
(overlap TPR `.6365`), but `N=1500` only narrowly (`.762`, `.038` below
the `.80` gate). That near-miss is the actionable part of D-026's own
consequences: "the true floor for this shape at `p=30` is plausibly
just above `1500`, not far beyond it ... a locatable question." This
charter locates it, mirroring the exact methodology Stage 1i used to
locate the general DPI floor between `N=500` and `750` (D-010) — test
new sample sizes inside and just past the gap, reuse already-frozen
evidence for the known bookend, and report a per-`N` table rather than
a single verdict.

This is not a new mechanism or a new DGP: every piece (screening at
`alpha=.0001`, DPI at `alpha=f(N)`, the overlap DGP) is already frozen
from D-023/D-012/D-018. The only new variable is `N` itself.

**Predeclared expectation, computed from the same Fisher-z power
calculation used in `docs/stage2h_charter.md`, extended past `N=1500`:**

| `N` | naive clean-clique rate (power^4) | D-026's own `N=1500` correction, applied |
|---|---|---|
| `1500` (D-026, reused) | `.697` | `.753` observed (`+.056` absolute) |
| `1600` | `.774` | `~.82`-`.83` (est.) |
| `1750` | `.860` | `~.90`-`.91` (est.) |
| `2000` | `.943` | `~.95`-`.96` (est.) |
| `2500` | `.993` | `~.99` (est.) |

The "correction" column is an estimate, not a second independent
derivation — D-026 observed the positive correlation among the four
cross-branch tests boosts the naive independent-power estimate by a
shrinking amount as power approaches `1` (a larger absolute boost in
the marginal region near `N=1500`/`1600`, negligible by `N=2500`).
**This charter predicts the crossover — REASSESS transitioning to
PROCEED — lands somewhere in `[1600, 1750]`**, with `2000` and `2500`
included as safety-margin points to confirm a clear, comfortable
PROCEED exists within `alpha(N)`'s own validated interpolation range
(`N` in `[700, 3000]`, D-012) rather than assuming it without checking.

## Data-generating process

Identical to Stage 2h: `p=30`, chain/fork/shared-node-overlap DGP, 19
noise columns, strength `.5`, master seed `20260829`, screening
`alpha=.0001` (D-023), DPI `alpha=f(N)` (D-012). **New sample sizes:
`N = [1600, 1750, 2000, 2500]`**, 2000 replicates each (development
0-999, validation 1000-1999) — fresh seed positions, since no prior
data exists at these `N`. **`N=1500` is not re-simulated**: this
charter reuses its raw evidence and decision directly from
`results/generated/stage2h_overlap_composition_p30/`, per Stage 1i's
own bookend-reuse practice.

## Mechanism

Unchanged from Stage 2h. No new code.

## Selection and gate

No selection step. Per `N` (the reused `1500` bookend plus the four new
values), on validation replicates (1000-1999), Stage 2h's exact five
criteria: chain indirect TPR `>= .80`, fork indirect TPR `>= .80`,
overlap indirect TPR `>= .80`, true-edge FPR `<= .10` pooled, final
false-edge rate within `.01` of screening-alone's own rate.

**Output is a five-row per-`N` table** (`1500, 1600, 1750, 2000, 2500`),
not a single global status, per Stage 1i's own reporting convention.

## Required evidence

Resolved configuration, this charter's SHA-256, a pointer to (and hash
of) the reused `N=1500` rows from Stage 2h's raw evidence, commit and
runtime metadata, raw per-replicate evidence for the four new sample
sizes, aggregate metrics, the five-row per-`N` decision table, report,
and figures (overlap TPR / clean-clique rate vs. `N`, extending Stage
2h's own figure).

## Consequences

If the table shows a clean, monotonic transition (REASSESS through some
point, then PROCEED from some `N` onward): that `N` becomes this
shape's `p=30` floor, and `docs/validated_operating_ranges.md`'s D-026
row should be updated to state it explicitly, replacing "the true floor
is unlocated" with a located value.

If the table is not monotonic (an isolated PROCEED surrounded by
REASSESS, or a REASSESS at `2500` after a PROCEED at `2000`): treat it
as evidence of noise near a genuine boundary, per Stage 1i's own
precedent for exactly this pattern, and do not claim a located floor —
finer resolution or more replicates near the ambiguous `N` would be its
own further charter, not assumed here.

Either way, this charter does not revisit whether the overlap mechanism
itself works (D-017 already validated that) or whether `p=30`'s
screening threshold is correct for strong-signal shapes (D-024, D-025
already validated that) — it only locates where, for this one
weak-signal shape, `N` becomes large enough to compensate for `p=30`'s
stricter automatic threshold.
