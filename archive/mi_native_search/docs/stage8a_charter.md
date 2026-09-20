# Stage 8a Charter: Tier-0 Confidence-Score Calibration Check (main)

Status: **FROZEN before results**
Date: 2026-09-07

## Background and objective

Every DPI decision this project makes already produces a p-value that
gets thresholded against `alpha` and then discarded. A cheap, always-on
per-edge confidence score — how far that p-value sat from the decision
boundary, not just which side it landed on — has been proposed as a
"Tier 0" diagnostic: free, requires no new evidence collection, and
gives a researcher something continuous to weigh alongside their own
theoretical judgment, in the spirit of this project's own standing
low-N stance (`docs/validated_operating_ranges.md`; see also the
project's `1 - p_value` finding there, already shown informative — a
Brier score below a flat 0.25 baseline across `N=100-3000` — but never
shown *calibrated*).

**Informative is not calibrated.** A score is informative if higher
values correlate with more often being correct — an ordering claim.
It is calibrated if the score's own numeric value equals the empirical
frequency of being correct among edges that received that value — a
much stronger, checkable-only-against-ground-truth claim. This charter
tests the stronger claim directly, on synthetic fixtures where truth is
known, rather than assuming it.

**Scope, deliberately narrow**: `mintnet.pipeline.growing_subset_dpi`
(the partial-correlation mechanism, D-053, unrestricted `PROCEED`) —
the only DPI mechanism in this project without an open `REASSESS` or a
scope restriction. CMIknn (`REASSESS`, D-059/D-064) and structured-
density (`REASSESS` outside `N>=1500`, D-064/D-065) compositions are
explicitly out of scope: calibrating a score against a mechanism that
itself hasn't earned unrestricted trust would conflate two open
questions. A future charter can extend this to either MI-based
mechanism once it reaches unrestricted `PROCEED` on its own terms.

## Mechanism

### Per-edge margin score

`growing_subset_dpi` uses an OR-rule growing-subset search: for a
candidate edge, test conditioning subsets of increasing size drawn from
its own connected component, **pruning immediately** the first time any
tested subset's p-value exceeds `alpha`, and **retaining** only if every
subset up to the search-depth cap rejects. This means "the decisive
p-value" is not the same quantity for both decisions:

- **Pruned edge**: the p-value that triggered the prune (already
  well-defined — the search stops there).
- **Retained edge** (non-empty pool): the *maximum* p-value among every
  subset actually tested — the single piece of evidence that came
  closest to overturning the retain decision. This is the correct
  "decisive" value for a retained edge precisely because retention
  requires *every* tested subset to reject; the weakest of those is the
  one margin should be measured against.
- **Isolated edge** (empty pool, retained unconditionally): no
  significance test ever ran. `decisive_p_value = NaN`, excluded from
  scoring — a structural certainty, not a statistical one.

**Implementation**: add one new field to `GrowingSubsetResult`,
`decisive_p_value: dict[tuple[int, int], float]`, populated per the
rule above. Purely additive — the existing `adjacency`,
`conditioning_size_used`, and `cap_reached` fields, and the pruning
logic itself, are unchanged.

**Margin formula**, applied to `decisive_p_value` at the `alpha` the
decision was actually made under:

```
margin = (alpha - p) / alpha            if retained
margin = (p - alpha) / (1 - alpha)      if pruned
```

Both branches land in `[0, 1]`: `0` at the decision boundary (a coin
flip), `1` at maximum distance from it in whichever direction the
decision went. This is deliberately decision-relative, not raw
`1 - p_value` — a confidently pruned edge (`p` far above `alpha`) and a
confidently retained edge (`p` far below `alpha`) should both score
near `1`, and both should score near `0` if the decisive evidence was a
near-tie, regardless of which way the coin landed.

### Calibration checks

For every edge-decision produced by the DGP sweep below, bin by margin
into deciles (`[0,.1), [.1,.2), ..., [.9,1.0]`) and compute, per bin,
the empirical accuracy — the fraction of decisions in that bin that
matched ground truth (an edge that should exist and was retained, or
should not exist and was pruned). Two separately falsifiable claims:

1. **Monotonicity** (ordinal, the weaker claim): empirical accuracy
   rises monotonically with margin bin, within sampling noise (Wilson
   95% CI overlap between adjacent bins counts as non-violating), at
   every tested `(N, motif)` cell.
2. **Calibration** (numeric, the claim this charter is actually
   chartered to test): Expected Calibration Error — mean, across bins,
   of `|mean(margin in bin) - empirical_accuracy(bin)|` — is at most
   `0.10` at every tested `(N, motif)` cell. `0.10` is a predeclared,
   disclosed tolerance choice (mirroring D-056's own tolerance-based
   defensibility precedent), not derived from the math.

