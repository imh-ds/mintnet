# Stage 3b Charter: Stability Filtering to Rescue the Overlap DGP's N=750 Failure (R4b)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-018 found the shared-node-overlap DGP REASSESSes at `N=750` (overlap
indirect-edge pruning TPR `.569`, below the `.80` gate), traced to
screening's weak (`~66%`) per-edge detection power for this DGP's
`~.135` cross-branch correlation, not to any DPI defect. D-019's
diagnostic bootstrap run on this same DGP found the wrongly-retained
indirect edges are not indistinguishable from true edges in stability
(`pi_final ~.53` pooled) — but flagged the pooled figure as "an
observation, not a validated fix," and explicitly deferred whether
stability filtering, *gated on this DGP itself*, could measurably
repair the failure (Section 17.6's second bullet: "improves topology
quality under a calibrated rule").

**This charter corrects and replaces D-019's pooled framing before
building on it.** Pooling `pi_final` across both correctly-pruned and
wrongly-retained instances of the same edge type mixes two different
populations and is the wrong statistic for calibrating a filter that
only ever acts on edges the point estimate already kept. Splitting by
the point estimate's own decision (`final_point`), using the raw
evidence already in `results/generated/stage3_bootstrap/raw_metrics.csv`
(the frozen secondary-DGP rows from Stage 3, D-019 — no new simulation,
just a different slice of already-frozen evidence):

| `final_point` | count | mean `pi_final` | median |
|---|---|---|---|
| correctly pruned (False) | 60 | `.322` | `.270` |
| wrongly retained (True) | 60 | `.737` | `.745` |

The wrongly-retained edges are *more* stable than the pooled figure
suggested, not less — because the same data draw that fooled the point
estimate tends to fool most of its own bootstrap resamples too. D-019's
passing remark that a `pi_min=.70` filter (calibrated on a different
DGP, in Stage 3's primary charter) "would in fact fall below threshold
most of the time" is not accurate for the conditional population that
matters: only `40%` of wrongly-retained overlap edges fall below `.70`.
A materially higher threshold is needed, and — checked before writing
this charter, not assumed — one appears available with no observed cost
to true edges in the same evidence:

| `pi_min` | % of wrongly-retained overlap edges removed | % of true-direct edges wrongly removed |
|---|---|---|
| `.80` | `63.3%` | `0.0%` (`n=300`, min observed `pi_final=.996`) |
| `.90` | `81.7%` | `0.0%` |
| `.95` | `96.7%` | `0.0%` |
| `.98` | `98.3%` | `0.0%` |

**This charter is expected to PROCEED at `N=750`** with a selected
`pi_min` somewhere in `{.90, .95, .98}`, per this pre-charter check —
stated as an expectation to be confirmed on fresh, gated evidence (60
replicates with a real development/validation split, not the 30
ungated descriptive replicates this pre-check reused), not assumed from
a 30-replicate exploratory slice.

## Mechanism

A **post-hoc stability filter**, layered after the existing, unmodified
screen-then-prune pipeline — no change to screening, DPI, or
`mintnet.pipeline.compose`:

1. Run the frozen pipeline on the original dataset, producing the
   point-estimate final graph (unchanged from every prior charter).
2. Compute bootstrap final-edge stability on that same dataset
   (`mintnet.bootstrap.compute_edge_stability`, `B=500`, same fixed
   `alpha` values — identical mechanism to Stage 3, reused, not
   reimplemented).
3. **Filtered final graph** = point-estimate final graph, with every
   edge `(i,j)` removed if `pi_final[i,j] < pi_min`. This can only
   *remove* edges relative to the point estimate, never add one back —
   a strict refinement, not an independent second opinion.

**Most of this charter's gate criteria are safe by construction, not
open empirical questions — stated explicitly so the charter does not
imply uncertainty where none exists:**

- Chain and fork indirect-edge TPR can only stay the same or improve
  under filtering (an already-pruned edge stays pruned; filtering can
  only additionally remove a still-present one). Reported as evidence,
  not a live risk.
- The final false-edge rate (null pairs) can only stay the same or
  improve, for the same reason.

**The two criteria that are genuine, unresolved empirical questions**
(the actual point of running this charter rather than trusting the
pre-charter check): does overlap indirect-edge TPR, after filtering,
actually clear `.80` at `N=750` on fresh gated evidence — and does
filtering avoid collateral removal of true direct edges, at a
statistical resolution (60 replicates, formally gated) beyond the
30-replicate descriptive pre-check.

## Data-generating process

Identical to `docs/stage2d_charter.md` / Stage 3's secondary DGP:
`p=15`, chain (0-2), measured fork (3-5), shared-node overlap (6-10,
node 8 shared), 4 noise columns (11-14), strength `.5`. `N = [750,
1500]` (both tested, per this project's standing per-N practice — the
objective is `N=750`'s rescue, but `N=1500` needs its own no-regression
check, not an assumption). Master seed `20260829`, screening
`alpha=.001` (D-013), DPI `alpha=f(N)` (D-012), `B=500` bootstraps per
dataset (Stage 3's validated setting, D-019 — not retuned here).

**60 outer replicates per `N`, split development (0-29) / validation
(30-59)** — twice Stage 3's secondary-DGP replicate count, because this
DGP is now gated (needs a real held-out validation split) rather than
purely descriptive.

Ground truth unchanged from Stage 2d: 10 true direct edges; indirect
edges tracked **per motif, not pooled** (chain 1, fork 1, overlap 4 —
the same anti-pooling discipline as D-018, motivated by the same D-004
precedent); 89 null pairs.

## Selection and gate

Candidate thresholds `pi_min in {.80, .90, .95, .98}` — the four values
checked in the pre-charter analysis above, not the Stage 3 primary
DGP's `{.70, .80, .90}` grid, since that grid was calibrated on a
different DGP and this charter's own evidence shows `.70` is too low
here.

Per `N`, independently, using development replicates: a `pi_min` is
*eligible* if, after filtering:

1. **Overlap indirect-edge TPR `>= .80`** (D-018's original gate,
   unmet at the point estimate at `N=750` — this is what the charter
   tests).
2. **True-edge retention FPR `<= .10`** (all 10 true direct edges,
   post-filter).
3. Chain and fork indirect-edge TPR do not decrease relative to the
   point estimate (sanity check on the safe-by-construction property
   above — a violation would indicate an implementation bug, not a
   real trade-off).
4. Filtered final false-edge rate does not exceed the point estimate's
   own final false-edge rate by more than `.01` (no-regression check,
   same tolerance as every prior composition charter — also expected
   to hold trivially by construction).

Among eligible `pi_min` values, select the **smallest** (least
aggressive filter — removes the fewest edges beyond what is needed,
same simplicity tiebreak as every prior threshold-selection charter).
The selected `pi_min` must meet all four criteria again on validation
replicates (30-59), with no recorded error, to PROCEED for that `N`. If
no `pi_min` is eligible on development, REASSESS: "stability filtering
does not clear the overlap gate at this `N`" — informative either way,
not a bug to chase.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (point-estimate and filtered final
graphs' relevant edge statuses, per-motif indirect TPR before and after
filtering, true-edge FPR before and after, final false-edge rate before
and after, `pi_final` for every edge), aggregate metrics, the per-N
decision table, report, and figures (overlap indirect TPR vs. `pi_min`,
before/after comparison, per `N`).

## Consequences

If PROCEED at `N=750`: this would be the first charter in this project
to demonstrate a *repair* for a previously identified failure mode
without collecting more data, not merely a validation or invalidation
of an existing mechanism — a materially different kind of result,
requiring correspondingly careful scoping. It would validate stability
filtering as a rescue mechanism **only for this exact DGP** (the
shared-node-overlap shape, `~.135` cross-branch correlation, `p=15`,
`N=750`). It would **not** validate: stability filtering for other
under-powered shapes or weaker signals (untested whether the same
`pi_min` range transfers), the `B=500` bootstrap cost as an acceptable
production default (roughly 500x the base pipeline's per-dataset cost —
a real practical concern for any future production-default decision,
not a charter gate criterion), or adopting a stability-filter stage as
a permanent addition to `mintnet.pipeline.compose` (an architecture
decision requiring its own design discussion, separate from this
charter's narrower mechanism-validation question).

If REASSESS at `N=750`: since three of the four criteria are safe by
construction (see Mechanism), a failure almost certainly means either
(a) overlap TPR still falls short of `.80` even at the highest tested
`pi_min=.98` — the wrongly-retained edges' stability distribution does
not separate cleanly enough at full statistical resolution, unlike the
30-replicate pre-check suggested — or (b) true-edge FPR exceeds `.10`
at whatever `pi_min` clears criterion 1, a genuine trade-off the
pre-charter check's `n=300`, `0%`-cost sample was too small to detect.
Report which one occurred; they have different implications (a) is a
statement about the failure mode's separability, (b) is a statement
about this specific `pi_min` grid's resolution and might warrant a
finer grid before concluding the mechanism doesn't work.

If REASSESS at `N=1500` (unexpected, since the point estimate already
PROCEEDs there before any filtering): would indicate filtering
introduces a genuine regression at this `N`, worth investigating before
trusting the mechanism anywhere.
