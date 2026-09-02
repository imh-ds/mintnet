# Stage 6a Charter: Conditioning-Set Architecture — Growing-Subset DPI vs. Full-Component Conditioning (mi-native prep)

Status: **FROZEN before results**
Date: 2026-09-01

## Background and objective

This charter opens the `mi-native` research track, but **uses no new
estimator** — it is a diagnostic architecture experiment on the
existing, already-validated Fisher-z partial-correlation primitive
(`mintnet.dpi.multi_conditional.compute_partial_correlation_evidence`),
run on the `mi-native` branch because its purpose is to determine the
conditioning-set dimension a future conditional-MI estimator actually
needs to support — not to change or claim anything about MI itself.

Two facts drive this charter, both established in this project's own
prior evidence, not assumed here:

1. **Conditional-independence testing is required**; classical
   pairwise-MI magnitude-ratio DPI (no conditioning at all) was
   directly falsified on this project's own required triangle motif
   using real KSG-estimated MI (`docs/decision_log.md` D-002).
2. **Full-component conditioning (condition on every other node in a
   validated clique) was never shown to be *necessary*** — it was
   introduced as "one principled candidate answer" among several named
   alternatives, chosen for simplicity within the closed-form Gaussian
   architecture (`docs/stage1k_charter.md`), and it has a known,
   measured cost: D-052 found a material share of MINT's own residual
   false positives are edges that never got conditioned on at all,
   because they landed outside a validated clique shape and this
   architecture has no way to test them.

