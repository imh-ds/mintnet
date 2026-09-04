# Stage 7b Charter: Power-Curve / Operating-Frontier Mapping for the Calibrated CMI Mechanism (mi-native)

Status: **FROZEN before results**
Date: 2026-09-04

## Background and objective

D-059 (Stage 7) found that the isolation-tier gate's two criteria —
chain/fork indirect-edge pruning TPR `>= .80` and triangle true-edge
retention FPR `<= .10` — cannot both be satisfied by any `alpha` in
`(0, 1)` for the `strong` triangle fixture specifically, at the
calibrated setting (`k_CMI=40`, `k_perm=3`, `permutations=199`) and
the tested `N in {750, 1500}`. This was proven directly, not inferred:
chain/fork pruning tracks `1 - alpha` almost exactly across the full
grid, `alpha <~ .2` is required to meet the TPR floor, and the
`strong` family's own FPR does not clear `.10` until `alpha = .5`, by
which point chain/fork TPR has already collapsed to `.543`. The
`strong` fixture's third edge has a true Gaussian conditional MI of
only `~0.0032` nats (partial correlation `-0.08`) — D-059's own
revision reframed this as an expected efficiency cost of a
nonparametric significance test relative to the analytically correct
Fisher-z test at a near-null Gaussian alternative, not a defect, and
recommended mapping the actual detection limit rather than re-tuning
the estimator against this one fixture (a real overfitting risk).

**This charter answers that specific question**: as a function of
effect size (`|partial correlation|` on the weak edge) and `N`, where
— if anywhere — does a feasible operating point exist that
simultaneously satisfies both an indirect-edge-pruning requirement and
a direct-edge-retention requirement, at the calibrated estimator
setting held fixed throughout?

**This is a descriptive/diagnostic charter, not a mechanism gate** —
mirroring Stage 5/Stage 6a's own R6-style structure. It characterizes
the already-calibrated mechanism's own operating characteristics; it
does not test a new mechanism, and reaching no feasible point anywhere
tested is itself a complete, reportable answer (a detection limit),
not a failure requiring another REASSESS cycle.

## Data-generating process

A new, minimal fixture family — `weak_edge_triangle(target_rho, n,
rng)` — extending the existing `strong` triangle fixture's own
structure rather than inventing a new one: same two dominant edges
(`partial correlation` `.45` and `.25`, matching `strong`'s own
off-diagonal precision entries `-.45`/`-.25`), with the third edge's
own target partial correlation swept continuously instead of fixed at
`-.08`. Since these fixtures use a unit-diagonal precision matrix,
`partial_correlation(i,j) = -precision[i,j]` exactly (no separate
derivation needed) — the same convention `mintnet.simulation.motifs`
already uses for `balanced`/`moderate`/`strong`. Positive-definiteness
is checked the same way (`np.linalg.cholesky`) and is a required,
not assumed, property for every swept value — a value that fails PD
is dropped and reported, not silently skipped.

**Effect-size grid**: `|target_rho| in {0, .04, .06, .08, .10, .12,
.15, .20, .25}`. `0` is included deliberately as an in-family null
check — D-059's own `1 - alpha` relationship was established on
chain/fork's own different conditioning structure (three independent
variables), not this triangle's own (two fixed correlated edges plus
one varying edge); this charter does not assume that calibration
transfers across DGP structures without checking. `.08` reproduces
D-059's own `strong` fixture exactly, for direct continuity. `.25` is
included to establish the upper end where full separation from the
null is expected, bounding the frontier plot.

**`N` grid**: `{750, 1500, 3000}`. The first two match Stage 7's own
tested range; `3000` is new, added specifically to test whether
D-059's own "nearly flat" `750->1500` improvement trend continues to
flatten (supporting a structural, not merely data-hunger, ceiling) or
whether it resumes improving at a larger `N` than previously tested.

**Estimator/test setting**: `k_CMI=40`, `k_perm=3`, `permutations=199`
— D-056/D-057's own calibrated values, held completely fixed
throughout this charter. No retuning of any kind happens here, by
design — see "Explicit non-goals."

**`alpha` grid**: since a single CMI/p-value computation per pair
supports re-thresholding at any number of `alpha` values for free
(the same "compute once" property Stage 7's own runner already
exploits), this charter uses a substantially finer grid than Stage
7's own 9-value one: `alpha in {.01, .02, ..., .50}` (uniform step
`.01`, 50 values) — fine enough to localize a crossing point
precisely if one exists, coarse enough to stay clear of the
`permutations=199` resolution floor (`.005`) except at its own lowest
value, which is retained deliberately as a boundary marker, not
dropped.

## Compute-cost disclosure

