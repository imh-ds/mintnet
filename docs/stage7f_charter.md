# Stage 7f Charter: Mapping the N x Effect-Size Detection Frontier, and Exposing a Continuous Per-Edge Confidence Score Instead of a Forced Binary Decision (mi-native)

Status: **FROZEN before results**
Date: 2026-09-09

## Background and objective

Stage 7's own isolation-tier arc (D-059 through D-065) established a
precise finding: at `N=750`, no single `alpha` simultaneously satisfies
chain/fork's own pruning requirement and the `strong` triangle
fixture's own weak-edge (`target_rho=-0.08`) retention requirement,
while `N=1500` has a comfortable feasible window. That finding was
measured at exactly one weak-edge strength and two `N` values — it
does not say where the real boundary is as a function of effect size,
nor whether `N<750` might already work for larger effects.

**A second, more fundamental point emerged from discussion with the
user, and it reframes what this charter should actually build.**
`growing_subset_dpi`'s own decision rule (mirrored unchanged in
`growing_subset_dpi_structured_density`) already has an asymmetric
structure: an edge is **retained** only if every tested conditioning
subset *rejects* independence (a strict, repeated, conjunctive bar —
exactly why D-076 found retain decisions are ~100% reliable). An edge
is **pruned** the moment any single subset *fails to reject*
independence. Failing to reject independence is not evidence of
independence — it is only an absence of evidence for dependence. The
current mechanism silently treats the two as equivalent, labeling the
"insufficient evidence" outcome "pruned" as if it had been proven
absent. At `N=750`, the `strong` triangle's own weak edge fails to
reject not because it is truly independent, but because there is not
enough power to detect it — and the current binary output has no way
to distinguish "confidently absent" from "we don't know."

**Trying to fix the "confident prune" side directly does not work**:
loosening `alpha` to catch the weak edge more often necessarily
loosens the same threshold for chain/fork's own genuinely-null edges,
degrading retain's own reliability there (this is exactly the D-059/
D-065 tension restated, not a new problem to solve). **The fix that
does not fight this limit**: stop forcing a binary retain/"pruned"
call at all. Report a continuous, per-edge confidence score instead,
and let the achievable confidence ceiling — which this charter
explicitly maps as a function of `N` — inform what threshold a
researcher chooses to treat as "good enough," given their own
theoretical priors and tolerance for risk. This does not require, and
this charter does not attempt, resolving the underlying power limit —
it requires reporting honestly around it.

## Mechanism

