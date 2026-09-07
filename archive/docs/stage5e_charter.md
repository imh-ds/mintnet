# Stage 5e Charter: Skeleton-Only PC-Algorithm Comparison — A Second, Structurally Different Incumbent (R6)

Status: **FROZEN before results**
Date: 2026-09-01

## Background and objective

D-047 through D-050 characterized MINT against one incumbent,
EBICglasso, across two axes (noise-column count, signal strength) on
shared Gaussian ground. Both MINT and EBICglasso target the same
underlying object via the same basic logic: a variable pair is an edge
iff conditioning on *every* other variable fails to explain the
association away (MINT: sequential per-edge conjunctive testing;
EBICglasso: a joint L1-penalized precision-matrix fit). This charter
adds a second incumbent that reaches the same target object —
conditional-independence edges — through a genuinely different
decision rule: the **PC algorithm** (Spirtes, Glymour & Scheines),
which tests whether a pair is independent conditioned on *some subset*
of neighboring variables, not all of them at once.

**Why this is worth doing, resolved in conversation before this
charter was frozen, not assumed:** an initial framing worried that
because PC also learns edge *direction*, its direction-finding search
would be entangled with which edges survive, making the skeleton
comparison uninterpretable ("could always be waved away as an
artifact of the orientation search"). That worry is correct for
**score-based** DAG learners (e.g. hill-climbing over a BIC-scored
search that adds/deletes/*reverses* edges as part of one joint
search), but it does not hold for **PC specifically**. PC runs in two
strictly sequential phases: phase 1 (skeleton) removes edges using
only conditional-independence tests over neighbor subsets; phase 2
(orientation) assigns arrowheads to the *already-fixed* skeleton and
never removes an edge phase 1 kept. **This charter runs phase 1 only
and never implements phase 2** — there is no orientation-search
component in this codebase's PC implementation at all, so the
"entangled with direction-finding" concern does not apply to what is
actually being run. What remains is an ordinary, disclosed
methodological difference (subset-conditioning independence tests vs.
all-at-once partial correlation / joint L1 estimation) — the same
kind of difference MINT and EBICglasso already have with each other,
not a categorically different problem.

## Comparator: PC-stable skeleton, implemented natively

No new dependency. A new module, `src/mintnet/comparators/pc_skeleton.py`,
implements the skeleton phase of PC-stable (Colombo & Maathuis, 2014 —
the order-independent variant, so results do not depend on an
arbitrary node-processing order):

1. Start from the complete undirected graph over the `p` variables.
2. For `ell = 0, 1, 2, ...`: using each pair's *own* adjacency set as
   it stood at the **end of the previous level** (the "stable" fix —
   not updated mid-level), test every pair `(i, j)` still adjacent
   against every size-`ell` subset `S` of `adj(i) \ {j}`. The test is
   the same Fisher-z partial-correlation test already used by MINT's
   own screening step (`r_{ij.S}`, Fisher-z transform, compared to a
   two-sided normal quantile at a fixed significance level). If any
   tested subset yields non-rejection, remove edge `(i, j)` and record
   `S` as its separating set (not used further in this charter, kept
   only because dropping it silently would misrepresent the
   algorithm).
3. Stop increasing `ell` once no remaining adjacent pair has an
   adjacency set of size `>= ell`. Output: the final undirected edge
   set. No orientation step follows.

## Fair-comparison rules (extending Stage 5a's own rules)

- **Edge definition.** PC: an edge is present iff it survives every
  level of the skeleton phase above. No secondary threshold.
- **Significance level, fixed not tuned.** `alpha_pc = 0.01` — the
  value used throughout the PC algorithm's own canonical tutorial
  (Kalisch & Bühlmann, 2007) and `pcalg`'s own worked examples, used
  here as a literature convention, exactly the same posture as
  EBICglasso's `gamma = 0.5`. **Not searched, not adjusted per `p` or
  `N` inside this charter.**
- **No orientation phase.** Stated once above, repeated here as a
  fair-comparison rule because it bounds the claim: this charter
  measures skeleton (undirected structure) recovery only. It says
  nothing about, and makes no claim about, PC's own ability to infer
  causal direction — that is a different capability this charter does
  not test.
- **Data access.** Paired with D-047's own draws, not merely
  comparable to them: this charter reuses `stage5a._condition_seed`
  and `stage5a`'s own `master_seed` unchanged, so every `(dgp, N,
  replicate)` cell draws the **identical** simulated dataset D-047's
  MINT and EBICglasso numbers were computed on. MINT and EBICglasso
  are not re-run in this charter (no new information would come from
  re-running them on data they already saw); D-047's own published
  per-cell numbers (`docs/decision_log.md`) are used as the reference
  for those two methods, and PC's fresh numbers are computed on the
  same draws for direct comparison.
- **Scoring.** Adjacency precision, recall, F1, SHD against the
  identical known ground-truth graph, computed identically to every
  prior R6 charter.

## Data-generating processes and grid

Identical to Stage 5a's own full grid, reused unmodified, for direct
row-by-row comparability against D-047's own published table: five
shapes (`chain_fork_hub`, `overlap`, `triangle_balanced`,
`triangle_moderate`, `triangle_strong`), `N = [400, 500, 600, 750,
1000, 1500, 1750]`, `2,000` replicates per cell (development `0`-`999`
/ validation `1000`-`1999`, though this charter has no fresh tuning to
develop — retained for reporting consistency with prior practice, same
rationale Stage 5a itself gave).

## Metrics and reporting

Per `(dgp, N)`, one row per method, all three methods shown together
(MINT and EBICglasso from D-047's own published numbers, labeled as
such; PC computed fresh in this charter): precision, recall, F1, SHD,
runtime. Full grid, no cell omitted regardless of outcome.

## Explicit non-goals for this charter

- **No orientation / causal-direction claim of any kind**, for PC or
  otherwise. See "Fair-comparison rules" above.
- **No score-based DAG learner** (hill-climbing, BIC-scored search).
  The entanglement concern raised in conversation does apply to that
  family; it is out of scope here, not silently resolved by this
  charter's own result.
- **No retuning of `alpha_pc` after seeing results**, and no `p`- or
  `N`-adjusted version of it inside this charter (mirroring Stage 5a's
  own EBICglasso `gamma` treatment, before Stage 5c's later `alpha(p)`
  question was opened for MINT specifically).
- **No re-running of MINT or EBICglasso.** Their numbers are D-047's
  own, referenced not regenerated (mirrors Stage 5c's own precedent of
  referencing D-048's published numbers rather than re-deriving them).

## Decision structure

Descriptive, not a gate — same standing as every prior R6 charter.
Predeclared reporting requirement: for each of the five shapes, state
which of

1. PC's skeleton recovery is comparable to or better than MINT's own
   D-047 numbers at the same `N`,
2. PC's skeleton recovery is comparable to or better than EBICglasso's
   own D-047 numbers but not MINT's,
3. PC trails both MINT and EBICglasso materially at most tested `N`,

holds, plus a runtime comparison, plus an explicit recall check (has
this arc's "the gap is entirely precision, not detection" finding held
for a third method, or does PC ever miss real edges that the other two
find) — the recall question gets its own sentence regardless of the
answer to the ranking question above, mirroring Stage 5d's own
discipline.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate PC metrics for every `(dgp, N)` cell, and a
report presenting the full three-method grid (PC fresh, MINT/EBICglasso
referenced from D-047) plus the predeclared ranking and recall-check
statements above.

## Consequences

Adds a second, structurally different incumbent to R6's "does the
method occupy a meaningful niche" question, without reopening or
retracting D-047 through D-050 (all remain valid readings of the
EBICglasso comparison specifically). Extends this arc's own
data-type-scope limitation identically: PC's skeleton phase, as
implemented here, is a Gaussian partial-correlation test, so this
charter stays within the same continuous-Gaussian scope already
disclosed in `docs/validated_operating_ranges.md`'s own "Scope
limitation, data type" note — not a step toward mixed/discrete data
support, which remains explicitly future work.
