# Stage 8g Charter: Structural Audit of `chain_fork_hub`/`overlap`'s Own Screened Conditioning Subsets (main)

Status: **FROZEN before results**
Date: 2026-09-08

## Background and objective

D-071 (Stage 8f) confirmed, in a controlled, known-truth fixture, that
conditioning on a genuine collider induces spurious dependence strong
enough to explain D-069's own composed-tier reversal pattern, and that
this is specifically attributable to the collider's presence, not
conditioning-set size alone. Both charters explicitly disclosed this
does **not** establish that a collider structure is what actually
occurs inside `chain_fork_hub`'s or `overlap`'s own screened
conditioning subsets for any real false edge -- that question is
chartered here.

**A structural fact, established by direct inspection of this
project's own already-frozen generative code, not requiring new
evidence, and stated up front because it reframes this charter's own
question:** neither `chain_fork_hub` (`mintnet.experiments.stage4l`)
nor `overlap` (`mintnet.experiments.stage2d`) contains a genuine
population-level collider anywhere in its own known structure.

- **`chain_fork_hub`**: chain (`0->1->2`, node `1` a mediator), fork
  (`4->3`, `4->5`, node `4` a common cause), hub (`6->7`, `6->8`, node
  `6` a common cause) -- three motifs sampled **independently** in
  `stage4l._sample_network` (separate `rng` calls, `np.column_stack`ed,
  no cross-motif term anywhere), plus 6 independent noise columns.
  Every named "indirect" pair's own connecting node (`1`, `4`, `6`) is
  a **mediator or common cause** -- a legitimate separator whose
  blocking role Stage 1-4's own already-validated evidence confirms
  works correctly. A mediator or common cause is definitionally the
  opposite of a collider (conditioning on either *correctly* induces
  independence; conditioning on a collider *incorrectly* induces
  dependence). No v-structure exists anywhere in this DGP.
- **`overlap`**: chain, fork (as above, independently sampled), and
  the shared-node-overlap motif (`sample_overlapping_triangles`, an
  **undirected** Gaussian graphical model specified by a precision
  matrix, node `8` shared between two triangles) -- again fully
  independent of the other motifs. Node `8` is a legitimate graph
  separator (its own conditional-independence role is exactly the
  undirected analogue of a mediator/common-cause) for the
  `OVERLAP_INDIRECT` pairs, not a collider. "Collider" (a v-structure)
  is a directed-graph concept; the overlap motif has no directed
  structure at all, and no combination of its own known edges produces
  the pattern of two arrows into a shared descendant.

**This means the collider-conditioning mechanism D-071 confirmed
cannot be operating on a fixed population-level collider anywhere in
either network** -- there is none to condition on. If the composed-
tier reversal is nonetheless explained by the same underlying
mechanism, it must be a **finite-sample, screening-induced pseudo-
collider effect**: a conditioning variable that happens, by chance, to
be correlated with both members of a tested pair *in that specific
simulated replicate* (despite true population independence or a
legitimate separating role), behaving like a collider for that one
dataset even though no such structure exists in the DGP. This charter
tests that reframed hypothesis (H3) directly, rather than auditing for
something (a true population collider) already established not to
exist.

## Mechanism

**Step 1 -- instrumentation (purely additive, no new randomness).**
`growing_subset_dpi`'s own OR-rule search already determines, internally,
exactly which conditioning subset triggered a prune, or which subset
produced the maximum p-value among those tested for a retained edge
(this is `decisive_p_value`'s own source, per Stage 8a). Add one new
field to `GrowingSubsetResult`: `decisive_conditioning_subset: dict[
tuple[int, int], tuple[int, ...]]`, recording that subset's own column
indices (empty tuple for an isolated edge, matching `decisive_p_value`'s
own `NaN` convention). Purely a persistence addition to already-computed
internal state -- identical in kind to Stage 8d's own
`conditioning_size_used`/`cap_reached` enrichment, no change to any
decision logic.

**Step 2 -- enrich, not replace, Stage 8c's own evidence, a third time.**
Re-run Stage 8c's exact frozen design (identical seeds, identical
`configs/stage8c_composed_calibration.yaml`, using `stage5a._condition_
seed`/`_DGP_REGISTRY` exactly as `stage8c_composed_calibration.py`
already does) capturing `decisive_conditioning_subset` per edge, on top
of the `conditioning_size_used`/`cap_reached` fields Stage 8d already
added. A deterministic reproduction, zero new randomness.

**Step 3 -- compute each decisive subset's own "chance correlation" with
the tested pair.** For every false edge (`is_true_edge=False`) with
`conditioning_size_used >= 2` (D-069's own reversal-trigger condition),
regenerate that exact replicate's own simulated data (deterministic
from the same seed, per Step 2 -- no new raw data is persisted, only
recomputed on demand) and compute:

```
chance_correlation = max over c in decisive_conditioning_subset of
    max(|Pearson corr(X_c, X_i)|, |Pearson corr(X_c, X_j)|)
```

