# Stage 2b Charter: Screening + DPI Composition (R3b)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

Stage 1 validated conditional-independence pruning on isolated,
hand-picked three-node motifs (`docs/decision_log.md` D-008 through
D-012). Stage 2 validated candidate-edge screening on a `p=15` network,
in isolation, never applying DPI to its output (D-013). Per the outline's
Section 2.1 ("validate mechanisms independently before composing them"),
neither charter tested what happens when they run as one pipeline. This
charter tests exactly that composition, and only that — not bootstrap,
not a third mechanism, not a larger or differently-shaped network.

**A real design gap this composition exposes, not resolved by either
prior charter:** Stage 1's DPI test conditions a candidate edge on one
specific third variable — the known mediator of a hand-built 3-node
motif. In a real network, after screening produces a set of candidate
edges, which variable (if any) should a given candidate edge condition
on? This charter does not attempt to answer that in general. It uses
Stage 2's exact DGP — three *disjoint* motifs (chain, fork, triangle) in
noise, sharing no variables — specifically because it makes the answer
unambiguous: candidate edges naturally group into connected components,
and each true-motif component is exactly the 3-node case Stage 1 already
validated. **Candidate components that are not exactly this shape
(more than 3 nodes, or fewer than 3 candidate edges among 3 nodes) are
explicitly out of scope: this charter passes them through unmodified,
does not apply DPI to them, and flags this as a real, distinct, harder
question for a future charter with a DGP built to test it (overlapping
motifs, larger candidate components).**

## Pipeline (frozen mechanism)

1. **Screen** every `C(p, 2)` pair using Stage 2's validated rule:
   uncorrected Fisher-z on raw correlation, `alpha = .001` (D-013's
   winning rule at both tested `N`).
2. **Group** the resulting candidate edges into connected components.
3. **For each 3-node component with exactly 3 candidate edges** (a
   "candidate triad"): apply Stage 1's validated conditional-independence
   test to each edge, conditioning on the third node, using
   `alpha = f(N)` from the validated formula (`docs/decision_log.md`
   D-012: `alpha(N) = 0.5222 - 0.0566 * ln(N)`) — the first real use of
   that formula outside its own validation charter.
4. **Every other candidate component** (isolated single edges, or any
   shape other than a candidate triad): retained unmodified, no DPI
   applied — this is the explicit scope boundary stated above, not an
   oversight.
5. **Final output**: DPI-retained edges from candidate triads, plus
   unmodified other-shaped candidate edges.

**Predeclared expectation, stated before running anything:** most false
positives from screening will be isolated single edges (two variables
with no shared candidate neighbor), since Stage 2's ~1% per-edge FDR
makes two false edges sharing a variable rare at `p=15`. If so, DPI
mostly cannot act on them (step 4 passes them through), and the final
false-edge rate should closely track screening's own per-edge FPR rather
than improving on it. This charter tests whether that expectation holds,
not just assumes it.

## Data-generating process

Identical to `docs/stage2_charter.md`: `p=15` (chain `X1->X2->X3`, fork
`X4<-X5->X6`, triangle `X7,X8,X9` at the `moderate` fixture, strength
`.5`; six independent noise columns `X10`-`X15`), `N = [750, 1500]`
(Stage 1 and Stage 2's shared validated regime), master seed `20260829`,
2000 replicates (development 0-999, validation 1000-1999).

**Ground truth for this charter** (distinct from Stage 2's — this is
about the *final* pipeline output, not just screening):

- **True direct edges (7)**: chain `(1,2)`, `(2,3)`; fork `(4,5)`,
  `(5,6)`; triangle `(7,8)`, `(7,9)`, `(8,9)`.
- **Indirect edges DPI should prune (2)**: chain `(1,3)`, fork `(4,6)`.
- **Null pairs (96)**: everything else, as in Stage 2.

## Selection and gate

No selection step — both `alpha` values (screening and DPI) are already
frozen from D-012/D-013; this charter only evaluates the resulting
pipeline. Per `N`, on validation replicates (1000-1999):

1. **Indirect-edge pruning TPR** (chain `(1,3)` and fork `(4,6)` correctly
   absent from the final output) `>= .80`.
2. **True-edge retention** (all 7 true direct edges present in the final
   output) — FPR (fraction wrongly pruned) `<= .10`.
3. **Final false-edge rate** (fraction of the 96 null pairs present in
   the final output) does not exceed screening-alone's own validated
   per-edge FPR at that `N` (D-013: `~.001` at `alpha=.001`) by more than
   a small tolerance (`.01` absolute) — a no-regression check, not a new
   threshold pulled from nowhere.

**PROCEED** for a given `N` only if all three hold with no recorded
error. **REASSESS** otherwise, reporting which criterion failed.
Descriptive-only: the fraction of candidate components that are actual
triads vs. other shapes, to check the predeclared expectation above.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (final retained/pruned status for
every one of the 9 true-motif pairs, plus which of the 96 null pairs
survived to the final output), aggregate metrics, the per-N decision
table, report, and figures.

## Consequences

If PROCEED at both `N`: this validates the composed pipeline only for
disjoint, non-overlapping 3-node motifs at `p=15`, `N in [750, 1500]`. It
does not validate general-shaped candidate graphs (overlapping motifs,
hub variables, components larger than 3 nodes) — that remains a distinct,
open, harder question requiring its own DGP and charter before Stage 3
(bootstrap) or a full continuous MVP can be responsibly attempted.

If REASSESS: the specific failing criterion determines the next step —
a false-edge-rate regression would implicate the composition itself
(DPI somehow making things worse, not better, contrary to the
predeclared expectation); a recall or TPR failure would suggest an
interaction between screening's candidate set and DPI's conditioning
that neither charter alone could have revealed.
