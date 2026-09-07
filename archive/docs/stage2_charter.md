# Stage 2 Charter: Candidate-Edge Screening in Isolation (R3)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

Stage 1 validated conditional-independence pruning (`docs/decision_log.md`
D-008 through D-012) as a mechanism for distinguishing direct from
indirect edges — but only ever on isolated, hand-picked three-variable
motifs where every pair was already known to matter. A real dataset has
many variables and many candidate pairs, most of which are typically
unrelated. Before any pair reaches the validated Stage 1 pruning
mechanism, something has to first decide which pairs are worth
considering as candidate edges at all. That screening step is Stage 2, per
`outline/information_network_technical_build_plan.md` Section 16 (see
also the v2 annotated copy's revision notes on this section).

Per the outline's own Section 2.1 ("validate mechanisms independently
before composing them") and Section 6's precedent (Stage 1 tested pruning
*alone*, with no screening, bootstrap, or other machinery), this charter
tests **screening in isolation**: does a per-pair correlation
significance test correctly separate genuinely-associated pairs from
genuinely-independent pairs in a larger network, at the sample sizes
Stage 1 already validated? It does not combine screening with DPI
pruning, does not test bootstrap reproducibility, and does not authorize
either.

**Revision from the outline's original Stage 2 sketch:** the outline
suggested `N in {200, 350, 500, 1000}` for this stage, written before
Stage 1 existed. Stage 1 has since established that `N < 700` is a
decisive, structural failure for the validated pruning mechanism
(D-009, D-010) — screening pairs at a sample size the next stage cannot
use them at would not be a useful test. This charter uses Stage 1's own
validated regime instead: `N = [750, 1500]`.

## Mechanism

A per-pair Fisher-z significance test on **raw (unconditional) Pearson
correlation** — the same closed-form test family Stage 1 validated for
partial correlation (`docs/stage1b_charter.md`), applied without
conditioning on a third variable. For a pair `(i, j)`:

```
z_ij = atanh(r_ij) * sqrt(N - 3)
p_ij = 2 * (1 - Phi(|z_ij|))
```

A pair is a **candidate edge** if `p_ij <= threshold`, under two
predeclared threshold rules:

1. **Uncorrected**: a fixed `alpha` applied independently to every pair.
2. **BH-corrected**: Benjamini-Hochberg FDR control at nominal level `q`,
   applied across all `C(p, 2)` pairs in a single network.

Candidate thresholds: uncorrected `alpha in [.001, .005, .01, .05, .10]`;
BH `q in [.05, .10]` — seven candidate rules total. The uncorrected grid
is deliberately extended down to `.001`: with 96 null pairs and only 9
true pairs per replicate (roughly 10.7:1), back-of-envelope expected-value
arithmetic before running anything (`FP = 96 * alpha`, `TP ~= 9 *
power`) suggests `alpha = .01` sits right at the `FDR <= .10` boundary and
`alpha = .05`/`.10` will not control FDR at all — the grid needs to reach
low enough to give the uncorrected approach a genuine, fair chance,
otherwise "is BH necessary" is not an honestly open question. Per the
outline's Section 16.5 ("choose the simplest screening rule ... BH is not
mandatory"), if multiple candidates meet the gate, the simplest
(uncorrected, smallest `alpha` among passing options) is preferred over
any BH-corrected rule.

This is new code, not a reuse of Stage 1's conditional test — it belongs
in a new `mintnet.screening` module, matching
`outline/information_network_technical_build_plan.md` Section 3's
proposed repository structure.

## Data-generating process

`p = 15` variables per network (a single, modest network size for this
first Stage 2 charter, kept small per the outline's Section 2.2
falsification-first principle; `p = 30` is a natural follow-up charter if
this one passes, not tested here).

**Ground truth**, embedded in every replicate:

- One chain (`X1 -> X2 -> X3`, strength `.5`), one measured fork
  (`X4 <- X5 -> X6`, strength `.5`), one triangle (`X7, X8, X9`, the
  `moderate` fixture) — the same validated DGPs from Stage 1, using 9
  variables.
- Six independent standard-Gaussian noise variables (`X10`-`X15`),
  uncorrelated with everything.

**Ground-truth candidate status is about nonzero vs. zero pairwise
correlation, not direct vs. indirect edges** — that finer distinction is
Stage 1's validated job, applied downstream, and is explicitly out of
scope here (conflating the two would test both mechanisms' evidence
together, against the outline's own Section 2.1 principle). A chain's
indirect endpoints (`X1`-`X3`) have genuine nonzero population
correlation and count as a true candidate here, even though Stage 1's
pruning would later remove that edge as indirect.

This gives, per replicate: **9 true candidate pairs** (all pairs within
each of the three motifs) and **96 null pairs** (`C(15,2) - 9`: all
motif-to-motif, motif-to-noise, and noise-to-noise pairs).

Master seed `20260829` (continuing Stage 1's seed), 2000 replicates per
`N` (development 0-999, validation 1000-1999).

## Selection and gate

Per `N`, independently (no pooling across `N`, per the per-N principle
established in `docs/stage1d_charter.md` onward): a candidate rule is
*eligible* if, on development replicates, it achieves:

1. Recall on the 9 true candidate pairs `>= .80` (pooled across the three
   motif types).
2. Empirical FDR (fraction of *all* flagged pairs, across all 96+9
   possible pairs, that are actually null) `<= .10`.

Among eligible rules, select the simplest per the tiebreak stated above.
The selected rule must then pass validation (replicates 1000-1999) at the
same two thresholds, individually, with no recorded error, to PROCEED for
that `N`.

**Output is a per-N table** (mirroring Stage 1h/1i/1j), not one global
status — `N = 750` and `N = 1500` are evaluated and reported
independently.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (which of the 105 pairs were
flagged, per rule and per replicate), aggregate metrics (recall, FDR,
per-edge FPR, family-wise any-false-edge rate, graph density), the per-N
decision table, report, and figures (screening ROC-style operating curve,
performance vs. `N`).

## Consequences

If REASSESS at a given `N`: document which criterion failed and by how
much. Do not proceed to composing screening with DPI pruning (the
outline's Stage 3/4) until a passing screening rule exists at that `N`.

If PROCEED at both `N`: this validates only that per-pair correlation
screening (with or without BH correction) works at `p=15`, `N in [750,
1500]`. It does not by itself authorize combining screening with Stage
1's DPI pruning into one pipeline — that composition is its own
mechanism-interaction question and needs its own charter, per the
outline's Section 2.1. It also does not authorize `p=30` or other network
sizes; those remain untested.
