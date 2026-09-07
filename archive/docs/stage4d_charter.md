# Stage 4d Charter: Sequential/Greedy Conditioning Engine — Floor Search Below N=750 (R6c)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-031 (Stage 4b) tested the sequential engine only at `N in [750,
1500]`, deliberately reusing D-017/D-018's own comparison points rather
than searching for a floor. That choice answered "can this engine bring
the overlap shape's requirement down to the general `N=750` floor," not
"how low can this engine go below `750`" — a distinct, practically
important question, since a meaningful share of real behavioral studies
fall below `750` entirely. This charter asks that second question
directly.

**Naming note:** this is `Stage 4d`, not `4c` — `4c` is reserved for the
cascading-error stress test named in Stage 4a's own Consequences section
and the R6a milestone in
`outline/information_network_technical_build_plan_v3_2026-08-30.md`,
which this charter does not attempt and does not substitute for.

**What is and is not expected to move.** The sequential engine reuses
the conservative engine's identical per-edge Fisher-z partial-correlation
test unmodified — only the order and conditioning-set selection differ.
That underlying test's own floor is already characterized independent of
composition strategy (Stage 1h/1i, D-009-D-011): decisive failure at
`N<=300`, `N<=600` decisive, `N=650` a near-miss, `N=700` a thin PROCEED,
`N=750` comfortable — for the *general* mechanism, on the *easiest*
motifs. **This charter's default expectation is that the sequential
engine inherits a similar-shaped floor for the hub shape** (no
composition-order complication there) and predicts the **open
question is specifically whether the overlap shape's floor sits closer
to `750` (per D-031's near-miss at `.818`, `.018` short of margin) or
noticeably lower**, given the sequential engine already recovered most
of D-018's gap at `750` itself.

**Predeclared early-stop rule, per the project's own falsification-first
discipline, stated here so it is not decided post hoc:** if hub's
transition lands in the same `[600,700]` region already established for
the base mechanism, and overlap's floor lands anywhere at or above
`650`, this charter's own grid is sufficient to answer the question —
no further downward search charter is needed, and the finding should be
written up as "consistent with the known base-mechanism floor,
composition order does not change it materially below `750`." Only a
surprising result (a floor decisively below `600` for either shape, or
a non-monotonic/unstable transition) would justify a follow-up
charter narrowing the grid further.

## Data-generating process

Identical shapes to Stage 4b, unmodified: hub (`sample_hub(n, .5,
children=3, rng)`) and shared-node overlap
(`sample_overlapping_triangles(n, rng)`). **New `N = [300, 500, 600, 650,
700]`**, chosen to span from a point already known to be decisive for the
base mechanism (`300`) through the exact resolution Stage 1i used to
locate that mechanism's own floor (`550`-`700`, here `500`/`600`/`650`/
`700`) up to just below Stage 4b's own `750`.

**`N=750` is reused as a bookend, not re-simulated**: this charter loads
Stage 4b's own raw evidence (`results/generated/stage4b_hub_overlap/
raw_metrics.csv`), filters to `n == 750`, and concatenates it with fresh
simulation at the five new `N` values — mirroring Stage 1i/2i's own
bookend-reuse methodology exactly, including refusing to re-simulate the
bookend `N`. If that file is unavailable, the run must fail loudly
rather than silently proceeding without the bookend.

Same alpha grid as Stage 4a/4b: `[.50, .30, .20, .10, .05, .01, .005,
.001, .0001]`. Master seed `20260830` (matching Stage 4b, since the
bookend `N=750` rows must share the same seed lineage). **2,000
replicates per new `N`** (development 0-999, validation 1000-1999),
matching Stage 4b's own scale.

## Mechanism

Unchanged: `mintnet.pipeline.sequential_screen_and_prune_detailed`. No
code change from Stage 4a/4b.

## Selection and gate

Identical procedure to Stage 4b: per `(shape, N)`, on development
replicates, an `alpha` is eligible if indirect-edge TPR `>= .80` with
margin `>= .02`, and true-edge FPR `<= .10` with margin `>= .02`. Select
the **largest** eligible `alpha`. Confirm on validation replicates at
the same two thresholds. **PROCEED** for a given `(shape, N)` cell only
if both hold with no recorded error, mirroring Stage 4b's own gate
exactly for direct comparability across the full `N` curve (`300`
through `1500`, six points total per shape once combined with Stage
4b's own `1500` and the reused `750`).

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, bookend source path and its SHA-256, raw per-replicate
per-pair evidence for the five new `N` values, aggregate metrics, the
per-`(shape, N)` decision table spanning all six `N` points, a plot of
indirect TPR vs. `N` per shape with the `.80` gate marked, and a report
stating plainly whether the predeclared early-stop condition was met.

## Consequences

If the early-stop condition is met (see Background): record the located
transition range per shape in `docs/validated_operating_ranges.md` as
informational (this engine still has no validated status pending Stage
4c), and close out this specific sub-line of inquiry without further
downward search charters — per this charter's own predeclared rule, not
a post hoc convenience.

If overlap's floor lands materially below `650` (a genuinely lower floor
than the base mechanism's own established range): this would be a
second, independent line of evidence that composition order — not just
the underlying per-edge test — has real headroom to lower under-powered
shapes' data requirements, worth its own dedicated follow-up
investigating why, rather than filed as a minor footnote.

If hub's floor differs substantially from the base mechanism's own
known `[600,700]` transition (either direction) with no evident
explanation: treat as a discrepancy requiring diagnosis before trusting
any other Stage 4 result, since hub was the shape with no expected
surprises.

This charter does not authorize any user-facing `N` recommendation for
the sequential engine at any `N` — Stage 4c's cascading-error stress
test remains an unconditional precondition, per the R6a milestone.
