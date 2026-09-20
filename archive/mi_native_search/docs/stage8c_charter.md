# Stage 8c Charter: Does Tier-0 Margin Calibration Transfer to the Composed Tier? (main)

Status: **FROZEN before results**
Date: 2026-09-07

## Background and objective

D-066/D-067 characterized and (for the prune decision specifically)
recalibrated the Tier-0 margin score entirely on isolated 3-node
fixtures (chain, fork, triangle, `weak_edge_triangle`). This project's
own standing discipline — never trust an isolated-tier finding until
it survives composition (Stage 6a, Stage 7, Stage 7e all test an
isolation tier before a composed tier) — has not yet been applied to
the confidence-score work at all. This charter is that check.

**Two separate questions, deliberately not conflated**:

1. **Does raw margin's own calibration profile — well-calibrated for
   retain decisions, imperfect for a specific prune-decision case —
   hold up when `growing_subset_dpi` runs on a real composed p=15
   network**, where edges face screening noise and the cascading
   interactions this project has documented elsewhere (D-042, D-043),
   not an isolated 3-node motif?
2. Separately, exploratory, non-gating: **can a freshly-fit
   recalibration curve, built directly from the composed network's own
   evidence**, bring an under-calibrated decision type within
   tolerance the same way Stage 8b did for chain/fork in isolation?

**Question 1 explicitly does not reuse D-067's own chain/fork curve.**
`growing_subset_dpi`'s own `motif_family` parameter exists precisely so
a caller only invokes a recalibration curve when the edge's own DGP
identity is actually known — a composed network's own edges have no
such label (they are not individually "a chain" or "a fork"), so
passing one here would be exactly the unvalidated generalization that
parameter's own docstring disclaims. This charter therefore evaluates
**raw margin only** (`motif_family=None`) against the composed
network's own ground truth for question 1.

## Mechanism

Reuses Stage 6a's own composed-tier infrastructure unchanged (D-053):
`compute_pairwise_screening_evidence`/`screen_uncorrected` to build the
candidate graph, `growing_subset_dpi` (raw margin, `motif_family=None`)
for pruning, `stage5a`'s own DGP registry/seed derivation/
`_true_adjacency` for ground truth — the identical pipeline Stage 6a's
own composed tier already validated, run here to score margin, not to
re-litigate Stage 6a's own accuracy findings.

For every candidate edge in every replicate: record `decisive_p_value`,
`margin` (`motif_family=None`), whether the edge is a true edge (via
`_true_adjacency`), and whether the decision was correct. Bin by
margin decile and compute monotonicity/ECE exactly as Stage 8a's own
`stage8a_calibration_reporting` does — reused unchanged, split by
**DGP and true/false edge status** (a composed network has no clean
motif-family label the way an isolated fixture does, but it does have
clean true/false edge ground truth, which is the axis D-066's own
finding actually turned on).