**Hypothesis under test:** a PC-style growing-subset search — test
conditioning sets of size `1, 2, 3, ...` drawn from a candidate edge's
own local component, pruning as soon as *any* tested subset fails to
reject independence (the same OR-rule logic already implemented for
the Stage 5e PC comparator) — run using MINT's own screened candidate
graph as the starting adjacency (not PC's from-scratch complete graph)
will (a) resolve most retain/prune decisions at a *lower* conditioning
dimension than the current "condition on everyone" design, (b) extend
naturally to components the current architecture skips entirely
(non-clique and isolated two-node components), directly testing
whether it recovers some of D-052's passthrough gap, and (c) reveal
the actual maximum conditioning dimension this project's own validated
DGPs require — the number that determines how ambitious `mi-native`'s
conditional-MI estimator needs to be.

## Mechanism: growing-subset DPI

New, additive module (does not modify `mintnet.pipeline.compose` or
`compose_screen_then_prune` — both remain available unmodified for
direct comparison). For every candidate edge `(i, j)` in *any*
connected component of the screened candidate graph (size `>= 2`, not
restricted to validated clique shapes):

1. Let `pool` be every other node in `(i, j)`'s own connected
   component.
2. For `size = 1, 2, ..., min(len(pool), 4)` (a disclosed, fixed
   search-depth cap — see "Explicit non-goals" for why `4`): for every
   subset `S` of `pool` of that size, run
   `compute_partial_correlation_evidence(data, i, j, S)` at
   `alpha(N)` (D-012's general formula, reused unmodified — already
   validated at `|S| in {1, 2, 3}` without refitting, per
   `docs/stage1k_charter.md`/`docs/stage1l_charter.md`, D-015/D-017).
   If any subset's `p_value > alpha`, **prune** `(i, j)` immediately
   and record the triggering `size`.
3. If every tested subset up to the cap rejects (or `pool` is empty),
   **retain** `(i, j)` and record the largest `size` actually reached
   (`0` if `pool` was empty — an isolated two-node component, the same
   case that currently passes through unconditioned).

This is deliberately the *simplest* growing-subset design — the same
OR-rule PC itself uses, no attempt to pick a "smarter" reduced pool
(e.g. Stage 1k's own separately-named "shared neighbors" idea, checked
during this charter's own design phase and found to degenerate to "all
other clique members" whenever the component is already a confirmed
clique, since every other member of a clique is by definition a shared
neighbor — so it offers no reduction there and is not a distinct
design to test).

## Data-generating processes

Two tiers, mirroring this project's own established discipline of
testing a mechanism in isolation before testing it composed:

**Isolation tier (no screening, no noise, mechanism only):**
- Triad (`balanced`/`moderate`/`strong`, `mintnet.simulation.motifs`)
  — trivial control; growing-subset search can only ever reach
  `size=1` here (component size `3`), so this shape must reproduce
  full-component DPI's own numbers exactly, not just approximately —
  a built-in correctness check on the new implementation itself.
- Hub (`sample_hub`, `children=3`) — full-component conditioning uses
  `size=2` for every child-child pair; tests whether growing-subset
  search resolves these at `size=1` instead.
- Overlapping triangles (`sample_overlapping_triangles`, 5 nodes) —
  full-component conditioning uses `size=3`; the sharpest test of
  whether that dimension is actually needed, and (since this shape has
  genuine true edges, not just indirect ones to prune) the sharpest
  test of whether the OR-rule's growing search costs true-edge recall,
  mirroring D-051's own PC weak-edge finding.

`N = [750, 1500]` (this project's shared validated regime for isolated
motifs), strength `.5` for the hub, `2,000` replicates per cell,
development `0`-`999` / validation `1000`-`1999`, master seed
`20260829` (Stage 1's own tag, since these are Stage-1-style isolated
motifs, not Stage 5's composed networks).

**Composed tier (the actual target-use setting):** `chain_fork_hub`
and `overlap`, identical DGPs, full `N` grid, `alpha(N)`, and
condition-seed derivation as D-047/D-051/D-052 (`stage5a`'s own
registry and `_condition_seed`, unchanged) — paired against that same
existing evidence, not re-derived. This tier is where D-052's own
passthrough-gap hypothesis gets a direct test: does extending
conditioning to every connected component (not just validated cliques)
change the false-positive rate MINT's own D-052 diagnostic measured?

## Metrics and reporting

Per `(dgp/motif, N)`: precision, recall, F1, SHD for growing-subset DPI
and, in the same row, current full-component DPI's own numbers (D-047
for the composed tier's baseline; the isolated-motif tier's own
baseline computed fresh here since no isolated-mechanism baseline with
this exact grid/seed exists yet — both run on identical draws, paired
design). **The conditioning-set-size distribution actually used**,
separately for pruned and retained edges, separately for true and
false edges where ground truth allows it — this is the charter's own
primary required output, more central than the accuracy comparison.

## Explicit non-goals

- **No new estimator.** Partial correlation throughout; this charter
  says nothing about MI directly. Its output is a dimensionality
  target for `mi-native`'s own future estimator-validation charter.
- **No production pipeline change.** `compose_screen_then_prune`
  remains untouched; this is a diagnostic comparison, exactly the
  standing D-052 held.
- **Search-depth cap of `4`, not unbounded.** Fixed before results:
  the largest conditioning dimension ever validated in this project is
  `3` (the 5-node overlap shape); `4` gives one step of headroom
  without inviting combinatorial blowup on the composed `p=15`
  networks' occasionally larger candidate components. If the cap is
  ever hit, that is itself reported (a diagnostic flag), not silently
  absorbed into "retain."
- **No claim about which design should become the production
  mechanism.** Descriptive, like every R6 charter — a mixed picture
  (better precision, worse recall, different dimension needed) is a
  complete and useful answer, not a reason to force a verdict.

## Decision structure

Descriptive. Predeclared reporting requirements, fixed now:

1. **Dimension finding**: report, per shape, the maximum
   conditioning-set size actually used by any retained or pruned edge
   across the full grid — this is the charter's central deliverable.
2. **Accuracy comparison**: per shape, whether growing-subset DPI's
   F1 is comparable-to-or-better (within `.01`, mirroring this
   project's own established tolerance) than full-component DPI's, at
   a majority of tested `N`.
3. **Recall check**: explicit, separate from F1, per shape — has
   growing-subset DPI's OR-rule cost any true-edge recall relative to
   full-component DPI's, mirroring D-051's own PC finding. This gets
   its own reported sentence regardless of the answer.
4. **Passthrough-gap check (composed tier only)**: does extending
   conditioning to non-clique components change the false-positive
   rate relative to D-052's own measured baseline.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence for both mechanisms at every
cell (both tiers), and a report presenting the dimension-finding table,
the accuracy comparison, the recall check, and the passthrough-gap
check.

## Consequences

Directly determines the scope of `mi-native`'s own first real charter
(the conditional-MI estimator itself): if the maximum dimension found
here is `1`, Runge's single-variable conditional-MI-plus-local-
permutation method is sufficient and the estimator-validation charter
can be scoped narrowly; if `2` or `3` is genuinely needed anywhere,
the estimator work must handle multivariable conditioning from the
start, a substantially harder validation target. If growing-subset DPI
also improves precision or recovers D-052's passthrough gap without a
material recall cost, that is a candidate finding worth a follow-up
implementation charter for the Gaussian baseline (`main`) too — noted
here, not decided or acted on by this charter. Does not alter D-047
through D-052.