the largest marginal sample correlation between any decisive-subset
member and either endpoint of the tested pair, **in that specific
replicate** -- the quantity a true collider would inflate, and which a
merely-independent decoy (Stage 8f's own `step2_control`) would not,
except by ordinary sampling noise.

**Step 4 -- H3 (finite-sample pseudo-collider hypothesis).** Within
`conditioning_size_used >= 2`, per `(dgp, n)`: split false edges into
"high chance-correlation" (above that cell's own median
`chance_correlation`) and "low chance-correlation" (at or below it) --
a data-driven split, not a hand-tuned threshold. Compare each half's
own **wrong-retention rate** (fraction retained when ground truth says
prune) with Wilson 95% CIs, requiring `min_count=30` per half (D-069's
own precedent). **Confirmed** if "high" shows a materially,
consistently higher wrong-retention rate (non-overlapping CI, correct
direction) than "low" at every cell with enough data to compare.

**Step 5 -- validity cross-check (not a new hypothesis, a sanity check
on Steps 1-4 themselves).** For the same `conditioning_size_used >= 2`
false edges, confirm that no decisive subset for a WITHIN-motif indirect
pair (`CHAIN_INDIRECT`/`FORK_INDIRECT`/`HUB_INDIRECT` for
`chain_fork_hub`; the same plus `OVERLAP_INDIRECT` for `overlap`)
contains that pair's own known legitimate separator (`1`/`4`/`6` for
`chain_fork_hub`; `1`/`4`/`8` for `overlap`) while still being wrongly
retained. If the legitimate separator **was** present in a
wrongly-retained decisive subset, that is a materially different and
more serious finding than a pseudo-collider effect -- a genuine defect
in the significance test or the OR-rule's own subset-selection logic --
and would need to be reported and flagged as its own open question, not
folded into H3's own verdict.

## Data-generating processes

Identical to Stage 8c's own (`chain_fork_hub`, `overlap`, `p=15`,
`strength=0.5`, `screening_alpha=0.001`, `N in
{400,500,600,750,1000,1500,1750}`, `master_seed=80200`, `R=2000`) for
all steps -- this charter's own job is to explain that evidence more
deeply, not generate a different one. No new DGP, no new sweep
dimension.

## Compute-cost disclosure

**Step 2**: identical grid and per-replicate cost Stage 8c/8d already
measured (`~11-14ms`); persisting one additional already-computed tuple
per edge adds no meaningful overhead.

**Step 3 is not assumed free.** Regenerating a replicate's own raw data
on demand (rather than reusing a persisted array) means re-sampling the
DGP once per false edge needing this diagnostic, not once per
replicate -- if a single replicate has multiple `conditioning_size_used
>= 2` false edges (plausible, since a component's every candidate edge
is scored independently), this could re-sample the same replicate's
data more than once. Per this project's own standing discipline:
**measure real wall-clock cost of Step 3's own regeneration-plus-
correlation computation on at least one shard before committing to
running it inline vs. caching regenerated data per replicate** -- a
disclosed implementation choice, not assumed cheap from the DGP's own
already-known sampling cost alone.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** --
unchanged, hard requirement, per this project's established practice.

## Selection and gate

Diagnostic charter -- no PROCEED/REASSESS gate (mirrors Stage 8d/8f's
own precedent). Two predeclared verdicts:

1. **H3 (finite-sample pseudo-collider effect)**: Confirmed / Not
   confirmed / Inconclusive, per the Step 4 criterion above.
2. **Validity cross-check (Step 5)**: Clean (no legitimate-separator
   contamination found) / Flagged (at least one wrongly-retained
   decisive subset contained the pair's own known legitimate
   separator -- reported as a separate, more serious open question,
   not resolved here).

## Explicit non-goals

- **No claim about a true population-level collider existing in either
  network.** Already established false by direct code inspection (see
  Background) -- this charter does not re-litigate that.
- **No re-diagnosis of D-069's own H1/H2 findings** (cap-reached /
  conditioning-size-graded) or D-071's own controlled-fixture result --
  both stand as recorded; this charter asks whether D-071's own
  mechanism, reframed as a finite-sample effect, plausibly operates
  inside the real evidence.
- **No production deployment or fix**, even if H3 is confirmed. D-070's
  own recalibration mapping remains the deployed fix regardless of this
  charter's own result.
- **No claim beyond marginal Pearson `chance_correlation` as the
  operationalization of "sample-level collider-likeness."** A stronger
  or differently-defined statistic (e.g. involving partial correlations
  among decisive-subset members themselves) is a possible follow-up,
  not attempted here.
- **No structural audit of any mechanism other than
  `growing_subset_dpi`** (the partial-correlation mechanism) --
  CMIknn/structured-density are out of scope, unchanged from every
  prior Stage 8 charter's own scoping.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the Step 3 timing
measurement and resulting implementation decision, the enriched raw
evidence (`decisive_conditioning_subset` added to Stage 8d's own
already-enriched fields), the per-`(dgp, n)` chance-correlation
high/low wrong-retention-rate table with Wilson CIs, the Step 5
validity cross-check's own findings, both verdicts above, and a report.

## Consequences

**If H3 confirmed and Step 5 is clean**: the composed-tier reversal is
explained, specifically, as a finite-sample screening-selection
artifact -- a conditioning variable that happens to look like a
collider *for that dataset*, not because any such structure exists in
the DGP. This completes the mechanistic story D-069 opened and D-071
narrowed: real, collider-shaped bias, arising from sampling variability
interacting with `growing_subset_dpi`'s own search rather than from any
flaw in the DGPs or the significance test's own math. Motivates (as a
separate, not-yet-chartered future step) investigating whether a
conditioning-order or subset-selection heuristic could reduce exposure
to high-chance-correlation subsets -- not designed or evaluated here.

**If H3 is not confirmed**: the reversal's cause remains open even
after D-071's own controlled confirmation that the underlying mechanism
is real in isolation -- would mean whatever drives the real network's
own reversal is something this charter's own `chance_correlation`
operationalization fails to capture, warranting a differently-designed
follow-up rather than a retry of the same statistic.

**If Step 5 is flagged**: report it prominently regardless of H3's own
outcome -- a legitimate separator being present in a subset that still
retained a false edge would point to a defect in `growing_subset_dpi`'s
own OR-rule or the significance test itself, a materially more urgent
finding than a pseudo-collider explanation.