Per Stage 7's own charter precedent: before finalizing replicate
counts, measure real wall-clock cost per replicate at `N=3000`
directly (untested territory — Stage 7's own timing data covers only
`N<=1500`). `N=750`/`1500` costs are already known from Stage 7's own
execution (~`21`-`70`s per replicate for a 3-node motif's full set of
pairwise tests); `N=3000`'s own cost is not assumed to extrapolate
linearly, given KNN/tree-query costs typically scale worse than
linearly with `N`. A provisional planning figure (not a commitment):
`200`-`400` replicates per `(target_rho, N)` cell, sharded by
`(target_rho, N, batch)` mirroring `mintnet.experiments.stage7_isolation`'s
own batching design, dispatched via GitHub Actions from the first run
(not local execution), consistent with this project's own standing
infrastructure discipline.

## Reporting requirements

For every `(target_rho, N)` cell, across the full `alpha` grid:

1. **Empirical power** `P(reject H0 | H1)` (rejection rate) for the
   weak edge specifically — the primary output.
2. **Empirical null behavior** for the `target_rho=0` cells: rejection
   rate as a function of `alpha`, compared directly against `1 -
   alpha`(this charter's own in-family calibration check, not
   assumed from D-059).
3. **The two dominant edges' own retention rate**, as a sanity check
   that they remain reliably retained regardless of the weak edge's
   own behavior (expected to closely match `strong` fixture's own
   already-established near-`1.0` retention for those edges).
4. **The operating-frontier plot/table**: for each `(target_rho, N)`,
   whether any `alpha` exists where the weak edge's own power `>=
   .90` (mirroring the `<=.10` FPR requirement inverted) simultaneously
   with an indirect-edge pruning rate `>= .80` at that same `alpha`
   (using this charter's own in-family null cells, per point 2, as the
   indirect-edge proxy — not re-borrowing chain/fork's own numbers from
   a different DGP structure). Report the specific `alpha` range where
   feasibility holds, if any, per `(target_rho, N)` cell.
5. **The detection-limit summary**: the smallest `|target_rho|`
   (interpolating between tested grid points if needed, or reporting
   "not reached within the tested range" if none qualifies) at which a
   feasible operating point exists, per `N` — directly answering the
   question D-059's own revision posed.

## Explicit non-goals

- **No retuning of `k_CMI`, `k_perm`, or `permutations`.** Held fixed
  throughout, by design — this charter maps the frontier for the
  *already-calibrated* mechanism; retuning against these same
  fixtures before this mapping exists is exactly the overfitting risk
  D-059's own revision flagged. A follow-up charter asking whether
  retuning shifts the frontier is explicitly named as later,
  contingent work, not part of this one.
- **No change to the Stage 7 gate's own criteria.** This charter does
  not propose loosening `.80`/`.10` after finding they're hard to
  satisfy — it characterizes where they can and cannot be satisfied at
  all. Any future decision to revisit those thresholds is a separate,
  explicit decision, not an automatic consequence of this charter.
- **No nonlinear/non-Gaussian DGP.** Same Gaussian-only reasoning as
  every prior mi-native charter — this remains separate, later work.
- **No resolution of the `permutations=199` floor.** `alpha=.01` sits
  above the floor (`.005`) and is retained; nothing here changes `B`.
- **No composition into a retain/prune mechanism.** Purely
  characterization of the calibrated test's own operating
  characteristics in isolation.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the up-front `N=3000` timing measurement and its own
resulting replicate-count decision, raw per-replicate evidence (weak-
edge CMI/p-value, both dominant-edge CMI/p-values, per replicate),
the full per-`alpha` power/null tables, the operating-frontier
summary, and a report.

## Consequences

**If a feasible operating point is found** at one or more `(target_rho,
N)` cells: this directly informs (but does not by itself authorize)
a future Stage-1-equivalent composition charter's own choice of `N`
floor and `alpha`, restricted to DGPs whose true effect size is at or
above the mapped detection limit — a scoped, honest constraint, not a
claim of general capability below that limit.

**If no feasible operating point is found anywhere tested**: this is
itself the charter's own complete answer — a characterized detection
limit for the calibrated CMIknn/local-permutation mechanism on
Gaussian data at this estimator setting. The next decision (not
automatic, requiring explicit executive judgment per this project's
own standing discipline) would be among: revisiting the gate's own
`.80`/`.10` thresholds for the MI-native track specifically (with the
reasoning made explicit, not silently loosened), a dedicated
retuning charter testing whether `k_CMI`/`k_perm` shifts the frontier
without breaking D-056's own Type-I calibration, or accepting this as
a disclosed, bounded limitation of the current mechanism relative to
Fisher-z on near-null Gaussian effects specifically.