**Exploratory sub-question (question 2)**: fit a fresh isotonic curve
per `(DGP, N)` directly on this charter's own composed-tier evidence
(not D-067's), with the same development/validation replicate split
discipline Stage 8b used, and report whether it brings the
worse-calibrated cell(s) within the `0.10` tolerance. Descriptive only
— this charter does not deploy or wire in whatever curve results.

## Data-generating processes

`chain_fork_hub` and `overlap`, `p=15` (Stage 6a's own composed shapes,
`stage5a`'s registry, unchanged), strength `0.5` (Stage 6a's own
`composed_strength`), `composed_screening_alpha=0.001`,
`max_conditioning_size=4` — every value reused unchanged from
`configs/stage6a_conditioning_architecture.yaml`, not re-derived.
`N in {400, 500, 600, 750, 1000, 1500, 1750}` (Stage 6a's own composed
grid). **Disclosed comparability gap**: this grid overlaps Stage 8a's
own isolated-tier grid (`{300,500,750,1000,1500,3000}`) only at
`{500, 750, 1000, 1500}` — `400`/`600`/`1750` have no directly matching
isolated-tier `N` to compare against, and `300`/`3000` have no matching
composed-tier `N`. Comparisons at the four shared `N` values are direct;
elsewhere, comparison is qualitative (trend, not point-matched).

`alpha(N)`: D-012's own formula (`fit_candidate_forms`/`select_form`),
identical to Stage 8a's and Stage 6a's own usage.

`master_seed=80200` (Stage 8-series tag, following Stage 8a's `80100`).

## Compute-cost disclosure

**No assumption from Stage 8a's own cost carries over.** Stage 8a's
per-replicate cost (`~2.8ms`) was measured on a 3-node motif with a
single conditioning test per edge; a `p=15` composed network's own
growing-subset search visits many more candidate subsets per replicate
and also requires the screening step first. Per this project's own
standing discipline: **measure real per-replicate wall-clock cost of
the full screen-then-prune-then-score pipeline on at least one DGP at
the smallest and largest `N` before finalizing replicate count or
shard plan.** A provisional planning figure (not a commitment): Stage
6a's own composed tier used `R=2000` at this same grid, successfully,
via GitHub Actions sharding — a defensible starting point, adjusted
after direct measurement, not assumed.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run** —
unchanged, hard requirement, per this project's established practice.

## Selection and gate

**Narrow gate, on question 1's own true-edge (retain) case only** —
the one thing D-066 already showed calibrated in isolation, and the
one case composition could plausibly break in a way that would be a
genuinely new, more concerning finding:

- **PROCEED**: for true edges specifically, raw margin's ECE stays
  `<= 0.10` at every tested `(DGP, N)` cell, and monotonicity holds —
  i.e., composition does not degrade what was already working.
- **REASSESS**: either fails for true edges — would mean composition
  itself (screening noise, cascading interactions) breaks a previously
  clean result, worth its own diagnosis before any further
  confidence-score work proceeds.

**False-edge (prune) calibration is reported descriptively, not
gated.** D-066 already established this case is imperfect in
isolation; this charter's job is to characterize how it looks composed
(better, worse, or the same shape), not to re-adjudicate whether it
was acceptable to begin with.

**Question 2 (the exploratory fresh-curve fit) is fully descriptive,
no gate** — a finding for a possible future charter to act on, not a
decision this charter makes.

## Explicit non-goals

- **No use of D-067's own chain/fork curve on composed-network edges.**
  Explained above; a composed network's edges have no motif-family
  label to justify it.
- **No re-litigation of Stage 6a's own accuracy findings** (precision/
  recall/F1, conditioning-dimension distribution) — those stand from
  D-053; this charter only scores margin/confidence on the same
  pipeline's own decisions.
- **No production deployment of any curve this charter fits.** Purely
  descriptive, per question 2's own framing above.
- **No claim outside the tested `N`/DGP/strength grid.**
- **No extension to CMIknn or structured-density.** Same D-053-only
  scope restriction as Stage 8a and 8b.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, the up-front timing measurement and resulting replicate/shard
decision, raw per-edge evidence, the true-edge gate's own
monotonicity/ECE table and decision, the false-edge descriptive
table with a direct comparison against D-066's own isolated-tier
numbers at the four shared `N` values, the exploratory fresh-curve
fit/validation result, and a report.

## Consequences

**If PROCEED**: the Tier-0 diagnostic's own "calibrated for retain
decisions" property is confirmed to survive composition, not just
isolation — a materially stronger claim than D-066 alone supported.
If question 2's exploratory curve also looks promising, that motivates
a follow-up charter to actually validate and deploy a composed-tier
recalibration mapping (not decided here). If it does not, that is
itself a useful, disclosed negative result — recalibration may be a
harder problem in the composed setting than in isolation, worth
knowing before investing further.

**If REASSESS**: composition introduces a genuinely new problem beyond
what D-066 characterized — the true-edge case, previously clean, is no
longer. This would need its own diagnosis (is it a screening-alpha
interaction, a cascading-error effect like D-042/D-043, or something
specific to margin's own formula under composition) before any further
confidence-score work is worth pursuing.