Deciles were chosen (over coarser bins) because Fisher-z partial
correlation's own per-test cost is cheap enough to support the replicate
count fine bins need for tight per-bin Wilson CIs — confirmed by the
up-front timing measurement below, not assumed.

## Data-generating processes

Reuse this project's own already-chartered, known-truth fixtures —
deliberately, so any calibration claim this charter produces is scoped
to conditions the project can already stand behind independently, not
a new, uncharacterized DGP:

- Chain, measured fork (`sample_chain`, `sample_measured_fork`) —
  retain the two adjacent edges, prune the indirect pair.
- Triangle `balanced`/`moderate`/`strong`
  (`sample_precision_triangle`) — retain all three edges, including
  the historically hardest weak edge.
- `weak_edge_triangle` continuous sweep (`sample_weak_edge_triangle`)
  — the same structure as `strong`, with the weak edge's own strength
  swept, giving margin scores a continuous range of true-edge
  difficulty to be tested against, not just three fixed points.

`N in {300, 500, 750, 1000, 1500, 3000}` — this project's own shared,
previously-validated regime, reused unchanged rather than re-derived.
`alpha(N)`: D-012's existing calibrated formula, unmodified, exactly as
`growing_subset_dpi` already uses it in Stage 6a.

## Compute-cost disclosure

`compute_partial_correlation_evidence` is closed-form (Fisher-z, no
permutation test) — no real per-replicate timing measurement for this
exact configuration exists yet. Per this project's own standing
discipline: **measure real wall-clock cost of the full sweep on at
least one cell at the smallest and largest `N` before finalizing
replicate count or shard plan** — not assumed from the mechanism's
closed-form nature alone, however cheap that suggests it should be.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** —
unchanged, hard requirement, per this project's established practice,
regardless of how cheap the up-front measurement turns out to show this
mechanism to be.

## Selection and gate

**PROCEED**: both monotonicity and calibration (ECE `<= 0.10`) hold at
every tested `(N, motif)` cell. The "uncalibrated" caveat can then be
dropped for margin scores computed by `growing_subset_dpi`, **scoped
explicitly to this charter's own tested `N`/motif range** — not a
general claim, mirroring every prior charter's own scope discipline.

**REASSESS (recalibration case)**: monotonicity holds everywhere, but
ECE exceeds `0.10` somewhere. Margin remains valid for ordinal use
(ranking, flagging the weakest edges) but not as a literal probability.
A follow-up charter could fit an explicit recalibration mapping
(isotonic regression, on a development/validation split disjoint from
this charter's own replicates to avoid circularity) — not built here.

**REASSESS (defect case)**: monotonicity itself fails somewhere — a
genuine flaw in the margin formula, not just a scaling problem, needing
its own diagnosis before any recalibration attempt would be meaningful.

## Explicit non-goals

- **No claim about CMIknn or structured-density's own margin scores.**
  Neither mechanism has unrestricted `PROCEED` status; calibrating a
  score against either is separate future work, gated on that
  mechanism's own status first.
- **No production deployment of any recalibration mapping**, even on a
  clean `PROCEED` for raw margin — using margin as an approximate
  probability in a real (non-fixture) dataset is a further
  generalization step past synthetic conditions, a separate decision.
- **No claim outside the swept `N`/motif/strength range** tested here,
  mirroring every prior charter's own boundary discipline (e.g.
  D-065's own `N>=1500`-only scoping).
- **No Tier-1 (bootstrap-stability) work.** This charter is Tier-0
  only; Tier-1 remains a separate, not-yet-chartered extension of
  `mintnet.bootstrap.stability` to the mechanisms this project uses,
  named here only for context.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the up-front timing measurement and resulting replicate/shard
decision, raw per-edge-decision evidence (motif, `N`, strength,
replicate, `decisive_p_value`, `margin`, ground-truth correctness) for
every swept cell, the per-bin monotonicity and ECE tables, the gate
decision, and a report.

## Consequences

**If PROCEED**: `growing_subset_dpi`'s own margin score can be
presented to researchers as an approximately calibrated confidence
diagnostic within the tested range — a concrete, checked answer to
"how much should I trust this specific edge decision," complementing
(not replacing) the researcher's own theoretical judgment at low `N`
per this project's standing stance. Next named steps become live: (a)
extend the same check to CMIknn/structured-density once either reaches
unrestricted `PROCEED`; (b) design the Tier-1 bootstrap-stability
extension as a deeper, optional diagnostic.

**If REASSESS (recalibration case)**: margin stays usable for ranking
and flagging, with the numeric value explicitly caveated as
uncalibrated; a follow-up recalibration-mapping charter becomes a named,
not-yet-decided option.

**If REASSESS (defect case)**: the margin formula itself needs
rework before any calibration claim (numeric or ordinal) can be made —
diagnose whether the OR-rule's own `decisive_p_value` definition (max
over tested subsets for retained edges) is the source, since that is
the one design choice in this charter without a directly-established
precedent elsewhere in this project.
