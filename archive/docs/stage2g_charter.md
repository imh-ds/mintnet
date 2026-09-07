# Stage 2g Charter: Hub-Composed Pipeline at p=30 (R3i)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-024 validated the composed pipeline at `p=30` for disjoint 3-node
motifs only (chain, fork, triangle) — the direct `p=30` analog of
Stage 2b. Its own consequences explicitly deferred the hub shape: "does
not validate hub, overlap, or other candidate shapes at `p=30` ... each
would need its own charter, mirroring how Stage 2c/2d followed Stage 2b
at `p=15`." This charter is that follow-up — the direct `p=30` analog
of Stage 2c (chain/fork/hub composition), the same relationship Stage
2f had to Stage 2b.

Per the outline's Section 2.1, this combines only already-validated
pieces: the hub-clique conditioning mechanism (D-015, D-016), D-023's
`p=30` screening threshold, and D-012's unchanged `alpha(N)` formula.
No new mechanism is being tested — only whether wiring them together at
`p=30`, with a hub-shaped candidate component instead of a third triad,
behaves the way it did at `p=15`.

**Predeclared expectation, computed from prior charters' own findings
before running anything:** D-023 found screening's per-edge FPR at its
`p=30` rule (`alpha=.0001`) is `~.00012`, essentially exactly `alpha`
itself, regardless of DGP shape (it is a property of the per-pair test,
not of what else is in the network). D-024 confirmed this transfers to
a composed pipeline at `p=30` (final false-edge rate `.0001`-`.0001`,
matching screening alone, replicating D-014's "no rescue" finding).
D-016 found the hub shape composes cleanly at `p=15` (indirect TPR
`.820`-`.853`, true-edge FPR `.000`, shape-validated rate `~.96`).
Combining these: **this charter predicts PROCEED at both `N`**, final
false-edge rate `~.0001` (matching D-024's own figure, since the
null-pair mechanics are unaffected by adding a hub instead of a third
triangle), indirect TPR similar to D-016's `.82`-`.85` (plausibly a
little higher, per D-024's own observed small increase in shape-
validation rate under the stricter `p=30` alpha), and true-edge FPR
`~0`.

## Pipeline (frozen mechanism)

Identical to Stage 2c, using D-023's `p=30` screening threshold in
place of D-013's `p=15` one:

1. **Screen** every `C(30, 2) = 435` pairs at `alpha = .0001` (D-023's
   `p=30` rule — reused directly, not re-derived: this DGP's true:null
   ratio, `12:423`, is if anything slightly *more* favorable than the
   triangle DGP's `9:426` that `alpha=.0001` was validated against in
   D-023, so no new threshold-selection step is needed).
2. **Group** candidate edges into connected components.
3. **For each validated clique shape** (3-node triad or 4-node hub,
   `mintnet.pipeline.compose.VALIDATED_CLIQUE_SIZES`): apply DPI,
   `alpha = f(N)` (D-012).
4. **Every other candidate component**: retained unmodified.

No new code: the same generalized `compose_screen_then_prune` used by
every composition charter since D-016.

## Data-generating process

Identical to Stage 2c, extended to `p=30`: chain (`X1->X2->X3`, columns
0-2), measured fork (`X4<-X5->X6`, columns 3-5), a hub with 3 children
(column 6 hub, columns 7-9 children), and **20** independent noise
columns (10-29) — up from Stage 2c's 5, the same "keep the true-motif
structure fixed, add noise columns to reach the new `p`" principle
Stage 2e/2f used. Strength `.5`, `N = [750, 1500]`, master seed
`20260829`, 2000 replicates (development 0-999, validation 1000-1999)
— unchanged from every prior screening/composition charter.

**Ground truth**, identical structure to Stage 2c (only the noise count
differs): **12 true candidate pairs** (chain's 3 + fork's 3 + hub's
`C(4,2)=6`), **7 true direct edges** (chain's 2 + fork's 2 + hub's 3
hub-child edges), **5 indirect/prunable edges** (chain's 1 + fork's 1 +
hub's `C(3,2)=3` child-child pairs), **423 null pairs**
(`C(30,2) - 12`).

## Selection and gate

No selection step — both `alpha` values are already frozen (D-012,
D-023). Per `N`, on validation replicates (1000-1999):

1. **Indirect-edge pruning TPR** (5 prunable pairs) `>= .80`.
2. **True-edge retention** (7 true direct edges) — FPR `<= .10`.
3. **Final false-edge rate** does not exceed screening-alone's own rate
   (computed within the same run, per replicate) by more than `.01`
   absolute — the same no-regression check every composition charter
   has used.

**PROCEED** for a given `N` only if all three hold with no recorded
error. Descriptive: the fraction of candidate components that actually
achieve their validated shape (a clean triad for chain/fork, a clean
4-clique for the hub), to compare against D-016's `~.96` and D-024's
slightly higher `~.98`-`.99`.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence, aggregate metrics, the per-N
decision table, report, and figures — identical evidence set to
Stage 2c/2f, at `p=30`.

## Consequences

If PROCEED at both `N`: the generalized composed pipeline is validated
for networks containing a 4-node hub-clique candidate component (mixed
with disjoint triads) at `p=30`, using D-023's screening threshold.
Combined with D-024, this validates both tested candidate shapes'
composition at `p=30`. It does **not** validate the shared-node-overlap
shape at `p=30` (its own follow-up, mirroring Stage 2d after Stage 2c
at `p=15` — and one where D-018's `N=750` weak-signal caveat might
interact with `p=30`'s stricter screening threshold in a way that is
not safe to assume from either finding alone), bootstrap stability at
`p=30` for either shape, or `p` values beyond `30`.

If REASSESS: since every constituent piece is independently validated
at this `p`/`N` (hub conditioning: D-015/D-016; screening: D-023;
composition at `p=30`: D-024, for a different shape), a failure would
specifically implicate an interaction between the hub shape and `p=30`
screening specifically — worth its own investigation, not an assumption
that D-024's triangle-shape result was somehow shape-independent.
