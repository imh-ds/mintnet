# Stage 1L Charter: Multi-Variable Conditioning for Shared-Node Overlap (R3e)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

Stage 1k validated multi-variable conditioning on a hub/star topology (one
shared cause, independent children; D-015), and Stage 2c wired that shape
into the composed pipeline (D-016). Both used the same underlying
topology: one central node, several nodes connected only to it. A
genuinely different topology — two separate motifs *overlapping at a
shared node* (e.g., two triangles sharing one variable, rather than one
hub causing several children) — has not been tested, and there is no
guarantee it behaves the same way: a shared-node overlap has two
distinct "hub-like" roles feeding into each other, not one hub radiating
outward.

**A real complication found before writing this charter, not assumed
away:** the correlation between two variables on *opposite* branches of
the overlap (e.g., a member of triangle A and a member of triangle B,
connected only through the shared node) is markedly weaker than a hub's
child-child correlation was. A quick calculation showed screening's power
to detect this weak cross-branch correlation is only `~66%` at `N=750`
(vs. `~98%` at `N=1500`) at the already-validated `alpha=.001` — meaning
the candidate component frequently will **not** form a clean, fully-
connected clique at `N=750`, unlike the hub case where detection was
comfortable at both `N`. This charter deliberately separates two
questions rather than conflating them:

1. **Does the conditioning mechanism itself work on this topology**,
   given a clean candidate clique? (tested here, in isolation, exactly as
   Stage 1k did — DPI is handed the full clean component directly,
   bypassing whether screening would actually detect it that cleanly.)
2. **How often does screening actually produce a clean clique for this
   DGP?** (explicitly out of scope for this charter — it is a full-
   pipeline, screening-detection question, not a conditioning-mechanism
   question, and conflating them would violate the same
   validate-mechanisms-independently principle every prior charter in
   this line has followed. A future charter, mirroring Stage 2c's role
   after Stage 1k, would test this.)

## Data-generating process

Two triangles sharing node 2: variables `{0, 1, 2}` form one triangle,
`{2, 3, 4}` form another, both using the same symmetric `-0.25`
off-diagonal precision structure as Stage 1's `balanced` triangle fixture
(deliberately simple and symmetric — not compounding this new topology
question with the asymmetric-triangle question `balanced`/`moderate`/
`strong` already answered separately). Verified positive definite before
freezing (eigenvalues `[.360, .75, 1.25, 1.25, 1.39]`, all positive).

**Ground truth**: true direct edges (6): `(0,1)`, `(0,2)`, `(1,2)`
[triangle A], `(2,3)`, `(2,4)`, `(3,4)` [triangle B]. Indirect/prunable
edges (4): `(0,3)`, `(0,4)`, `(1,3)`, `(1,4)` — cross-branch pairs, real
but weak nonzero unconditional correlation (`~.135`, vs. `~.37` for
within-triangle pairs) purely through the shared node, with no direct
structural connection.

`N = [750, 1500]` (Stage 1/2's shared validated regime), master seed
`20260829`, 2000 replicates (development 0-999, validation 1000-1999).

## Mechanism

Unchanged: `mintnet.dpi.multi_conditional`'s general partial-correlation
test, conditioning each edge on all 3 other nodes in the 5-node
component — one more conditioning variable than Stage 1k's hub case (2).
`alpha = f(N)` from the unmodified D-012 formula, tested directly as in
Stage 1j/1k (no new grid search).

## Selection and gate

No selection step. Per `N`, on validation replicates (1000-1999):

1. Indirect-edge pruning TPR (4 cross-branch pairs) `>= .80`.
2. True-edge retention (6 within-triangle pairs) — FPR `<= .10`.
3. Both margins `>= .02`.

**PROCEED** for a given `N` only if all three hold with no recorded
error.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence, aggregate metrics, the per-N
decision table, report, and figures.

## Consequences

If PROCEED at both `N`: the conditioning mechanism generalizes to
shared-node overlap, not just hub/star topology — meaningful evidence
that "condition on all other candidate-component nodes" is a genuinely
general rule rather than one that happened to work for stars. This does
**not** by itself extend `VALIDATED_CLIQUE_SIZES` or wire anything into
`mintnet.pipeline.compose` — a future charter would need to test the
screening-detection-rate question above before that extension could be
trusted end to end, given the power calculation showing clean-clique
formation is unreliable at `N=750` for this specific DGP.

If REASSESS: the mechanism validated for hub/star topology does not
automatically generalize to other topologies, which would be an important
scope limitation for any future extension.