**Part A -- frontier mapping (point-estimate baseline, unchanged from
this charter's own first draft).** Reuse `growing_subset_dpi_
structured_density` (Stage 7e, `degree=1`) unmodified for the decision
itself. Sweep:

- `N in {400, 500, 600, 700, 750, 1000, 1500}`.
- Weak-edge target partial correlation `|target_rho| in {0.08, 0.12,
  0.16, 0.20, 0.25}` (`sample_weak_edge_triangle`'s own parameterized
  family, already implemented for D-060/D-062 -- no new DGP code).
- Chain/fork's own indirect-edge null, unchanged, at every tested `N`.

For each `(N, target_rho)` cell, reuse D-065's own free re-analysis
technique (compute once, threshold `41` alpha-grid points from `.05`
to `.35` step `.01` purely from stored p-values) to determine whether
any feasible `alpha` exists, and its width. Output: a lookup table --
`N -> smallest resolvable |target_rho|` and `|target_rho| -> smallest
sufficient N` -- the concrete accessibility answer this project has
been missing, and the calibration backbone Part B needs (see below).

**Part B -- expose a continuous per-edge confidence score on
`growing_subset_dpi_structured_density`, mirroring the pattern already
built and used on the Fisher-z engine.** `mintnet.pipeline.growing_
subset_dpi.GrowingSubsetResult` already carries `decisive_p_value`
(the weakest piece of evidence behind a retain decision, or the
triggering p-value behind a prune) and `confidence` (a `[0,1]` score
via `mintnet.confidence.margin.edge_margin`, explicitly disclosed as
"ordinal-only... unless a validated recalibration curve exists" —
docs/stage8a_charter.md). `growing_subset_dpi_structured_density`
(`StructuredDensityGrowingSubsetResult`) has never had this exposed --
it returns only the binary `adjacency`, `conditioning_size_used`, and
`cap_reached`. This charter adds `decisive_p_value` and `confidence`
fields to it, computed identically (same "maximum p-value among
subsets that all had to reject for retention to hold" logic, same
`edge_margin` call) -- **purely additive, zero new compute**: the
p-values these fields need are already produced inside the existing
search loop, just not currently returned. `adjacency`'s own binary
output is unchanged and remains available for any caller that wants
the current retain/pruned behavior unmodified.

**Verification (a real, falsifiable check, not assumed to "just
work")**: using Part A's own generated evidence (every replicate
already has known ground truth), confirm the exposed confidence score
is actually informative on this estimator -- specifically: (1) at each
tested `N`, confidence-score distributions for genuinely-null
(chain/fork indirect) edges are measurably lower than for real edges at
or above that `N`'s own Part-A-mapped detection floor; (2) a real
edge's own average confidence score increases with effect size and
with `N`, not flat or non-monotonic. Neither is assumed from the
Fisher-z engine's own already-validated behavior (D-066-D-068's own
recalibration arc found real, disclosed surprises even there — e.g.
D-068's false-edge case not transferring cleanly) -- this estimator's
own confidence score is checked directly, on its own evidence.

## Data-generating processes

Identical to this charter's own first draft: `sample_weak_edge_
triangle`, `sample_chain`, `sample_measured_fork`, isolation tier only.
No composed-tier work in this charter.

## Compute-cost disclosure

**Part A**: unchanged from this charter's own first draft -- cheap,
comparable to Stage 7e's own isolation tier (`5.6s`-`9.3s` per 3-pair
evidence computation, D-062).

**Part B**: negligible incremental cost beyond Part A's own evidence
generation -- `decisive_p_value`/`confidence` are computed from
p-values the search already produces; no bootstrapping, no additional
significance tests, no new DGP draws. The verification step reuses
Part A's own raw evidence entirely.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing**, per this project's own
established practice for Part A's own evidence generation.

## Selection and gate

**Part A has no PROCEED/REASSESS gate** -- descriptive, required
evidence, mirroring D-060's own power-curve mapping.

**Part B gate**: **PROCEED** (the confidence score is adopted as a
documented, available output field, and `docs/validated_operating_
ranges.md` records N-dependent guidance on interpreting it) if both
verification checks above hold at every tested `N`. **REASSESS**
(the field may still be added for diagnostic use, but is NOT
documented as a trustworthy signal for researcher-facing decisions)
if either check fails anywhere -- an honest negative result, not a
blocker to Part A's own frontier table standing on its own.

## Explicit non-goals

- **No claim that `confidence` is a calibrated literal probability.**
  Ordinal-only, exactly mirroring the Fisher-z engine's own existing
  disclaimer -- a dedicated recalibration charter (mirroring Stage
  8b/8c's own arc for the Fisher-z engine) is separate, not-yet-decided
  future work, only worth chartering if this charter's own PROCEED
  holds.
- **No universal recommended confidence threshold.** This charter's
  own explicit point is that the right threshold is `N`-dependent and
  a researcher's own choice given their theoretical priors -- Part A's
  table informs that choice, it does not replace it with a new fixed
  rule.
- **No composed-tier evidence**, no re-tuning of `degree`/`k_perm`/any
  other estimator parameter, no claim about `N<400`, no production
  deployment authorization even on a full PROCEED -- unchanged from
  this charter's own first draft.
- **No change to `growing_subset_dpi_structured_density`'s own binary
  `adjacency` output or default behavior.** Purely additive fields; any
  existing caller relying on `adjacency` alone is unaffected.
- **No claim this transfers to `growing_subset_dpi_mi` (CMIknn).** This
  charter scopes to the structured-density engine only, per Stage 7e's
  own established operating setting (D-063); CMIknn's own confidence-
  score behavior, if ever wanted, is separate future work.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, Part A's own full `N x target_rho` frontier table, Part B's
own added fields' full per-replicate distribution (confidence score by
edge type/N/effect size), both verification checks' own results
(pass/fail per `N`, with the actual separation/monotonicity evidence
shown, not just a verdict), and a report.

## Consequences

**Part A (always produced)**: replaces today's binary "`N=750`
REASSESS, use `N>=1500`" recommendation with an effect-size-conditional
lookup table. `docs/validated_operating_ranges.md` should record it
directly, superseding D-065's single-point characterization without
contradicting it.

**If Part B PROCEEDs**: researchers working at `N<1500` gain a real,
disclosed accessibility path this method did not have before --
instead of a hard REASSESS, a continuous confidence score plus
`N`-specific guidance on what that score can and cannot promise at
their own sample size ("you don't get all the bells and whistles" —
lower `N` means accepting a lower achievable confidence ceiling on
weak edges specifically, an explicit, informed tradeoff rather than a
silent one). This is a reporting/interface change, not a new
statistical claim about detection power.

**If Part B REASSESSes**: the confidence score built the same way as
the Fisher-z engine's own does not transfer cleanly to the structured-
density estimator -- informative in itself (mirrors D-068's own
disclosed false-edge-transfer surprise for a different pair of
mechanisms), and would motivate its own follow-up diagnostic before
ever being exposed as researcher-facing guidance. Part A's own
frontier table is unaffected either way.
