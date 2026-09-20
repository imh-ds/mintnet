# Stage 5a Charter: Broad Comparator Benchmarking — EBICglasso on Shared Gaussian Ground (R6)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

`outline/information_network_technical_build_plan_v3_2026-08-30.md`
Section 22 (its own "Stage 7 — Broad benchmarking") names R6's question
directly: **does the method occupy a meaningful niche compared with
incumbents?** Section 22.2 is explicit that this is not a supremacy
requirement — "the method does not need to dominate all comparators."
Stage 4's own arc (`docs/stage4o_recommendation.md`, D-044) closed out
R6a (the greedy engine's own internal validation); R6 itself has not
been started. This charter opens it.

**A scoping correction, made transparently before this charter is
frozen, not after:** the initial framing discussed for this charter
proposed hunting for a DGP that violates a named Gaussian-graphical-
model assumption (nonlinearity, non-Gaussian marginals, mixed types) to
show MINT succeeding where EBICglasso's assumptions break. On reviewing
`outline/information_network_technical_build_plan_v3_2026-08-30.md`'s
own "Validated scope" section (Version 2 Revision Notice), that framing
overreaches what has actually been validated so far: **every pruning
mechanism validated through Stage 4 — the conservative engine's Fisher-z
partial-correlation test (`docs/stage1b_charter.md` onward, D-008) and
the sequential engine's identical per-edge test (`docs/stage4a_charter.md`
onward)** — is itself a closed-form **Gaussian** conditional-independence
test, explicitly *not* a general nonparametric conditional-MI estimator
(see that section's own "Explicitly not validated" list: "nonlinear or
non-Gaussian data ... a nonparametric conditional-mutual-information
estimator"). Genuinely nonlinear known-graph DGPs are reserved for
Stage 8 (outline Section 23), which has not been chartered. Running an
assumption-violation comparison now would test MINT on a regime it was
never validated to handle correctly — a "win" there would carry no
ground-truth confidence in MINT's own output, and a "loss" would be an
expected, uninformative result. **That comparison is deferred to a
later charter, contingent on Stage 8.**

**This charter instead runs the honest, currently-available comparison:
same Gaussian ground for both methods.** MINT's conservative engine and
EBICglasso both ultimately target the same object — a Gaussian
graphical model's nonzero partial correlations — via different
selection procedures (per-edge sequential/conjunctive hypothesis testing
vs. joint L1-penalized precision-matrix estimation with an EBIC-selected
penalty). A same-assumptions comparison is still informative: it asks
whether MINT's specific selection procedure has a real efficiency,
accuracy, or compute-cost difference from an established incumbent on
identical data, using DGP shapes (chain, fork, hub, triangle,
shared-node overlap) already deeply characterized across Stages 1-4.
This is explicitly the *first* R6 charter, not the only one — see
"Explicit non-goals" below for what is deliberately left to later work.

## Scope: which engine

**Conservative engine only** (`mintnet.pipeline.compose_screen_then_prune`),
not the sequential/greedy engine. The conservative engine is the
project's one fully general, uncaveated recommendation across all five
tested shapes; the greedy engine still carries per-shape disclosed
caveats (`docs/stage4o_recommendation.md`) that have not yet been
resolved into one clean, general-purpose recommendation. Comparing an
incumbent against a still-caveated engine would confound "does MINT have
a niche" with "which MINT engine, under which caveat" — two separate
questions. A follow-up charter can add the sequential engine once useful.

## Comparator: EBICglasso, implemented natively

This repository has no R/rpy2 dependency and none is being added.
`EBICglasso` (Foygel & Drton 2010's extended-BIC selection, as packaged
for psychometric use by `qgraph::EBICglasso`) is algorithmically:
graphical lasso fit across a regularization path, with the path's
penalty selected by minimizing

\[
\text{EBIC}(\lambda) = -2\,\ell(\lambda) + E(\lambda)\,\ln N + 4\,\gamma\,E(\lambda)\,\ln p
\]

where \(\ell\) is the fitted Gaussian log-likelihood, \(E(\lambda)\) is
the number of retained edges, and \(\gamma\) is the EBIC hyperparameter
(`qgraph`'s own package default: `gamma = 0.5`). This is implemented
directly in Python: a new module `src/mintnet/comparators/ebicglasso.py`
using `sklearn.covariance.graphical_lasso` (the core glasso solver only)
across a fixed, log-spaced `lambda` grid (`nlambda = 100`, matching
`qgraph`'s own default grid density, spanning from a data-derived
`lambda_max` — the smallest penalty producing a fully dense fit — down to
`lambda_max * 0.01`, `qgraph`'s own `lambda.min.ratio` default), scoring
each fitted precision matrix's EBIC, and selecting the minimizer. This
is a from-specification re-implementation of the selection procedure,
not a call into the R package itself — flagged explicitly as an
implementation choice, not an assumption that it reproduces `qgraph`'s
numerical output bit-for-bit. New dependency: `scikit-learn` (added to
`pyproject.toml`, `test`/runtime extras as appropriate) — its own glasso
solver only, no other part of the library used here.

## Fair-comparison rules (outline Section 22.1, resolved before results)

- **Edge definition.** MINT: an edge is present iff retained after
  screening + DPI (the project's own convention throughout Stages 1-4).
  EBICglasso: an edge is present iff its estimated partial correlation is
  nonzero at the EBIC-selected `lambda` — no secondary threshold applied
  on top of glasso's own sparsity.
- **Tuning budget — the one asymmetry that must be disclosed, not
  hidden.** MINT's screening/DPI `alpha(N)` was originally *fit* using
  truth-informed simulation (D-012's general formula; the overlap-
  specific formula, Stage 4g/4i/4j). That fitting is not repeated here —
  this charter only *uses* the already-frozen formulas exactly as
  Stage 4o's own recommendation specifies per shape (D-012's general
  formula for chain/fork/hub/triangle; the overlap-specific formula
  within its own validated `[400, 735]` range, the general formula
  outside it). EBICglasso's `gamma = 0.5` is likewise used as a fixed,
  literature-standard default, not searched. **Neither method receives
  fresh truth-informed tuning inside this charter** — both enter using
  settings fixed before this charter's own data is drawn. The asymmetry
  that MINT's formula was *originally derived from* truth-informed
  simulation (in earlier, separate charters) while `gamma = 0.5` is a
  literature convention is real and is stated here rather than elided.
- **Data access.** Paired design (this project's own established
  precedent — Stage 4c/4m/4n/4p): both methods are fit on the identical
  drawn sample, same seed, every replicate. Neither method sees data the
  other does not.
- **Scoring.** Adjacency precision, recall, F1, and structural Hamming
  distance (outline Section 13's own metric set) against the identical
  known ground-truth graph, computed identically for both methods.

## Data-generating processes

Reused unmodified — no new DGP construction in this charter:

- **Chain, fork, hub(2-children)**, composed `p=15`, noisy
  (`mintnet.experiments.stage4l`'s own DGP — `TRUE_DIRECT_EDGES`,
  `NOISE_COUNT=6`, `P=15` — already the composed/noisy fixture Stage 4l
  and Stage 4p reused).
- **Shared-node overlap**, composed `p=15`, noisy
  (`mintnet.experiments.stage2d`'s own network —
  `sample_overlapping_triangles`, `OVERLAP_INDIRECT`, `TRUE_DIRECT_EDGES`,
  `NOISE_COUNT`, `P` — the same network Stage 4p/4q benchmarked).
- **Classic asymmetric triangle**, three-node, no noise
  (`docs/stage1_charter.md`'s own balanced/moderate/strong fixtures) —
  retained as the smallest, cleanest case, direct continuity with the
  very first Stage 1 result (D-008).

All three are strictly Gaussian, linear, continuous precision-matrix
DGPs — EBICglasso's own native assumption class, and MINT's own fully
validated territory (conservative engine).

## Sample sizes, replicates, seeds

`N = [400, 500, 600, 750, 1000, 1500, 1750]` — Stage 4p's own canonical
public grid, extended with `1750` (D-046's corrected overlap floor) for
direct comparability against every already-published table. `2,000`
replicates per `(DGP, N)` cell, development `0`-`999` / validation
`1000`-`1999`, mirroring Stage 4p's own split even though this charter
has no fresh tuning to develop — the split is retained so validation-only
reporting stays consistent with prior practice. Master seed and
per-condition seed derivation reused verbatim from
`mintnet.experiments.stage4p._condition_seed`, extended with a new,
disjoint stream tag for this charter (never reuses a seed already drawn
for a different purpose).

## Metrics and reporting

Per `(DGP shape, N)`, report **both methods in the same row**, full
grid, no cell omitted regardless of outcome (the discipline established
`docs/stage4j_charter.md` onward):

- MINT: precision, recall, F1, SHD, and its own PROCEED/REASSESS status
  (reusing existing gate logic).
- EBICglasso: precision, recall, F1, SHD. **No PROCEED/REASSESS concept
  applies** — `EBICglasso` always returns *some* graph regardless of
  whether the data actually support it at that `N`. This qualitative
  difference (MINT can and does disclose "not enough evidence here";
  EBICglasso cannot) is itself a reportable finding, not something to
  force into a shared status column.
- Runtime (wall-clock, per replicate, both methods) — outline Section 26's
  own required diagnostic, and the concrete basis for any "moderate
  compute" niche claim (Section 22.2).

## Explicit non-goals for this charter

- **No nonlinear, non-Gaussian, or mixed-type DGP.** Deferred to a later
  charter, contingent on Stage 8 (outline Section 23) first validating
  that MINT's own mechanism produces correct output on such data at all.
- **No sequential/greedy engine.** See "Scope" above.
- **No claim of superiority.** Per outline Section 22.2, a genuine niche
  does not require dominating every cell — a mixed picture (comparable
  accuracy, different compute cost, different failure-disclosure
  behavior, or a shape-specific advantage in either direction) is a
  complete and useful answer.
- **No retuning of either method's hyperparameter after seeing results.**
  `alpha(N)`'s formulas and `gamma = 0.5` are both fixed before this
  charter's data is drawn (see "Fair-comparison rules").

## Decision structure

This is not a PROCEED/REASSESS/STOP gate in the Stage 1-4 sense — there
is no pruning-mechanism correctness question left open here; both
methods are already validated on their own terms. Instead, per outline
Section 32's R6 question, this charter requires a **predeclared,
descriptive verdict**, fixed now rather than drafted after seeing
results (mirroring Stage 4o's own rubric-before-verdict discipline):
for each of the three DGP shapes, state which of

1. MINT reaches acceptable recovery (F1, SHD within the shape's own
   already-established acceptable range) at a materially lower `N` than
   EBICglasso,
2. EBICglasso reaches it at a materially lower `N` than MINT,
3. no material `N` difference, accuracy comparable throughout,

holds, plus the runtime comparison and the failure-disclosure
qualitative note, stated plainly and separately from the `N`-efficiency
finding — not merged into one composite score.

## Required evidence

Resolved configuration for both methods, this charter's SHA-256, commit
and runtime metadata, raw per-replicate metrics for both methods (not
just aggregates), the full per-shape-per-`N` comparison table (every
cell, regardless of outcome), and a report stating the three-way verdict
above per shape.

## Consequences

Answers R6's own top-level question descriptively, for the Gaussian,
shared-assumption case. Does not retroactively alter any Stage 1-4
PROCEED/REASSESS verdict — those concern MINT's own internal validity on
its own terms, unaffected by how an external comparator performs. If a
genuinely differentiating (assumption-violation) niche is later wanted,
the correct next step is chartering Stage 8's nonlinear known-graph
DGPs first, then a second comparator charter reusing this charter's own
`EBICglasso` implementation and fair-comparison rules against that new
data — not amending this charter after the fact.
