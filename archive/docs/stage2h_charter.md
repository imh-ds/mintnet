# Stage 2h Charter: Overlap-Composed Pipeline at p=30 (R3j)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-024 and D-025 validated the composed pipeline at `p=30` for two
candidate shapes (disjoint triads, hub), both predicted cleanly from
prior findings and both PROCEEDing at both `N` with no correction
needed. Both charters' own consequences explicitly deferred the third
tested shape: shared-node overlap — "the one shape where D-018's
`N=750` weak-signal caveat makes a safe-transfer assumption least
justified." This charter tests it, and **this charter is not expected
to repeat the clean-PROCEED pattern of Stage 2f/2g.**

**Predeclared expectation, computed from the same Fisher-z power
calculation D-018 itself used, before running anything — and this time
predicting trouble, not confirmation:** D-018 found the overlap DGP's
weak (`~.135`) cross-branch correlation is detected with per-edge power
`~66%` at `N=750` and `~98%` at `N=1500`, at Stage 2's `p=15` threshold
(`alpha=.001`). D-023's `p=30` threshold is `alpha=.0001` — a full order
of magnitude stricter, adopted because `p=30`'s multiple-testing burden
demanded it (D-023), not because any DGP's own signal strength changed.
**A stricter threshold reduces detection power for a fixed weak signal
by construction** — the opposite of what happened for chain/fork/hub's
*strong* (`.5`-correlation) signals, whose power was already
`~1.0` at both thresholds and so unaffected (D-024, D-025). Recomputing
the same power calculation at `alpha=.0001`:

| `N` | per-edge power @ `alpha=.001` (D-018) | per-edge power @ `alpha=.0001` | naive clean-clique rate (power^4) @ `.001` | naive clean-clique rate @ `.0001` |
|---|---|---|---|---|
| `750` | `.663` | `.429` | `.194` | `.034` |
| `1500` | `.975` | `.914` | `.905` | `.697` |

(The `.001`-column naive figures closely match D-018's own pre-charter
`~26%`/`~89%` estimates, confirming this calculation method — cited here
only to validate applying it at the new `alpha`, not as new evidence
about `p=15`.) **D-018's own charter found actual clean-clique rates
(`.287`/`.921`) ran meaningfully higher than this naive
independent-power estimate (`.194`/`.905`)** — the four cross-branch
tests are positively correlated through the shared node, so joint
success is more common than independence predicts, by roughly `1.5x`
at the harder `N=750` cell.

**This charter therefore predicts**: `N=750` will very likely REASSESS,
and decisively rather than narrowly — even applying D-018's own
`~1.5x` correction factor to `.034` gives `~.05`, an order of magnitude
below the `.80` gate, not a near-miss like D-018's own `.569`. **`N=1500`
is genuinely uncertain** — the naive estimate (`.697`) sits well below
`.80`, but D-018's correlation-driven correction was large enough at the
harder cell that a similar boost here could plausibly clear the gate;
this charter does not predict which way `N=1500` resolves, and that
uncertainty is the primary reason to run it rather than infer it.
**Chain and fork, whose signal strength is unaffected by the stricter
alpha, are predicted to behave as they did in D-024/D-025** (TPR
`.83`-`.89`).

## Pipeline (frozen mechanism)

Identical to Stage 2d, using D-023's `p=30` screening threshold:

1. **Screen** every `C(30, 2) = 435` pairs at `alpha = .0001` (D-023's
   `p=30` rule, applied here exactly as automatically selected —
   **deliberately not hand-tuned for this DGP's weaker signal**, since
   the point of this charter is to test what happens when a `p`-driven
   threshold, chosen without regard for any specific motif's signal
   strength, meets a DGP whose signal happens to be weak. A real
   dataset's screening threshold cannot be retuned per candidate shape
   after the fact either).
2. **Group** candidate edges into connected components; extend
   `VALIDATED_CLIQUE_SIZES` to include size 5 (D-017/D-018).
3. **Apply DPI**, `alpha = f(N)` (D-012), within any validated clique
   shape.

No new code.

## Data-generating process

Identical to Stage 2d, extended to `p=30`: chain (0-2), measured fork
(3-5), shared-node overlap (6-10, node 8 shared), and **19** independent
noise columns (11-29) — up from Stage 2d's 4. Strength `.5`,
`N = [750, 1500]`, master seed `20260829`, 2000 replicates (development
0-999, validation 1000-1999).

**Ground truth**, identical structure to Stage 2d: **16 true candidate
pairs** (chain's 3 + fork's 3 + overlap's `C(5,2)=10`), **10 true direct
edges**, **6 indirect edges** (chain 1, fork 1, overlap's 4 cross-branch
pairs), **419 null pairs** (`C(30,2) - 16`).

## Selection and gate

No selection step. Per `N`, on validation replicates (1000-1999),
computed **separately per motif** (the same anti-pooling discipline
D-018 used, per the D-004 precedent):

1. Chain indirect-edge TPR `>= .80`.
2. Fork indirect-edge TPR `>= .80`.
3. Overlap indirect-edge TPR `>= .80` (the one predicted, at `N=750`, to
   fail decisively).
4. True-edge retention FPR `<= .10`, pooled across all three motifs.
5. Final false-edge rate does not exceed screening-alone's own rate by
   more than `.01` (no-regression, unchanged tolerance).

**PROCEED** for a given `N` only if all five hold with no recorded
error. Descriptive: the overlap clean-clique formation rate, to compare
against this charter's own predeclared table above.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (per-motif indirect TPR, pooled
true-edge FPR, screening/final false-edge rates, overlap clean-clique
indicator), aggregate metrics, the per-N decision table, report, and
figures — identical evidence set to Stage 2d, at `p=30`.

## Consequences

If the predicted split occurs (decisive REASSESS at `N=750`, either
outcome at `N=1500`): this would establish that **a `p`-driven screening
threshold, selected without regard for individual motif signal
strength, can turn an already-known-marginal weak-signal shape into a
much more decisively broken one at larger `p`** — a genuinely new
finding, not a restatement of D-018's `p=15` result, and a concrete
argument for why a production system cannot safely apply one global
`p`-driven `alpha` across a dataset with mixed signal strengths without
this exact kind of per-shape check. It would **not** by itself suggest
the `p=30` results for chain/fork/hub (D-024, D-025) are somehow in
doubt — their signal strength was never close to this threshold's
detection boundary at either `alpha`.

If `N=1500` unexpectedly PROCEEDs alongside `N=750`'s REASSESS: this
would replicate D-018's own split-outcome pattern one `p` level up, and
would be worth comparing quantitatively against this charter's own
naive-vs-corrected table to check whether the correlation-correction
factor scales predictably with `p` and `alpha`, or whether it is
specific to the `p=15` cell it was first observed in.

If both `N` unexpectedly PROCEED (contradicting this charter's central
prediction): investigate why the power calculation or D-018's
correction factor failed to transfer, rather than assuming the
mechanism is simply more robust than modeled — an unpredicted PROCEED
here would be more surprising, and more worth understanding, than an
unpredicted REASSESS would have been.
