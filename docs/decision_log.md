# Methodological Decision Log

## D-001: Proceed from Gaussian MI validation to Stage 1 chartering

Date: 2026-08-28

Stage: R1 / Stage 0.1

Status: PROCEED

Decision timing: Predeclared gate evaluated after results

Question: Is the in-repository bivariate KSG-1 estimator viable at the
intended continuous Gaussian sample-size regime?

Prior specification: `docs/stage0_charter.md` fixed the conditions, 500
replicates, development-only k selection, and validation-only proceed gate
before results were generated.

Evidence: `results/generated/stage0_gaussian/decision.json` records 72,000
estimates, zero estimator errors, selected `k=20`, maximum moderate-signal
absolute bias of 0.0134 nats, maximum moderate-signal RMSE of 0.0452 nats,
Spearman strength ranking of 1.00, and null 95th percentile of 0.0213 nats.

Decision: Proceed to a new frozen Stage 1 charter for tolerant-DPI chain,
measured-fork, and true-triangle motif validation.

Rationale: All predeclared Stage 0.1 validation criteria passed. This decision
is limited to the tested continuous Gaussian estimator regime.

Consequences: Do not add screening, bootstrap, mixed-type, synergy, or public
network API layers. Stage 1 must receive its own DGPs, thresholds, seeds, and
stop/reassess gate before implementation.

## D-002: Reassess tolerant-DPI motif validation

Date: 2026-08-28

Stage: R2 / Stage 1

Status: REASSESS

Decision timing: Predeclared gate evaluated after results

Question: Does tolerance-modified DPI remove observed transitive dependencies
from continuous Gaussian chains and measured forks without pruning genuine
conditional-dependence triangle edges, for some adjacent tolerance pair?

Prior specification: `docs/stage1_charter.md` froze the chain/fork/triangle
DGPs, `N` grid, strengths, tau grid `[0, .05, .10, .15, .20, .25, .30, .40,
.50]`, 500 replicates, development/validation replicate split, and the
proceed gate (chain/fork TPR `>= .80` and triangle FPR `<= .10` at `N >= 500`
for two adjacent tau values) before results were generated.

Evidence: `results/generated/stage1_dpi/decision.json` records 243,000 raw
estimates, zero estimator/DGP/Cholesky errors, and
`"no eligible development tau pair"`. Pooled development-replicate metrics
(`N in [500, 750, 1000]`) show chain/fork indirect-edge pruning TPR `>= .938`
at every tau, but triangle true-edge pruning FPR never drops below `.117`,
even at `tau = .50`, the top of the frozen grid. See
`docs/stage1_report.md` for the full per-tau breakdown.

Decision: Reassess. Do not select a public default tau, and do not proceed to
Stage 2 candidate-edge screening on this evidence.

Rationale: The binding failure is triangle true-edge over-pruning, not
chain/fork under-pruning or estimator/sample-size failure. Tolerant DPI, as
chartered, cannot reach a jointly passing tau within the tested range; the
FPR floor near `tau = .50` does not improve with `N`, indicating a mechanism
property rather than an incomplete or noisy run. Extrapolating past the
frozen tau grid would not be a valid post hoc adjustment under this charter.

Consequences: Stage 2 candidate-edge screening, bootstrap reproducibility,
and later layers remain blocked. Any further tolerant-DPI work requires a new
charter — for example, a wider or differently shaped tolerance grid, or a
reconsidered pruning rule for the triangle motif — frozen before new results,
per the outline's mechanism-by-mechanism falsification requirement.

## D-003: Reassess conditional-independence motif validation (Stage 1b / R2b)

Date: 2026-08-28

Stage: R2b / Stage 1b

Status: REASSESS

Decision timing: Predeclared gate evaluated after results

Question: Does pruning by each edge's own conditional-independence test
(Gaussian partial correlation, exact for conditional MI on this DGP) fix the
D-002 failure, where magnitude-ratio DPI could not distinguish a real-but-
weaker triangle edge from a fake indirect one?

Prior specification: `docs/stage1b_charter.md` froze the same chain/fork/
triangle DGPs, `N` grid, strengths, 500 replicates, and development/
validation split as the R2 charter, substituting an `alpha` grid `[.0001,
.001, .005, .01, .05, .10, .20, .30, .50]` and the same proceed gate
structure (chain/fork TPR `>= .80`, triangle FPR `<= .10`, two adjacent
alphas, all validation cells).

Evidence: `results/generated/stage1b_dpi/decision.json` records 243,000 raw
estimates, zero errors, and selection of adjacent pair `(0.05, 0.10)` on
pooled development data, failing one validation criterion (triangle
genuine-edge pruning FPR) at `strong`-family cells: `alpha=.05` at `N=500,
750`, and `alpha=.10` at `N=500`. Unlike D-002, the pooled development
curves for chain/fork TPR and triangle FPR now overlap in a shared feasible
region (`alpha` roughly `[.05, .20]`), and the `balanced`/`moderate`
triangle families pass cleanly. The `strong` family's FPR improves
monotonically with `N` at every alpha (e.g., `alpha=.05`: `.187` at `N=500`
down to `.111` at `N=1000`, development replicates), unlike D-002's
`N`-invariant floor. See `docs/stage1b_report.md` for the full breakdown.
Exploratory (non-gating) tracking of `1 - p_value` as a candidate
confidence-style score (not a validated calibration) against ground truth
gives a pooled Brier score of `.081` against a flat `.25` baseline,
improving with `N`.

Decision: Reassess. Do not select a public default alpha, and do not
proceed to Stage 2 candidate-edge screening on this evidence.

Rationale: This result confirms the D-002 diagnosis — the R2 failure was the
magnitude-ratio comparison confusing "weaker but real" with "fake," not an
inherent limit of DPI-style pruning. Testing each edge's own conditional
dependence resolves two of three triangle fixtures outright and narrows the
third to specific small-`N` cells with a trend, not a floor. That is real
progress, but it does not meet the frozen gate on this grid, and the charter
does not permit selecting a different `N` floor or alpha resolution after
seeing results.

Consequences: Stage 2 and later layers remain blocked. A follow-up charter
extending the `N` floor or refining the alpha grid near `[.05, .10]` — frozen
before new results, per the outline's mechanism-by-mechanism rule — is a
reasonable next step given the trend evidence. Separately, the exploratory
`1 - p_value` score result is promising enough to be worth a dedicated
future charter for a confidence-scored edge representation — one that
would need to include a proper reliability diagram and a prevalence-
adjusted baseline before calling it calibrated — per
`docs/stage1b_charter.md`'s consequences section; this remains an
executive decision, not an automatic next step.

## D-004: Reassess higher-N-floor conditional-independence validation (Stage 1c / R2c)

Date: 2026-08-28

Stage: R2c / Stage 1c

Status: REASSESS

Decision timing: Predeclared gate evaluated after results

Question: Does raising the gate's minimum sample size from `N = 500` to
`N = 750` resolve D-003's failure, where the `strong`-family triangle FPR
cleared the gate at `N = 750`/`1000` but not `N = 500`, improving
monotonically with `N`?

Prior specification: `docs/stage1c_charter.md` froze R2b's DGP, mechanism,
seeds, and alpha grid, extending `sample_sizes` with `N = 1500, 2000` and
raising the gate floor to `N >= 750`, decided from the shape of the R2b
trend before any new evidence.

Evidence: `results/generated/stage1c_dpi/decision.json` records 324,000 raw
estimates, zero errors. Development selection chose adjacent pair `(0.005,
0.01)`, which fails validation on triangle FPR at `strong`-family cells
`N = 750, 1000`. Reading `strong`-family FPR at fixed `alpha` across the
full extended `N` range (development replicates) shows a clean, continuing
decline — `alpha = .05`: `.187` (`N=500`) to `.015` (`N=2000`); `alpha =
.10`: `.141` to `.007` — confirming the sample-size/power hypothesis
directly. The gate nonetheless failed because development selection scans
`alpha` ascending and returns the first pair whose **pooled** average across
all `N >= 750` and all strengths clears both thresholds; at `alpha =
.005`/`.01`, strong performance at the newly added `N = 1500`/`2000` cells
pulled the pooled average under the FPR threshold even though `N =
750`/`1000` alone remained above it. `(0.05, 0.10)` would have passed every
validation cell individually with real margin but was never reached, because
the ascending scan stops at the first pooled-passing pair. See
`docs/stage1c_report.md` for the full breakdown. An exploratory-score
check on `1 - p_value` (Brier score against a flat baseline, non-gating,
not a calibration claim) stayed stable and well below `.25` across the
full `N` range (`.073`-`.094`).

Decision: Reassess. Do not select a public default alpha or `N` floor, and
do not proceed to Stage 2 candidate-edge screening on this evidence.

Rationale: The charter's scientific question — is the R2b failure a
sample-size/power limitation — is answered yes, clearly, by the fixed-alpha
trend. But the formal PROCEED/REASSESS gate is decided by the frozen
development-selection rule, and that rule's pooled-average selection is
blind to per-`N` variation once a wide, heterogeneous `N` range is pooled
together — the same blind spot D-002 identified between pooled-family and
per-family evidence, now appearing between pooled-`N` and per-`N`. Per this
charter, seeing that `(0.05, 0.10)` would have passed cannot be used to
retroactively substitute it for the rule's actual selection; that would be
exactly the kind of post hoc re-selection the process forbids.

Consequences: Stage 2 and later layers remain blocked. The natural next
charter is a revision to the *development-selection rule itself* — for
example, requiring every individual `N` cell (not just the pooled average)
to clear the threshold before an alpha pair is eligible — frozen before new
results. This is a change to the evaluation methodology, not the pruning
mechanism, which the accumulated R2b/R2c evidence supports well. The
confidence-scored-edge-representation option from D-003 remains open and
unaffected by this result.

## D-005: Reassess per-cell development selection (Stage 1d / R2d)

Date: 2026-08-28

Stage: R2d / Stage 1d

Status: REASSESS

Decision timing: Predeclared gate evaluated after results

Question: Does requiring every individual `(N, strength)` development cell
to pass (not just the pooled average) find an adjacent alpha pair that R2c's
pooled rule missed?

Prior specification: `docs/stage1d_charter.md` froze a change to the
development-selection rule only — an alpha is eligible only if every
individual cell, `N >= 750`, passes both criteria. DGP, mechanism, seeds,
`N` grid, and alpha grid are unchanged from R2c; R2c's raw evidence is
reused verbatim rather than re-simulated.

Evidence: `results/generated/stage1d_dpi/decision.json` records
`"no eligible development alpha pair"`. Checking every alpha individually:
only `alpha = 0.10` is per-cell eligible, with no adjacent eligible partner.
`alpha = .05` fails only two cells (both `strong`-family, FPR `.117`/`.111`
against the `.10` gate); `alpha = .20` fails several chain/fork TPR cells,
all in the `.76`-`.80` range against the `.80` gate. With 250 development
replicates per cell, the binomial standard error is `~.025` at `.80` and
`~.019` at `.10`; every failing cell above misses its threshold by less
than one standard error. See `docs/stage1d_report.md` for the full
breakdown.

Decision: Reassess. Do not select a public default alpha, and do not
proceed to Stage 2 candidate-edge screening on this evidence.

Rationale: This is a third distinct finding, different in kind from D-002
(structural confound) and D-004 (pooling artifact). The per-cell rule,
honestly applied, finds a single isolated passing alpha surrounded by
near-misses consistent with replicate-count sampling noise rather than a
systematic gap. That points at the development replicate count (250 per
cell) being too small for a per-cell decision rule at this alpha grid's
resolution, not at a remaining flaw in the conditional-independence
mechanism, which by this point has been supported by three converging
lines of evidence (D-003's balanced/moderate pass, D-004's power trend to
near-zero FPR, and D-005's isolated-but-clean single point).

Consequences: Stage 2 and later layers remain blocked. Two legitimate next
directions, each requiring its own charter frozen before new results: (a)
more development replicates (the mechanism and grid are unchanged, so this
is a straightforward re-run at higher replicate count, not a new design),
or (b) a coarser alpha grid step that does not require resolving a boundary
this fine. Given the accumulated evidence, this looks like a matter of
statistical resolution rather than a mechanism or methodology problem. The
confidence-scored-edge-representation option from D-003 remains open and
unaffected by this result.

## D-006: Reassess higher-replicate-count per-cell selection (Stage 1e / R2e)

Date: 2026-08-28

Stage: R2e / Stage 1e

Status: REASSESS

Decision timing: Predeclared gate evaluated after results

Question: Does quadrupling development replicates (250 to 1000) resolve
D-005's near-misses at `alpha = .05` and `alpha = .20`, which were each
smaller than one standard error at 250 replicates?

Prior specification: `docs/stage1e_charter.md` froze R2d's DGP, mechanism,
`N` grid, alpha grid, and per-cell selection rule, increasing replicates
from 500 to 2000 (development 0-999, validation 1000-1999) — a statistical-
power change to the evaluation, not a new design, decided from the observed
noise magnitude in D-005.

Evidence: `results/generated/stage1e_dpi/decision.json` records 1,296,000
raw rows, zero errors, and again `"no eligible development alpha pair"`:
only `alpha = 0.10` passes every cell, with no adjacent partner. But the
extra replicates changed the picture rather than merely repeating it. At
1000 development replicates (SE `~.0095` for FPR at `.10`; `~.0126` for TPR
at `.80`): `alpha = .05`'s one remaining failing cell (`strong` family,
`N = 750`) now misses by `.128` against the `.10` gate — nearly 3 standard
errors, a real failure, not noise (it was `<1` SE at 250 replicates).
`alpha = .20`'s failing chain/fork TPR cells dropped from 12 to 8, and most
remaining misses are now well under 1 SE, consistent with convergence
toward passing, though a couple remain marginal (up to `1.26` SE). See
`docs/stage1e_report.md` for the full breakdown. An exploratory-score
check on `1 - p_value` (Brier score, not a calibration claim) remained
stable (`.074`-`.096` by `N`, pooled `.080`),
consistent with R2c/R2d.

Decision: Reassess. Do not select a public default alpha, and do not
proceed to Stage 2 candidate-edge screening on this evidence.

Rationale: More replicates sharpened the boundary rather than dissolving
it into noise, which is itself informative: `alpha = .05` is now a
confirmed real failure, while `.20`'s issues are shrinking but not fully
resolved. This is consistent with a real, narrow valid region sitting near
`alpha = .10` that the frozen grid's coarse steps (`.05` to `.10` to `.20`)
straddle without another tested point landing inside it. Per
`docs/stage1e_charter.md`'s consequences, this is now a grid-resolution
problem, not a replicate-count problem — more replicates would sharpen the
picture further but would not manufacture an adjacent passing pair where
the grid has no point to land on.

Consequences: Stage 2 and later layers remain blocked. The next charter
should add finer alpha resolution between `.05` and `.20` (e.g. `.06`
through `.19` in fine steps) rather than increasing replicates again,
frozen before new results. Given four converging rounds of evidence
(D-003's balanced/moderate pass, D-004's power trend to near-zero FPR,
D-005's isolated clean point, D-006's sharpening boundary), the mechanism
itself is well supported; what remains is locating the passing alpha
region precisely enough to select an adjacent pair. The confidence-scored-
edge-representation option from D-003 remains open and unaffected.

## D-007: Reassess fine alpha-resolution per-cell selection (Stage 1f / R2f)

Date: 2026-08-28

Stage: R2f / Stage 1f

Status: REASSESS

Decision timing: Predeclared gate evaluated after results

Question: Does a 0.01-resolution alpha grid across `[.06, .25]` contain an
adjacent pair that passes the per-cell development-and-validation gate,
where the coarse grid was too widely spaced to find one?

Prior specification: `docs/stage1f_charter.md` froze R2e's DGP, mechanism,
`N` grid, replicate count, and per-cell selection rule, narrowing the
alpha grid to 20 points at 0.01 steps spanning the region bounded by R2e's
confirmed failure at `.05` and decisive failure at `.30`.

Evidence: `results/generated/stage1f_dpi/decision.json` records 2,880,000
raw rows, zero errors. Development selection found adjacent pair `(0.09,
0.10)`, which fails validation at exactly one cell (`strong` family,
`N = 750`, `alpha = 0.09`, FPR `.104` against the `.10` gate) by `.004` —
under half a standard error at 1000 replicates (`SE ~ .0095`), the smallest
margin failure in this line of charters. Reading the same cell across
`alpha = .08`-`.11` on both development and validation data shows `alpha =
0.09` was development-eligible only by a `.008` margin (also under 1 SE)
and landed on the wrong side of the gate on independent validation data,
while `alpha = 0.10` and `0.11` both hold comfortably on both development
and validation. A pair of `(0.10, 0.11)` was never evaluated against
validation, because the frozen selection rule returns the first ascending
adjacent pair that is development-eligible, and `(0.09, 0.10)` qualified
first — the rule has no way to prefer a pair with a larger, more robust
margin over one that barely and noisily cleared the development threshold.
See `docs/stage1f_report.md` for the full breakdown.

Decision: Reassess. Do not select a public default alpha, and do not
proceed to Stage 2 candidate-edge screening on this evidence.

Rationale: This is a second, distinct selection-methodology gap, different
from D-004's pooling artifact: a "first eligible pair wins" rule offers no
protection against selecting a pair whose eligibility was itself a
coin-flip-margin call. Unlike D-002's structural confound or D-006's
grid-resolution gap, there is now strong, specific evidence (not merely a
trend) that an untested-on-validation pair in the same grid would pass.
Per this charter, that evidence cannot be used to retroactively substitute
`(0.10, 0.11)` for the rule's actual selection.

Consequences: Stage 2 and later layers remain blocked. The next charter
should revise the selection rule to prefer development-eligible pairs with
adequate margin above the threshold (not merely the first pair found) —
frozen before new results, reusing R2f's existing evidence rather than
re-simulating, exactly as R2d reused R2c's. This is the third selection-
methodology fix in this line (after D-004's pooling correction and R2d's
per-cell correction), on top of six rounds of accumulated support for the
underlying mechanism. The confidence-scored-edge-representation option
from D-003 remains open and unaffected.

## D-008: Proceed on margin-robust selection (Stage 1g / R2g)

Date: 2026-08-29

Stage: R2g / Stage 1

Status: PROCEED

Decision timing: Predeclared gate evaluated after results

Question: Does selecting the adjacent development-eligible alpha pair with
the largest worst-case margin, rather than the first eligible pair found,
yield a pair that passes validation with real margin?

Prior specification: `docs/stage1g_charter.md` froze a selection-rule
change only, reusing R2f's raw evidence verbatim: among adjacent alpha
pairs where both members individually pass every `(N, strength)` cell,
select the pair maximizing the minimum cell margin across both members,
rather than the lexicographically first such pair.

Evidence: `results/generated/stage1g_dpi/decision.json` records
`"status": "PROCEED"`, selected pair `(0.14, 0.15)`. Every validation cell
(all three triangle families, `N in [750, 1000, 1500, 2000]`, all three
strengths, both alpha values) passes individually, with a worst-case
chain/fork TPR margin of `.031` above the `.80` gate and a worst-case
triangle FPR margin of `.021` below the `.10` gate — both well outside the
`~.01` standard error at 1000 validation replicates. An exploratory-score
check on `1 - p_value` (Brier score against ground truth, not a
calibration claim) remained stable at `.074`-`.096` by `N`, pooled `.080`,
consistent with every prior
round. `(0.10, 0.11)`, flagged as a promising candidate in D-007, was not
selected; the margin-robust rule found `(0.14, 0.15)` has more worst-case
slack across the full cell grid, not just at the one cell that broke
`(0.09, 0.10)`. See `docs/stage1g_report.md` for the full breakdown.

Decision: Proceed. This closes the R2 through R2g line of Stage 1
tolerant/conditional-independence-DPI motif validation. Stage 2
candidate-edge screening may be planned.

Rationale: This is the first PROCEED in this line, reached only after
diagnosing and correcting three separate flaws — a structural confound in
magnitude-ratio DPI (D-002, resolved by switching to conditional
independence at D-003), a pooled-average selection artifact (D-004,
resolved by per-cell selection at D-005), and a "first eligible pair"
selection artifact with no margin awareness (D-007, resolved here). Seven
prior rounds of REASSESS were each a legitimate falsification of a
specific, narrow hypothesis, not repeated failures of the same claim; the
mechanism itself was never the thing that kept failing.

Consequences: The validated scope is specifically continuous Gaussian
data, `N >= 750`, three-node motifs, conditional-independence pruning via
Gaussian partial correlation, `alpha` near `0.14`-`0.15`. This does not
select a public default alpha beyond this pair and does not by itself fix
a specific Stage 2 design; Stage 2 candidate-edge screening must receive
its own frozen charter, DGP, and gate before implementation, per the
outline's mechanism-by-mechanism rule. The confidence-scored-edge-
representation option from D-003 remains open; the exploratory `1 -
p_value` score has stayed informative (consistently low Brier score
against a flat baseline) across every round from R2b through R2g, though
this is not itself a calibration finding — a reliability diagram and a
prevalence-adjusted baseline would be needed before making that claim.

## D-009: Per-N alpha table (Stage 1h / R2h)

Date: 2026-08-29

Stage: R2h / Stage 1

Status: Per-N table (no single global status — see rationale)

Decision timing: Predeclared gate evaluated after results

Question: Does each sample size have its own passing alpha region, and if
so, what is the relationship between `N` and the validated alpha?

Prior specification: `docs/stage1h_charter.md` froze an executive change
to the gate structure: select and validate an alpha pair independently per
`N`, rather than requiring one pair across a pooled `N` range. Extended
`N` to `[100, 200, 300, 500, 750, 1000, 1500, 2000, 3000]` and widened the
alpha grid to `[.0001 ... .50]` (23 points) to give smaller `N` a fair
search.

Evidence: `results/generated/stage1h_dpi/decision.json` records 3,726,000
raw rows, zero errors, and a per-`N` table:

| N | status | alpha pair | margin |
|---|---|---|---|
| 100 | REASSESS | none | — |
| 200 | REASSESS | none | — |
| 300 | REASSESS | none | — |
| 500 | REASSESS | none | — |
| 750 | PROCEED | (0.14, 0.16) | .032 |
| 1000 | PROCEED | (0.12, 0.14) | .041 |
| 1500 | PROCEED | (0.10, 0.12) | .075 |
| 2000 | PROCEED | (0.08, 0.10) | .087 |
| 3000 | PROCEED | (0.06, 0.08) | .099 |

At `N >= 750`, alpha decreases and margin increases monotonically with
`N` — a clean, usable trend. Below `750`, the worst-case TPR- and
FPR-satisfying alpha regions were checked for overlap across the full
alpha sweep: `N = 100, 200, 300` show a wide, decisive gap (raising alpha
enough to fix triangle FPR destroys chain/fork TPR long before the two
regions meet); `N = 500` shows a gap of only one grid step (`.18` passes
TPR, `.20` passes FPR), plausibly resolvable with finer resolution but
likely thin-margin even so. See `docs/stage1h_report.md` for the full
breakdown.

Decision: This charter does not produce a single PROCEED/REASSESS by
design. It produces the per-`N` evidence table above, which is the
required input to a future charter proposing a specific `alpha(N)`
default rule.

Rationale: Different sample sizes needed, and got, different treatment,
per this charter's explicit executive framing. The `N >= 750` finding
strengthens D-008 with five sample sizes now showing a clean, monotonic
`alpha`-vs-`N` shape instead of one — but this is a predeclared
**reanalysis under a new per-N selection rule, not five independent fresh
replications**: `N = 750, 1000, 1500, 2000` reuse the exact same
simulated data as R2c through R2g (identical seeds; only `N = 3000` is
genuinely new data). The value of this result is the new selection rule
and the shape it reveals, not additional independent statistical power at
those four `N` values. The `N < 750` findings are informative in their own
right, scoped to the alpha grid actually tested (`[.0001, .50]` at this
resolution): `N <= 300` shows no alpha in that grid where both criteria
hold at once — a decisive structural limit within the tested range, not a
tuning problem, though not a proof about every conceivable alpha value
outside it. `N = 500` quantitatively confirms — rather than merely
re-asserts — R2c's original choice of a `750` floor, by showing `500`
sits almost exactly on the boundary rather than comfortably on either
side of it.

Consequences: A future charter may (a) fit and freeze a specific
`alpha(N)` default rule from the `N >= 750` table (e.g., a smooth
decreasing function of `N`, validated at genuinely new, held-out `N`
values), and/or (b) check whether the `N = 500` gap closes with finer
alpha resolution, purely out of curiosity about the boundary shape —
`N <= 300` does not warrant that check within the tested grid, since its
gap is wide and decisive there. Neither is required before Stage 2
planning, which may proceed using the `N >= 750` result from D-008 and
this table's reanalysis of it. The confidence-scored-edge-representation
option from D-003 remains open; the exploratory `1 - p_value` score
stayed informative (stable Brier score against a flat baseline, not a
calibration finding) across the full `100`-`3000` range tested here.

## D-010: Locate the N=500-750 crossover (Stage 1i / R2i)

Date: 2026-08-29

Stage: R2i / Stage 1

Status: Per-N table (no single global status)

Decision timing: Predeclared gate evaluated after results

Question: `N=500` came within one grid step of passing (D-009) while
`N=750` passed comfortably (D-008); does the actual minimum viable `N`
lie somewhere in the untested gap between them?

Prior specification: `docs/stage1i_charter.md` froze fresh simulation for
`N = [550, 600, 650, 700]`, reusing R2h's `N=500, 750` rows as bookends,
under the same per-N margin-robust selection rule as R2h/R2g.

Evidence: `results/generated/stage1i_dpi/decision.json` records 2,484,000
raw rows (1,656,000 newly simulated), zero errors:

| N | status | alpha pair | margin |
|---|---|---|---|
| 500 | REASSESS | none | — |
| 550 | REASSESS | none | — |
| 600 | REASSESS | none | — |
| 650 | REASSESS | (0.14, 0.16), failed validation | .018 (dev) |
| 700 | PROCEED | (0.14, 0.16) | .012 |
| 750 | PROCEED | (0.14, 0.16) | .032 |

`N <= 600` finds no development-eligible pair at all. `N=650` is a
near-miss (development-eligible, fails validation). `N=700` is the first
sample size to PROCEED, but with a margin (`.012`) close to the `~.0095`
-`.0126` standard error established at D-006/D-009 — a real pass, not a
comfortable one. `N=750` remains the first sample size with a clearly
robust margin (`.032`, roughly `3`-`4`x the noise level). See
`docs/stage1i_report.md` for the full breakdown.

Decision: The transition is broadly monotonic (REASSESS through `600`,
near-miss at `650`, thin-margin PROCEED at `700`, comfortable PROCEED at
`750`) rather than the noisy, non-monotonic pattern that would have
warranted treating the gap as unresolved. `N=700` is a legitimate,
evidence-based floor for a thin-margin use case; `N=750` remains the floor
for a comfortable, noise-robust margin.

Rationale: The gap was real, not an artifact of the round number `750`
chosen in D-004 — but it was also narrower than it might have been: `500`
through `600` are decisively not viable, and the actual crossover sits in
a tight `650`-`700` band, not spread evenly across the whole `500`-`750`
range.

Consequences: `docs/validated_operating_ranges.md` should record both
`700` (thin margin) and `750` (comfortable margin) explicitly, rather than
collapsing to one number, so a downstream user can choose based on how
much margin they need. No further replicate or grid-resolution charter is
required to act on this finding; `N=700`'s thin margin is disclosed as
such rather than treated as fully resolved.

## D-011: Recommend N=750 as the default floor, not N=700

Date: 2026-08-29

Stage: Policy (post-Stage 1, using D-010's evidence; no new simulation)

Status: Executive decision

Decision timing: Made after seeing D-010's results, since it is an
interpretation of existing evidence, not a predeclared statistical gate

Question: D-010 showed both `N=700` and `N=750` PROCEED. Should the
project recommend one as the default floor for autonomous use?

Evidence: `N=700`'s validation margin (`.012`) is roughly `1.3` standard
errors above the pass/fail line at 1000 replicates; `N=750`'s (`.032`) is
roughly `3`-`4` standard errors. `N=650`, one step below `700`, fails.
This project has twice before (D-005, D-007) seen a margin of this size
flip sides on an independent re-check.

Decision: Recommend `N >= 750` as the default floor for autonomous DPI
edge-pruning decisions. Retain `N = 700` as a documented, available
option for a researcher who cannot collect more data and explicitly
accepts the thinner, noise-adjacent margin — not withheld, but not the
default.

Rationale: An "autonomous use" floor's value is specifically that a
researcher does not need to inspect or second-guess it case by case
(per `docs/validated_operating_ranges.md`'s stated stance). A margin of
`1.3` SE, sitting one step past a demonstrated failure at `N=650`,
partially defeats that purpose even though it technically passed its own
validation split. This is a judgment call about acceptable risk, not a
new empirical finding — the underlying D-010 evidence is unchanged and
both options remain visible.

Consequences: `docs/validated_operating_ranges.md` records this
explicitly (see "Recommended default floor" section). Any future Stage 2+
work, or production default-selection logic, should treat `750` as the
recommended floor unless a specific downstream use case has reason to
accept `700`'s thinner margin instead.

## D-012: Fit and validate an alpha(N) formula (Stage 1j / R2j)

Date: 2026-08-29

Stage: R2j / Stage 1

Status: PROCEED

Decision timing: Predeclared gate evaluated after results (fitting form
selection was also predeclared and required no results-dependent choice,
since `linear_log_n` won outright)

Question: Can a smooth `alpha(N)` formula, fit only from the six known
validated points, correctly predict a working alpha at sample sizes it
never saw?

Prior specification: `docs/stage1j_charter.md` froze four candidate
functional forms, a fitting procedure using the six D-008/D-009/D-010
points (no new simulation), and a held-out validation requirement at four
interpolated, previously-untested `N` values (`900, 1250, 1750, 2500`),
gated on the single predicted alpha clearing a `.02` margin — not merely
passing — at every held-out `N`.

Evidence: `linear_log_n` fit the six known points with `R^2 = .997`, more
than `.005` ahead of every other candidate (linear `N`: `.952`; power
law: `.987`; inverse-sqrt: `.989`) — selected outright, no tiebreak
needed. `results/generated/stage1j_dpi/decision.json` records 72,000 raw
rows, zero errors, and PROCEED at all four held-out `N`, with margins
increasing with `N` exactly as every prior charter in this line found:
`900`: `.039`; `1250`: `.069`; `1750`: `.079`; `2500`: `.097`. None are
thin-margin passes. See `docs/stage1j_report.md` for the full breakdown.

Decision: Proceed. The fitted formula `alpha(N) = 0.5222 - 0.0566 *
ln(N)` is a candidate default rule, validated by interpolation across
`N in [700, 3000]`.

Rationale: Curve-fit quality alone would not have been sufficient
evidence — a formula can fit six known points closely and still fail
between them. It did not fail here: every held-out prediction not only
passed but passed comfortably, which is the actual claim a default rule
needs to support.

Consequences: This is a candidate for a production default, not itself
one — adopting it requires a separate, later decision, consistent with
every prior "this stage does not authorize the next" boundary in this
line. The formula must not be extrapolated below `N=700` (the D-010/D-011
floor) or above `N=3000` (the edge of the tested range); both are outside
this charter's validated scope. `docs/validated_operating_ranges.md`
should record the formula alongside the existing per-`N` table as a
candidate default, not a replacement for the floor recommendation in
D-011.

## D-013: Candidate-edge screening passes in isolation (Stage 2 / R3)

Date: 2026-08-29

Stage: R3 / Stage 2

Status: PROCEED at both tested `N`

Decision timing: Predeclared gate evaluated after results

Question: Does per-pair Fisher-z screening on raw correlation correctly
separate genuinely-associated pairs from genuinely-independent ones in a
`p=15` network, at Stage 1's validated `N`, and is BH correction
necessary to do so?

Prior specification: `docs/stage2_charter.md` froze a known-ground-truth
`p=15` network (chain, fork, `moderate` triangle embedded in 6 noise
columns: 9 true candidate pairs, 96 null pairs), `N = [750, 1500]`, seven
candidate rules (uncorrected `alpha in [.001, .005, .01, .05, .10]`, BH
`q in [.05, .10]`), gated on development recall `>= .80` and FDR `<= .10`,
validated independently per `N`, with a predeclared tiebreak preferring
the simplest eligible rule.

Evidence: `results/generated/stage2_screening/decision.json` records
28,000 raw rows, zero errors, and PROCEED at both `N`, selecting
uncorrected `alpha = .001` at both (validation recall `.9999`/`1.0000`,
FDR `.0121`/`.0106`). The full operating table shows recall is
essentially `1.0` at *every* tested threshold — power was never the
constraint — while FDR scales with `alpha` in the direction the charter's
pre-registered back-of-envelope arithmetic anticipated (`alpha=.001`
predicted `~.012`, observed `.011`-`.012`) — a successful pre-specified
prediction of the FDR/alpha relationship's shape, not an independent
confirmation, since the arithmetic and the simulation share the same
96:9 null:true DGP assumption. Both BH thresholds also pass at both `N`,
but lose the tiebreak to the simpler uncorrected rule. See
`docs/stage2_report.md` for the full breakdown.

**Correction (2026-08-30, second peer review):** the FDR figures above
were originally computed as a mean of each replicate's own FDR ratio
(`.0109`/`.0094`), which does not match this charter's frozen pooled
definition ("fraction of *all* flagged pairs, across all 96+9 possible
pairs, that are actually null" — i.e. total false discoveries / total
discoveries, summed across replicates, not averaged per-replicate
ratios). `src/mintnet/experiments/stage2_reporting.py`'s `_rule_metrics`
and `aggregate_stage2` were corrected to pool by summed counts
(`src/mintnet/experiments/stage2.py`'s raw evidence now also records
`true_positives`/`false_positives`/`total_flagged` per row so this is
possible), and Stage 2's evidence was regenerated
(`results/generated/stage2_screening/`). The corrected pooled FDR is
`.0121` at `N=750` and `.0106` at `N=1500` — both still comfortably under
the `.10` gate, so this decision's PROCEED status and selected rule
(`uncorrected, alpha=.001`, at both `N`) are unchanged. The two FDR
values happened to move in opposite directions under the fix (`N=750`'s
figure rose, `N=1500`'s fell), consistent with mean-of-ratios and
pooled-counts being genuinely different statistics rather than the same
number reached two ways.

Decision: Proceed. Screening validated in isolation at `p=15`,
`N in [750, 1500]`.

Rationale: This is the first Stage 2 charter to PROCEED on its first
attempt, unlike every Stage 1 charter after R2. The charter's
pre-registered arithmetic anticipating the FDR/alpha relationship before
any simulation ran (given the 96:9 null:true imbalance) matched the
observed results closely — a successful pre-specified prediction, which
is evidence the mechanism and its evaluation are well understood, though
not independent confirmation given the shared DGP assumption noted above.

Consequences: This does not authorize composing screening with Stage 1's
validated DPI pruning into one pipeline — per the outline's Section 2.1,
that composition is its own mechanism-interaction question and needs its
own charter. It also does not authorize `p=30` or other network sizes,
which remain untested. `docs/validated_operating_ranges.md` should record
this component's validated range (`p=15`, `N in [750, 1500]`, uncorrected
`alpha=.001` sufficient, BH available but not required).

## D-014: Screening + DPI composition passes (Stage 2b / R3b)

Date: 2026-08-29

Stage: R3b / Stage 2

Status: PROCEED at both tested `N`

Decision timing: Predeclared gate evaluated after results, including a
predeclared quantitative expectation (final false-edge rate should track
screening's own rate, stated before running anything)

Question: Does composing Stage 2's validated screening with Stage 1's
validated DPI pruning, applied only within clean 3-node candidate triads,
correctly recover the true network structure end to end?

Prior specification: `docs/stage2b_charter.md` froze the pipeline
(screen at D-013's winning `alpha=.001`; group candidate edges into
connected components; apply DPI, at the D-012 formula's `alpha(N)`, only
within components that are exactly a 3-node candidate triad; pass every
other shape through unmodified), reusing Stage 2's exact `p=15` DGP and
`N in [750, 1500]` specifically so "which variable to condition on" has
an unambiguous answer.

Evidence: `results/generated/stage2b_composition/decision.json` records
4,000 raw rows, zero errors, PROCEED at both `N`:

| N | indirect TPR | true-edge FPR | screening FER | final FER | triad rate |
|---|---|---|---|---|---|
| 750 | .818 | .0053 | .00115 | .00115 | .961 |
| 1500 | .861 | .0004 | .00100 | .00100 | .963 |

`screening_false_edge_rate` and `final_false_edge_rate` are identical at
both `N`, confirming the charter's predeclared expectation exactly: DPI
essentially never rescues a screening false positive, because false
positives are almost always isolated single edges with no shared
neighbor to condition on. Indirect-edge TPR (`.818`/`.861`) is a little
below Stage 1's isolated-motif numbers at similar alpha (D-009: `~.85`-
`.87` at `N=750`), explained by the `~4%` of replicates (`triad_rate ~
.96`) where a true motif's candidate component was not a clean triad and
so skipped DPI entirely. See `docs/stage2b_report.md` for the full
breakdown.

Decision: Proceed. The composed pipeline is validated for disjoint,
non-overlapping 3-node motifs at `p=15`, `N in [750, 1500]`.

Rationale: This is the first charter to test an actual interaction
between two independently-validated mechanisms, and the result is not
just a pass but an explained one — both the "no false-edge rescue" and
the "small TPR gap" findings match predeclared or immediately traceable
mechanistic reasons, rather than being accepted as an opaque aggregate
number the way early Stage 1 charters sometimes had to be before their
underlying cause was understood.

Consequences: This does not validate general-shaped candidate graphs —
overlapping motifs, hub variables, or components larger than 3 nodes
remain a distinct, open, harder question needing its own DGP and charter
before Stage 3 (bootstrap) or a full continuous MVP can be responsibly
attempted. `docs/validated_operating_ranges.md` should record the
composed pipeline's validated range separately from screening-alone
(D-013) and DPI-alone (D-008/D-012), since composition was not guaranteed
by either mechanism's individual validation.

## D-015: Multi-variable conditioning passes on a hub motif (Stage 1k / R3c)

Date: 2026-08-29

Stage: R3c / Stage 1

Status: PROCEED at both tested `N`

Decision timing: Predeclared gate evaluated after results; a quick
non-charter simulation check was run before freezing to confirm the
design was well-posed (not treated as evidence, only as a sanity check
before committing compute)

Question: Does conditioning on every other node in a candidate component
— the direct generalization of Stage 1's one-variable partial
correlation — correctly separate direct from indirect edges when a
component has more than 3 nodes, and does the existing D-012 `alpha(N)`
formula (fit only for one-variable conditioning) still work unmodified?

Prior specification: `docs/stage1k_charter.md` froze a minimal 4-node hub
DGP (1 hub, 3 independent children), `N in [750, 1500]`, testing the
D-012 formula's predicted `alpha_hat` directly (no new grid search),
gated on indirect-edge TPR `>= .80`, true-edge FPR `<= .10`, and a `.02`
required margin on both.

Evidence: `results/generated/stage1k_hub/decision.json` records 4,000 raw
rows, zero errors, PROCEED at both `N`: `750` (TPR `.854`, FPR `0`,
margin `.054`); `1500` (TPR `.887`, FPR `0`, margin `.087`). Both clear
the required margin comfortably, not as thin-margin passes. A
pre-charter sanity simulation predicted `TPR ~ .858`/`.882`, `FPR = 0` —
the actual results landed almost exactly there. See
`docs/stage1k_report.md` for the full breakdown.

Decision: Proceed. Multi-variable conditioning, using the unmodified
D-012 formula, is validated for this 4-node hub shape at `N in [750,
1500]`.

Rationale: This is a genuinely informative, non-obvious result: a formula
fit only against one-variable-conditioning evidence did not need
refitting to also work for two-variable conditioning. That the actual
outcome matched a quick pre-registered simulation almost exactly is
further evidence the mechanism is understood, not merely lucky —
consistent with D-013's similar experience.

Consequences: This validates the multi-variable conditioning mechanism
only for the hub shape tested (one shared cause, several independent
children) — not for components formed by two motifs sharing a node, or
larger components generally, which remain open questions for a future
charter. Combined with D-014, the pieces needed to extend Stage 2b's
composed pipeline beyond exact 3-node triads to hub-shaped candidate
components now exist, though wiring that extension into the actual
pipeline (`mintnet.pipeline.compose`) has not itself been done or
chartered yet.

## D-016: Wired hub conditioning into the pipeline; mixed-shape composition passes (R3d)

Date: 2026-08-29

Stage: R3d / Stage 2

Status: PROCEED at both tested `N`

Decision timing: Predeclared gate evaluated after results; a pre-charter
simulation check (1500 replicates) was run before freezing to catch a
misleading noisy estimate from an even smaller initial check, not treated
as evidence itself

Question: Does the composed pipeline correctly handle a single network
containing both a 3-node triad shape and a 4-node hub-clique shape at
once, using one general conditioning rule for both?

Two things happened here, in order:

1. **Code generalization.** `mintnet.pipeline.compose` was rewritten to
   replace its triad-only special case with one general rule: apply
   multi-variable conditioning within any candidate component that is a
   validated clique shape (size 3, from D-008 through D-012, or size 4,
   from D-015); pass through every other shape unmodified. This was
   justified by proving the general multi-variable mechanism
   (`mintnet.dpi.multi_conditional`) is numerically identical to Stage
   1's original one-variable closed-form when there is exactly one
   conditioning variable (see `tests/unit/test_multi_conditional.py`),
   and verified safe by re-running D-014's exact original configuration
   through the new code and confirming byte-for-byte identical
   `decision.json` output before proceeding.
2. **New evidence.** `docs/stage2c_charter.md` froze a `p=15` network
   combining Stage 2b's chain/fork motifs with Stage 1k's hub motif in a
   single network (replacing the triangle from D-014), `N in [750,
   1500]`, same screening/DPI alphas as D-014.

Evidence: `results/generated/stage2c_composition/decision.json` records
4,000 raw rows, zero errors, PROCEED at both `N`:

| N | indirect TPR | true-edge FPR | screening FER | final FER | shape-validated rate |
|---|---|---|---|---|---|
| 750 | .820 | .000 | .00101 | .00101 | .965 |
| 1500 | .853 | .000 | .00120 | .00120 | .958 |

Every prior finding replicated: screening and final false-edge rates are
identical at `N=1500` (`.0012043` both) and nearly identical at `N=750`
(screening `.00101075` vs. final `.00100000` — the displayed 5-figure
table above rounds this to the same `.00101` at both, masking a real but
tiny difference; corrected 2026-08-30, second peer review) — D-014's "no
rescue" finding, essentially confirmed alongside hub components too;
true-edge retention is perfect; the `~.96` shape-validated rate matches
D-014's triad-only rate closely. The `N=750` indirect TPR (`.820`)
landed almost exactly on a pre-charter 1500-replicate simulation's
prediction (`.823 +/- .005`) — a successful pre-specified prediction,
not independent evidence against an unpredicted interaction, since the
pre-charter check shares the same DGP and code assumptions as the frozen
run. See `docs/stage2c_report.md` for the full breakdown.

Decision: Proceed. The generalized pipeline is validated for networks
mixing 3-node triad and 4-node hub-clique candidate components, at
`p=15`, `N in [750, 1500]`.

Rationale: This closes the loop opened at D-015's consequences: the hub
mechanism is now not just validated in isolation but actually wired into,
and confirmed working within, the composed pipeline — and confirmed not
to interact badly with the triad mechanism it now runs alongside.

Consequences: `docs/validated_operating_ranges.md` should record the
generalized composed pipeline's validated range, noting it now covers
mixed 3-node/4-node candidate components, not just uniform triads.
Non-clique components, cliques of any other size, larger networks, and
components sharing variables across motifs remain untested and out of
scope.

## D-017: Multi-variable conditioning generalizes to shared-node overlap (R3e)

Date: 2026-08-29

Stage: R3e / Stage 1

Status: PROCEED at both tested `N`

Decision timing: Predeclared gate evaluated after results; a pre-charter
power calculation (not simulation this time, closed-form) flagged that
screening's detection of the weak cross-branch correlation is unreliable
at `N=750` (`~66%` power) vs. `N=1500` (`~98%`) — this was used to scope
the charter to the conditioning mechanism in isolation, not to predict
its outcome

Question: Does "condition on all other nodes in the candidate component"
generalize to a topology genuinely different from Stage 1k's hub/star —
two triangles overlapping at a single shared node — using the existing
D-012 `alpha(N)` formula unmodified?

Prior specification: `docs/stage1l_charter.md` froze a 5-variable DGP
(two `balanced`-style triangles sharing node 2), `N in [750, 1500]`,
testing the D-012 formula's predicted `alpha_hat` directly against a
clean, hand-fed 5-node component (bypassing whether screening would
actually detect it that cleanly — explicitly out of scope, deferred to a
future wiring charter mirroring Stage 1k -> Stage 2c).

Evidence: `results/generated/stage1l_overlap/decision.json` records 4,000
raw rows, zero errors, PROCEED at both `N`: `750` (TPR `.858`, FPR `0`,
margin `.058`); `1500` (TPR `.894`, FPR `0`, margin `.094`). Both clear
the required margin comfortably. A pre-charter 1000-replicate simulation
predicted `TPR ~ .847`/`.884` — close to the actual result. See
`docs/stage1l_report.md` for the full breakdown.

Decision: Proceed. Multi-variable conditioning generalizes to shared-node
overlap topology, at `N in [750, 1500]`, using the unmodified D-012
formula.

Rationale: This is now the second distinct topology (after the hub) where
the same general rule and the same formula work without modification,
strengthening the case that the conditioning mechanism itself is broadly
general rather than validated only for star-shaped structures.

Consequences: This does **not** extend `VALIDATED_CLIQUE_SIZES` or wire
anything into `mintnet.pipeline.compose` — unlike the hub case, this
DGP's cross-branch signal is weak enough that screening frequently will
not produce a clean 5-node candidate clique at `N=750` (the pre-charter
power calculation), so a wiring charter here would need to separately
characterize how often a clean shape actually forms, not just assume it
does because the mechanism works when handed one. That remains a distinct
future charter. `docs/validated_operating_ranges.md` should record this
mechanism-level result separately from any pipeline-wiring claim.

## D-018: Overlap wiring matches the pre-specified screening-power split prediction (R3f)

Date: 2026-08-29

Stage: R3f / Stage 2

Status: REASSESS at `N=750`, PROCEED at `N=1500` (matches the pre-specified split prediction)

Decision timing: Predeclared gate evaluated after results; the specific
split outcome was predicted, in writing, by a pre-charter simulation
before any frozen results existed — this is a successful pre-specified
prediction, not independent confirmation, since the pre-charter
simulation and the frozen run share the same DGP and code assumptions
(second peer review, 2026-08-30; see the correction note below)

Question: Does the shared-node-overlap motif, embedded in a network and
run through the full screen-then-prune pipeline (with
`VALIDATED_CLIQUE_SIZES` extended to include 5, per D-017), behave the
way its screening-power limitation predicted?

Prior specification: `docs/stage2d_charter.md` froze a `p=15` network
(chain, fork, the overlap motif, 4 noise columns), extended
`VALIDATED_CLIQUE_SIZES` to `{3, 4, 5}`, and gated **per motif**
(chain/fork/overlap TPR each individually `>= .80`, not pooled — a
deliberate design choice to avoid the D-004 pooling blind spot). It
explicitly predicted, before results: `N=750` overlap TPR `~.59`,
clean-clique rate `~26%` (REASSESS); `N=1500` overlap TPR `~.82`,
clean-clique rate `~89%` (PROCEED).

Evidence: `results/generated/stage2d_composition/decision.json` records
4,000 raw rows, zero errors. Observed: `N=750` overlap TPR `.569`
(predicted `.59`), clean-clique rate `.287` (predicted `.26`) — REASSESS.
`N=1500` overlap TPR `.817` (predicted `.82`), clean-clique rate `.921`
(predicted `.89`) — PROCEED. Chain and fork TPR (`.815`-`.868` across
both `N`) behaved normally at both `N`, matching every prior charter. A
pooled average at `N=750` (`(.816+.815+.569)/3 = .733`) would also have
failed, but by a smaller, less diagnostic margin than the per-motif
breakdown gave. See `docs/stage2d_report.md` for the full breakdown.

Decision: The observed split matches the pre-specified prediction.
Extending `VALIDATED_CLIQUE_SIZES` to include size 5 is safe and correct
when the mechanism gets a chance to run (consistent with D-017), but for
this DGP's weak cross-branch signal, screening reliably provides that
chance only from `N=1500`, not `N=750`, despite `N=750` already being
comfortably above the DPI mechanism's own established floor (D-010/D-011).

Rationale: This is a genuinely new, narrower bottleneck, distinct from
every `N`-floor question characterized so far: it is a property of
*screening's* detection power for a specific weak-signal DGP shape, not
of the DPI conditioning mechanism (which D-017 already showed works
correctly whenever it runs) or of the general `N >= 700`-`750` floor
(D-010/D-011, which concerns DPI's own power, not screening's). That the
outcome matched pre-charter arithmetic closely is a successful
pre-specified prediction and evidence the bottleneck's *mechanism* was
understood well enough to anticipate its numeric size correctly — but
not independent confirmation, since the pre-charter check and the frozen
run share the same DGP and code assumptions rather than being derived
two separate ways (correction, second peer review, 2026-08-30).

Consequences: Trusting a validated clique size for a given DGP shape
should not be assumed safe at every `N` where the DPI mechanism itself is
validated — screening's detection power for that specific shape's signal
strength must be separately checked, as this charter did. This is not a
general statement that `VALIDATED_CLIQUE_SIZES = {3,4,5}` is unsafe (the
hub shape, D-016, worked fine at both tested `N`); it is specific to
weak-signal shapes like this one. `docs/validated_operating_ranges.md`
should record this as a distinct, DGP-dependent caveat rather than folding
it into the general `N`-floor entries.

## D-019: Bootstrap edge stability separates true from false edges; a known pruning failure shows partial, not complete, stability (R4)

Date: 2026-08-30

Stage: R4 / Stage 3

Status: PROCEED at both `N = 750` and `N = 1500` (primary DGP);
secondary DGP is diagnostic only, no PROCEED/REASSESS status

Decision timing: Predeclared gate evaluated after results, per
`docs/stage3_charter.md`

Question: Does bootstrap resampling of the composed screen-then-prune
pipeline produce a final-edge stability statistic (`pi_final`) that
meaningfully separates true edges from false ones under a calibrated
threshold — and does the outline's Section 17.5 predicted failure mode
("high bootstrap stability can occur for wrong edges") actually occur?

Prior specification: `docs/stage3_charter.md` froze a two-DGP design.
**Primary (gated)**: Stage 2b's disjoint chain/fork/triangle network
(already PROCEED at both `N`, D-014), `N = [750, 1500]`, 500-bootstrap
row resampling, 30 development + 30 validation outer replicates per
`N`. Per `N`, select the smallest `pi_min in {.70, .80, .90}` meeting,
on development, stability recall `>= .90`, pooled stability FDR
`<= .10`, and a stability-filtered final false-edge rate within `.01`
of the point-estimate baseline; the selected `pi_min` must meet the
same three criteria again on validation to PROCEED. **Secondary
(diagnostic only)**: Stage 2d's shared-node-overlap network at
`N = 750` — the specific condition D-018 found REASSESS on (overlap
indirect-edge pruning TPR `~.59`) — 30 replicates, no gate, reported
descriptively to answer Section 17.5 directly.

Evidence: `results/generated/stage3_bootstrap/decision.json`, 15,750
raw per-pair rows (12,600 primary + 3,150 secondary), zero errors,
runtime 333s. **Primary**: at both `N`, every candidate `pi_min`
(`.70`/`.80`/`.90`) was eligible on development; the smallest,
`pi_min = .70`, was selected and PROCEEDed on validation — `N=750`:
recall `.9952`, FDR `0`, stability-filtered final false-edge rate `0`
vs. baseline `.00069`; `N=1500`: recall `1.0`, FDR `0`, same `0` vs.
`.00069` comparison. **Secondary** (descriptive, `N=750`): mean
`pi_final` by category — `true_direct` `.99999`, `indirect_chain`
`.6338`, `indirect_fork` `.6345`, `indirect_overlap` `.5295`
(median `.545`), `null` `.0210`. See `docs/stage3_report.md`,
`stability_by_category.png`, and `secondary_overlap_diagnostic.png`.

Decision: **PROCEED for the primary DGP at both `N`.** Final-edge
bootstrap stability separates true direct edges (`pi_final ~1.0`) from
null pairs (`pi_final ~0.02`) almost completely, and the least
conservative eligible threshold (`pi_min = .70`) recovers essentially
every true edge while adding no measurable false-edge cost beyond the
point estimate's own baseline. **The secondary DGP's descriptive result
answers Section 17.5 directly, but only partially in the direction the
outline flagged as a risk**: D-018's known-mispruned `indirect_overlap`
edges do show elevated stability relative to null pairs (`.53` vs.
`.02`, roughly 25x) — confirming that a wrongly-retained edge is not
automatically unstable — but their stability is well below true edges'
(`.53` vs. `~1.0`) and even below the network's correctly-pruned chain
and fork indirect edges (`~.63`).

**Correction (2026-08-30, while chartering the follow-up):** the
preceding paragraph's `pi_min = .70` remark was based on the *pooled*
mean across both correctly-pruned and wrongly-retained instances of the
overlap-indirect edge type, which mixes two different populations and
is not the right statistic for a filter that only ever acts on edges
the point estimate already kept. Split by the point estimate's own
decision, the wrongly-retained instances are *more* stable (mean
`.737`, median `.745`, `n=60`) than the correctly-pruned ones (mean
`.322`, `n=60`) — so a `pi_min = .70` filter would remove only `40%` of
them, not "most." See `docs/stage3b_charter.md` for the corrected
conditional analysis and the higher threshold range (`pi_min in {.80,
.90, .95, .98}`) it motivates instead.

Rationale: The primary result is the charter's central question,
answered cleanly: bootstrap stability is not statistical noise here,
it is a genuinely separating statistic, at least for a composed
pipeline already known to work well (D-014). The secondary result is
more nuanced than the outline's Section 17.5 framing implies "high
stability for wrong edges" as a binary risk — here, wrongness produces
*intermediate*, not *high*, stability, still clearly distinguishable
from both extremes with enough resolution to matter. This is exactly
why Section 17.5 asks for this test explicitly rather than assuming
bootstrap either always helps or never does: the answer is graded, not
binary, and depends on how weak the underlying signal driving the
mispruning is (D-018 already established the overlap DGP's cross-branch
correlation is weak, `~.135`).

Consequences: Bootstrap edge stability is validated as a meaningfully
separating statistic for `p=15`, `N in [750, 1500]`, on a disjoint-triad
composed pipeline, at `B=500` row bootstraps — not validated for hub or
overlap-containing networks' own gate criteria, other resampling
schemes, or other `B` values. The secondary finding — that
wrongly-retained overlap edges are stability-separable from true edges,
at a materially higher threshold than the primary DGP's own `pi_min`
(see the 2026-08-30 correction above) — is a promising lead for a
future charter (does stability filtering, properly gated on the overlap
DGP itself, measurably improve topology quality there, per Section
17.6's second bullet?), not a claim that it already does; this is now
`docs/stage3b_charter.md`. Per this charter's explicit non-goals
section, `pi_final` must continue to be reported as a
resampling-reproducibility statistic, never as a p-value or confidence
level, in any report built on this evidence.

## D-020: Bootstrap stability filtering rescues the overlap DGP's N=750 failure (R4b)

Date: 2026-08-30

Stage: R4b / Stage 3

Status: PROCEED at both `N = 750` and `N = 1500`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage3b_charter.md`

Question: Does a post-hoc bootstrap-stability filter (drop an edge from
the final graph if `pi_final < pi_min`, calibrated on the overlap DGP
itself) clear D-018's `.80` overlap indirect-edge TPR gate at `N=750`,
without wrongly removing true direct edges or regressing `N=1500`?

Prior specification: `docs/stage3b_charter.md` corrected D-019's pooled
`pi_final` framing (wrongly-retained overlap edges are, split by the
point estimate's own decision, *more* stable — mean `.737` — than the
pooled `.53` figure suggested) and predicted PROCEED at `N=750` with a
selected `pi_min` somewhere in `{.90, .95, .98}`. Candidate grid: `{.80,
.90, .95, .98}`. Gate per `N`: overlap indirect TPR `>= .80`, true-edge
FPR `<= .10`, chain/fork indirect TPR no worse than baseline
(safe-by-construction), final false-edge rate within `.01` of baseline
(also safe-by-construction) — select smallest eligible `pi_min` on
development (0-29), confirm on validation (30-59).

Evidence: `results/generated/stage3b_stability_filter/decision.json`,
12,600 raw rows, zero errors, runtime 689s. **`N=750`**: baseline
(unfiltered) overlap TPR `.633` (development) / `.558` (validation) —
below the `.80` gate, replicating D-018's failure on fresh evidence.
Every candidate `pi_min` was eligible on development; the smallest,
`pi_min=.80`, was selected and cleared validation: overlap TPR
`.867`, true-edge FPR `0`, chain TPR `.867`, fork TPR `.933`, final
false-edge rate `0`. **`N=1500`**: baseline overlap TPR `.692`
(development) / `.808` (validation) — the development-partition dip
below `.80` is 60-replicate sampling noise (D-018's original,
2000-replicate estimate was `.817`; this run's own validation partition
recovers `.808`, consistent with D-018), not a new finding that `N=1500`
newly fails without filtering. `pi_min=.80` selected and validated:
overlap TPR `.883`, true-edge FPR `0`. See `docs/stage3b_report.md`,
`overlap_tpr_vs_pi_min.png`, `before_after_filtering.png`.

Decision: **Stability filtering rescues `N=750`.** The smallest
candidate threshold, `pi_min=.80`, was sufficient — lower than the
`{.90, .95, .98}` range the pre-charter conditional analysis predicted,
meaning the true separation between wrongly-retained overlap edges and
true edges is *cleaner* at full statistical resolution (60 replicates,
formally gated) than the 30-replicate exploratory slice suggested. True
direct edges were never wrongly removed at any tested `pi_min`, at
either `N` — true-edge FPR was exactly `0` throughout, matching the
pre-charter check's `0%`-cost observation exactly, now on independent,
gated evidence.

Rationale: This is the first charter in this project to demonstrate a
genuine *repair* of a previously identified failure mode without
collecting more data, not merely a validation or invalidation of an
existing mechanism (contrast with every prior R-series charter). The
repair works because the two conditions this DGP creates are
distinguishable in a way pure point estimation cannot see but resampling
can: an edge the point estimate barely, contingently kept (because this
replicate's specific draw happened to push a weak `~.135` correlation's
p-value under `alpha` for 4 simultaneous cross-branch pairs) tends to
*not* survive most of that same replicate's own bootstrap resamples as
reliably as a genuinely strong edge does — even though, per the D-019
correction, it survives more resamples than a purely null edge would.
The gap between "survives most resamples" (true edges, `~1.0`) and
"survives about three-quarters" (wrongly-kept overlap edges, mean
`.737`) turned out to be wide enough for a `pi_min=.80` cut to fall
cleanly between them on real gated evidence, even though the
exploratory pre-check's own numbers suggested needing to go higher.

Consequences: Bootstrap stability filtering, calibrated at `pi_min=.80`
via `B=500` row bootstraps, is validated as a rescue mechanism
specifically for the shared-node-overlap DGP (`p=15`, `N in [750,
1500]`, `~.135` cross-branch correlation). This does **not** validate:
stability filtering for other under-powered shapes, weaker or stronger
signals, other `B` values, or a `pi_min` outside `{.80, .90, .95, .98}`
— a finer grid below `.80` was never tested, so whether an even lower,
cheaper-to-satisfy threshold would also work is unknown. It does **not**
authorize adding a stability-filter stage to `mintnet.pipeline.compose`
as a production default — that is a separate architecture decision, and
the `B=500` bootstrap cost (roughly 500x the base pipeline's per-dataset
cost) is a real, unresolved practical concern for that future decision,
not resolved by this charter's PROCEED. `docs/validated_operating_ranges.md`
should record this as a distinct rescue-mechanism entry, not folded into
the existing overlap-DGP caveat (D-017/D-018), since it changes what is
achievable at `N=750` for this shape when filtering is applied, without
changing the underlying `N=750` screening-power limitation itself.

## D-021: Bootstrap stability's general selection gate transfers to the hub network (R4c)

Date: 2026-08-30

Stage: R4c / Stage 3

Status: PROCEED at both `N = 750` and `N = 1500`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage3c_charter.md`

Question: Does Stage 3's general bootstrap-stability separation/
selection gate (recall `>= .90`, pooled FDR `<= .10`, no false-edge
regression, `pi_min in {.70, .80, .90}`) transfer, unmodified, to a
structurally different composed-pipeline DGP — the chain/fork/hub
network (D-016) — or was Stage 3's PROCEED specific to the
disjoint-triad shape it was tested on?

Prior specification: `docs/stage3c_charter.md` re-ran Stage 3's exact
primary-DGP procedure on Stage 2c's DGP instead of Stage 2b's, with no
new criteria or grid — explicitly *not* chasing a known failure (unlike
Stage 3b), since D-016 already PROCEEDs cleanly at the point estimate
(`.820`-`.853` indirect TPR, `.000` true-edge FPR at both `N`). The
predeclared expectation was a clean PROCEED, stated as something to
confirm rather than assume.

Evidence: `results/generated/stage3c_hub_stability/decision.json`,
12,600 raw rows, zero errors, runtime 758s. Every candidate `pi_min`
was eligible on development at both `N`; the smallest, `pi_min=.70`,
was selected and PROCEEDed on validation at both — `N=750`: recall
`1.0`, FDR `0`, final false-edge rate `0` vs. baseline `0`; `N=1500`:
recall `1.0`, FDR `0`, final false-edge rate `0` vs. baseline `.0007`.
Development-stage FDR at `N=750` for the two lower thresholds
(`pi_min=.70`: `.0073`; `pi_min=.80`: `.0041`) was nonzero but still
comfortably under the `.10` gate — the only nonzero FDR values recorded
across this charter's entire evidence, and still an order of magnitude
below the bar. See `docs/stage3c_report.md`,
`stability_by_category.png`.

Decision: **The general stability-selection gate transfers cleanly to
the hub shape**, exactly as predicted, at the same `pi_min=.70` that
was selected on the disjoint-triad DGP in Stage 3. No new threshold
range, no rescue needed, no surprises — this is a confirmation, not a
repair (contrast with D-020).

Rationale: Unlike the overlap DGP (D-018's known weak-signal failure,
which needed Stage 3b's higher, DGP-specific `pi_min` range), the hub
shape's signal is strong enough at the point estimate that bootstrap
resampling reproduces the same clean separation Stage 3 found on the
disjoint-triad DGP, with no adjustment. This is the useful negative
result the charter set out to get: confirmation that Stage 3's original
finding was not an artifact of the specific disjoint-triad shape it
happened to be tested on, without having to assume that from a single
data point.

Consequences: Bootstrap edge stability's general recall/FDR/
no-regression gate is now validated on two structurally different
composed-pipeline DGPs (disjoint-triad, D-019; hub, D-021) at `p=15`,
`N in [750, 1500]`, `B=500`, both selecting `pi_min=.70`. It remains
**not** validated as this kind of general gate on the shared-node-
overlap DGP (Stage 3b addressed that DGP only through a narrower,
filtering-specific lens with a different threshold range) — whether the
general gate itself, run unmodified on the overlap DGP the way this
charter ran it on the hub DGP, would also transfer or would instead
reproduce D-019's more nuanced intermediate-stability finding remains
an open, untested question. `docs/validated_operating_ranges.md` should
extend the Stage 3 bootstrap-stability row to note the hub-shape
confirmation, rather than adding a new row, since the validated range
and selected `pi_min` are unchanged from Stage 3 — only the tested shape
is new.

## D-022: General stability gate transfers to the overlap DGP too, but says nothing about D-018 (R4d)

Date: 2026-08-30

Stage: R4d / Stage 3

Status: PROCEED at both `N = 750` and `N = 1500` — **not a reassessment
of D-018, which remains REASSESS at `N=750` for indirect-edge pruning**

Decision timing: Predeclared gate evaluated after results, per
`docs/stage3d_charter.md`

Question: Does Stage 3's general stability-selection gate transfer,
unmodified, to the shared-node-overlap DGP — the one DGP D-021 flagged
as untested for this specific gate (Stage 3b only ever tested a
different, filtering-specific gate on it)?

Prior specification: `docs/stage3d_charter.md` predicted PROCEED at
both `N`, *including* `N=750` despite D-018's REASSESS there, stated in
advance and for a structural reason: the gate's three criteria (recall
over `true_direct`, pooled FDR over `null`, no-regression on the
`null`-only final false-edge rate) never reference the indirect-edge
category where D-018's failure lives, so they cannot detect it
regardless of `N`. The charter required descriptive (non-gated)
reporting of the indirect categories alongside the gate, specifically
so a PROCEED here could not later be misread as contradicting D-018.

Evidence: `results/generated/stage3d_overlap_general_gate/decision.json`,
12,600 raw rows, zero errors, runtime 551s. Every candidate `pi_min`
was eligible on development at both `N`; the smallest, `pi_min=.70`,
selected and PROCEEDed on validation at both (matching D-019's and
D-021's selection on the other two DGPs) — `N=750`: recall `1.0`, FDR
`0`; `N=1500`: recall `1.0`, FDR `0`. **Indirect-edge categories,
reported descriptively and not part of the gate**: at `N=750`,
`indirect_overlap` mean `pi_final` `.505` (median `.535`), with only
`23%` of instances surviving even this charter's own selected
`pi_min=.70` threshold — the gate's PROCEED and the indirect category's
messy, still-partly-wrong behavior coexist in the same evidence, exactly
as predicted. See `docs/stage3d_report.md`, `stability_by_category.png`.

Decision: The general gate transfers to a third DGP shape, confirming
the prediction. **This does not reassess, resolve, or otherwise touch
D-018's finding.** The `.505` mean `indirect_overlap` stability here is
consistent with, though not identical to, D-019's earlier `.53` pooled
figure on the same category (small differences expected: 60 replicates
here vs. 30 there, different replicate draws) — both readings describe
the same known-messy category, from two separate charters that happened
to look at it from different angles (general-gate context here;
rescue-filter calibration in Stage 3b).

Rationale: This result is exactly as informative as a predicted,
structural result can be — it closes the specific gap D-021 named
without producing any new surprise, because the charter correctly
anticipated that this gate's blindness to indirect edges, not the
overlap DGP's own weak signal, would determine the outcome. The
substantive content of this charter is not the PROCEED itself but the
explicit demonstration, in one piece of evidence, that a general
stability gate passing is not a substitute for a mechanism-specific
accuracy check — the same distinction Stage 3b's targeted, DGP-specific
filtering gate exists to make.

Consequences: Stage 3's general recall/FDR/no-regression gate is now
confirmed on all three composed-pipeline DGPs studied so far (disjoint-
triad D-019, hub D-021, overlap D-022), always selecting `pi_min=.70`,
at `p=15`, `N in [750, 1500]`, `B=500`. Any future summary of this
project's validated ranges must keep this gate's PROCEED status and
D-018's indirect-edge REASSESS status recorded as answers to different
questions about the same DGP, never merged into one line that could
read as inconsistent. No further charter is needed to establish that
this general gate "works" on the overlap DGP — that question is now
closed on all three tested shapes.

## D-023: Screening scales to p=30, with a comfortable margin once the grid was extended low enough (R3g)

Date: 2026-08-30

Stage: R3g / Stage 2

Status: PROCEED at both `N = 750` and `N = 1500`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage2e_charter.md`

Question: Does Stage 2's per-pair screening mechanism and rule-
selection framework, completely unmodified, still work at `p=30` (9
true pairs, 426 null pairs — a `~4.4x` worse true:null ratio than
Stage 2's `p=15`)?

Prior specification: `docs/stage2e_charter.md` predeclared an FDR-vs-
`alpha` table from D-013's own recall findings, before running
anything, and extended the candidate grid below Stage 2's own lower
bound (`.0001`, `.0005`, alongside Stage 2's original `.001`-`.10`) for
the same "give the uncorrected rule a fair chance" reasoning Stage 2's
own charter used to set its bound.

Evidence: `results/generated/stage2e_screening_p30/decision.json`,
36,000 raw rows, zero errors, runtime 154s. **The predeclared table was
almost exactly right** — predicted vs. observed FDR: `alpha=.0001`
`.005` vs. `.0056`/`.0056`; `.0005` `.023` vs. `.0248`/`.0247`; `.001`
`.045` vs. `.0487`/`.0446`; `.005` `.191` vs. `.194`/`.188`; `.01`
`.321` vs. `.322`/`.320` (`N=750`/`N=1500`) — every value within `.005`
of prediction, and the predicted pass/fail boundary (pass at `<=.001`,
fail at `>=.005`) landed exactly where predicted. Selected rule at both
`N`: **uncorrected `alpha=.0001`** (validation recall `.999`/`1.0`, FDR
`.0068`/`.0048`). BH also passed at `q=.05` (`FDR .059`/`.054`) but
**BH `q=.10` narrowly failed its own nominal level** (`FDR .113`/
`.106`, both just over `.10`) — a secondary, unpredicted finding: BH's
FDR control is asymptotic/average-case, not a per-realization guarantee,
and `q=.10` ran slightly hot here. See `docs/stage2e_report.md`,
`screening_operating_curve.png`.

**Correction to this charter's own prediction, made immediately rather
than left standing:** the charter's Consequences section anticipated
`alpha=.001` (FDR `~.045`) would be the selected rule, since it was the
smallest value from Stage 2's *original* grid predicted to pass. But
the charter's own predeclared table already showed `.0001` and `.0005`
passing even more comfortably (`.005`, `.023`) — and Stage 2's frozen
tiebreak rule selects the *smallest* eligible uncorrected `alpha`, not
the smallest from the old grid specifically. Applied consistently, the
charter's own table implied `.0001` would win the tiebreak, not `.001`
— the observed result is not a surprise given the table, only a
prediction I stated imprecisely when writing the Consequences section
before checking it against the tiebreak rule.

Decision: Proceed. Screening's mechanism and rule-selection framework
are validated at `p=30`, `N in [750, 1500]`, with the same 9 true
signals as Stage 2's `p=15` test.

Rationale: **This also corrects the charter's practical takeaway, not
just its selected-rule prediction.** The Consequences section argued
that `p=30`'s thinner margin (at a grid capped at Stage 2's original
`.001` floor) would make BH "more valuable, not merely available" going
forward. The actual result undercuts that framing: once the uncorrected
grid was extended low enough (exactly the "fair chance" principle the
charter itself invoked), the selected rule's margin (`.0068`/`.0048`)
is *comparable to or better than* Stage 2's own `p=15` margin
(`.011`/`.012`), achieved with the same simple uncorrected mechanism,
no correction procedure needed. The real lesson is narrower and more
precise than originally framed: **the multiple-testing burden from
added noise variables is fully compensated by extending the uncorrected
alpha grid downward** for this specific true-signal count and effect
size — BH is not thereby more necessary, it is simply one of several
methods that happen to work here, and in fact BH's own nominal level
ran slightly hot at `q=.10`, which the uncorrected rule did not.

Consequences: Screening is validated at `p=30`, `N in [750, 1500]`,
uncorrected `alpha=.0001` sufficient (BH available at `q=.05` but not
required, and `q=.10` should not be trusted at this true:null ratio
without further checking, given its narrow miss here). This does not
authorize composing screening with DPI pruning at `p=30` (its own
composition question, per Section 2.1, and a natural next charter), nor
`p` values beyond `30`, nor different true-signal counts or true:null
ratios. `docs/validated_operating_ranges.md` should record this as a
new row, explicitly correcting the "BH becomes more valuable as `p`
grows" intuition this charter's own drafting initially reached for, in
favor of the narrower, evidence-backed statement above.

## D-024: Composed pipeline scales to p=30, exactly as predicted (R3h)

Date: 2026-08-30

Stage: R3h / Stage 2

Status: PROCEED at both `N = 750` and `N = 1500`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage2f_charter.md`

Question: Does the composed screen-then-prune pipeline (screening's
D-023 `p=30` rule, unmodified DPI) behave the way it did at `p=15`
(D-014) when wired into one pipeline at `p=30`?

Prior specification: `docs/stage2f_charter.md` predicted, from D-023's
own per-edge FPR finding (`.00012` at `alpha=.0001`, essentially exactly
`alpha` itself) and D-014's "DPI cannot rescue an isolated false
positive" finding: final false-edge rate `~.0001`, true-edge FPR `~0`,
indirect TPR similar to D-014's `~.80`-`.82`, and PROCEED at both `N`.

Evidence: `results/generated/stage2f_composition_p30/decision.json`,
4,000 raw rows, zero errors, runtime 173s. **Every prediction landed
close to its predicted value**: final false-edge rate `.000146`/
`.000101` (`N=750`/`N=1500`, vs. predicted `~.00012`), identical to the
screening-alone rate at both `N` — D-014's "no rescue" finding
replicated exactly, now at `p=30`; true-edge FPR `.0054`/`.0004` (small,
consistent with `~0`); indirect TPR `.838`/`.891` (comfortably above
the `.80` gate, similar order to D-014's `.82`/`.87`, if a little
higher); triad-formation rate `.983`/`.994`, slightly *higher* than
D-014's `~.96` — plausibly because the much stricter `p=30` screening
`alpha` (`.0001` vs. `.001`) makes it marginally less likely for a true
motif's candidate component to pick up an extra spurious neighbor edge
from a nearby noise correlation, though this charter did not set out to
test that specific mechanism and treats it as a descriptive observation,
not a new finding to build on. See `docs/stage2f_report.md`,
`false_edge_rate_comparison.png`.

Decision: Proceed. The composed pipeline is validated at `p=30` for
disjoint 3-node motifs, using D-023's `p=30` screening threshold and
D-012's unchanged DPI formula.

Rationale: Unlike D-023 (which needed a correction to its own selected-
rule and practical-takeaway predictions), this charter's predeclared
expectations held without needing correction — the composition
mechanism itself was already known to work (D-014), and this charter
only needed to confirm that wiring D-023's specific `p=30` threshold
into that already-validated mechanism didn't introduce a new
interaction. It didn't. This is the cleanest kind of confirmatory
result this project produces: a prediction stated in enough numeric
detail to be falsified, that wasn't falsified.

Consequences: The composed pipeline is validated at `p=30`,
`N in [750, 1500]`, for disjoint 3-node motifs, using screening
`alpha=.0001` and DPI `alpha=f(N)`. This does **not** validate hub,
overlap, or other candidate shapes at `p=30` (each would need its own
charter, mirroring how Stage 2c/2d followed Stage 2b at `p=15`), nor
bootstrap stability at `p=30` (Stage 3's line of work remains `p=15`-
only), nor `p` values beyond `30`. `docs/validated_operating_ranges.md`
should record this as a new row alongside D-023's `p=30` screening-alone
entry.

## D-025: Hub-composed pipeline scales to p=30, exactly as predicted (R3i)

Date: 2026-08-30

Stage: R3i / Stage 2

Status: PROCEED at both `N = 750` and `N = 1500`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage2g_charter.md`

Question: Does the composed pipeline, with a hub candidate component
instead of a third triad, behave at `p=30` the way it did at `p=15`
(D-016), using D-023's `p=30` screening threshold reused without
re-derivation?

Prior specification: `docs/stage2g_charter.md` predicted, by combining
D-023 (screening's per-edge FPR `~.00012` at `alpha=.0001`, `p`- and
shape-independent), D-024 (composition doesn't disturb that rate at
`p=30`), and D-016 (hub composes cleanly at `p=15`, indirect TPR
`.820`-`.853`): PROCEED at both `N`, final false-edge rate `~.0001`,
indirect TPR `~.82`-`.85` (plausibly a little higher, per D-024's own
observed shape-rate increase), true-edge FPR `~0`.

Evidence: `results/generated/stage2g_hub_composition_p30/decision.json`,
4,000 raw rows, zero errors, runtime 109s. Final false-edge rate
`.000121`/`.000099` (`N=750`/`N=1500`), identical to screening-alone at
both `N` — D-014's "no rescue" finding, now replicated on a second
candidate shape at `p=30`; indirect TPR `.839`/`.883`, landing inside
the predicted range and, like D-024, at the higher end of it; true-edge
FPR exactly `0` at both `N`; shape-validated rate `.984`/`.991`, closely
matching D-024's own `.983`/`.994` for the triangle-shape charter at the
same `p`. See `docs/stage2g_report.md`, `false_edge_rate_comparison.png`.

Decision: Proceed. The composed pipeline is validated at `p=30` for a
network containing a 4-node hub-clique candidate component (alongside
disjoint triads), using D-023's screening threshold and D-012's DPI
formula, reused without modification for either.

Rationale: Like D-024 and unlike D-023, this charter's predeclared
expectations held without needing correction. Combined, D-024 and D-025
show the `p=30` scale-up story is now consistent across both tested
candidate shapes: the same screening threshold, the same DPI formula,
and closely matching final-false-edge-rate and shape-validation figures
regardless of whether the third motif is a triangle or a hub. This is
the same "no shape-specific surprise" pattern D-016 established at
`p=15` (D-014's triad-only result transferring cleanly to the mixed
triad/hub network), now confirmed to hold across `p` as well as across
shape.

Consequences: Both tested candidate shapes' composition (disjoint
triads: D-024; hub-containing: D-025) are validated at `p=30`,
`N in [750, 1500]`, using screening `alpha=.0001` and DPI `alpha=f(N)`.
This does **not** validate the shared-node-overlap shape at `p=30`
(explicitly deferred by this charter's own consequences — and the one
shape where D-018's `N=750` weak-signal caveat makes a safe-transfer
assumption least justified), bootstrap stability at `p=30` for either
tested shape, or `p` values beyond `30`. `docs/validated_operating_ranges.md`
should record this alongside D-024's own `p=30` composition row.

## D-026: p=30's stricter screening threshold pushes the overlap DGP's N floor beyond 1500 (R3j)

Date: 2026-08-30

Stage: R3j / Stage 2

Status: **REASSESS at both `N = 750` and `N = 1500`**

Decision timing: Predeclared gate evaluated after results, per
`docs/stage2h_charter.md`

Question: Does `p=30`'s stricter, automatically-selected screening
threshold (D-023: `alpha=.0001`, chosen for the multiple-testing
burden, not any specific motif's signal strength) turn the overlap
DGP's already-marginal `N=750` weak-signal problem (D-018) into
something worse, and does it put `N=1500` — comfortably passing at
`p=15` — at risk too?

Prior specification: `docs/stage2h_charter.md` recomputed D-018's own
Fisher-z power calculation at `alpha=.0001` instead of `.001`, predicting
naive clean-clique rates of `.034` (`N=750`, down from `.194` at
`p=15`'s threshold) and `.697` (`N=1500`, down from `.905`). It predicted
`N=750` would REASSESS decisively (even after applying D-018's own
`~1.5x` observed correction factor), and left `N=1500` explicitly
uncertain — the naive estimate was below gate, but D-018's actual
result had run well above its own naive estimate at the harder cell.

Evidence: `results/generated/stage2h_overlap_composition_p30/decision.json`,
4,000 raw rows, zero errors, runtime 62s. **`N=750`**: overlap indirect
TPR `.6365` (REASSESS, decisive failure as predicted, but well above
the naive `.034`/corrected `~.05` estimate); clean-clique rate `.080`
(vs. naive `.034` — an observed correction factor of `~2.35x`, larger
than D-018's own `~1.5x` at `p=15`, suggesting the positive correlation
among the four cross-branch tests matters *more*, not less, at a
stricter threshold). Chain/fork TPR (`.840`/`.839`) and true-edge FPR
(`0`) behaved normally, as predicted. **`N=1500`**: overlap indirect TPR
`.762` — **REASSESS, but a near-miss** (`.038` below the `.80` gate, not
a decisive failure), unlike D-018's own comfortable `.817` PROCEED at
`p=15`'s threshold. Clean-clique rate `.753` (vs. naive `.697`, a
smaller `~8%` relative correction near the ceiling, as expected). Final
false-edge rate (`.000122`/`.000107`) tracked screening-alone exactly at
both `N`, replicating D-014's finding on a third shape now. See
`docs/stage2h_report.md`, `overlap_clean_clique_vs_tpr.png`.

Decision: **REASSESS at both `N`.** This is the outcome the charter's
own predeclared table treated as the central open question (not the
"both PROCEED" case its Consequences section called more surprising),
and it resolved toward the harder side: `N=1500`, previously a
comfortable PROCEED for this shape at `p=15`, no longer clears the gate
once `p=30`'s stricter automatic threshold is applied.

Rationale: **This is the first charter in the `p=30` line to find a
genuinely new problem, not confirm a prediction of success.** D-023 and
D-024/D-025 established that `p=30`'s stricter threshold is harmless
for signals strong enough to have near-total detection power at either
`alpha` — but the overlap DGP's weak `~.135` correlation was never in
that category, and this charter's own predeclared power calculation
correctly anticipated that reusing an automatically-selected,
signal-agnostic threshold would matter here specifically. The `N=1500`
near-miss (`.762` vs. `.80`) is the most actionable part of this
result: it is close enough to the gate that the true floor for this
shape at `p=30` is plausibly just above `1500`, not far beyond it — a
locatable question, not an open-ended one, the same kind of question
D-010/D-011 answered for the general DPI floor.

Consequences: **A `p`-driven screening threshold, selected without
regard for individual motif signal strength (as D-023's own selection
procedure does, by design — it only ever looks at recall/FDR against
whatever DGP it is run on), cannot be assumed to transfer safely to
every candidate shape at that `p`.** This is now demonstrated, not
hypothetical. `docs/validated_operating_ranges.md` must record the
shared-node-overlap shape as **REASSESS at both tested `N` at `p=30`**,
distinct from and not overwriting the `p=15` entry (D-017/D-018), where
`N=1500` PROCEEDs. A natural, well-scoped follow-up charter (mirroring
D-010/D-011's own floor-location exercise) would search for the new
`N` floor at `p=30` for this shape specifically — this charter does not
attempt that, only establishes that `1500` is no longer sufficient.
Neither this result, nor Stage 2f/2g's clean PROCEEDs, should be
generalized to shapes or signal strengths not yet tested at `p=30`.

## D-027: Located the overlap shape's p=30 floor between N=1600 and 1750 (R3k)

Date: 2026-08-30

Stage: R3k / Stage 2

Status: REASSESS at `N=1500`/`1600`; **PROCEED from `N=1750` onward**

Decision timing: Predeclared gate evaluated after results, per
`docs/stage2i_charter.md`

Question: Where, between D-026's near-miss `N=1500` and comfortably
above it, does the overlap shape's `p=30` composed pipeline start to
clear the `.80` gate?

Prior specification: `docs/stage2i_charter.md` reused D-026's `N=1500`
evidence as a bookend and simulated four new sample sizes (`1600, 1750,
2000, 2500`), predicting — from the same Fisher-z power calculation
used throughout this line, adjusted by D-026's own observed
correlation-correction factor — a crossover landing somewhere in
`[1600, 1750]`.

Evidence: `results/generated/stage2i_overlap_floor_p30/decision.json`,
10,000 raw rows (2,000 reused `N=1500` + 8,000 fresh), zero errors,
runtime 150s. **A clean, monotonic transition, landing exactly where
predicted**:

| `N` | status | overlap TPR | overlap clean-clique rate |
|---|---|---|---|
| `1500` (reused) | REASSESS | `.762` | `.753` |
| `1600` | REASSESS (near-miss) | `.786` | `.781` |
| `1750` | **PROCEED** | `.815` | `.872` |
| `2000` | PROCEED | `.872` | `.942` |
| `2500` | PROCEED | `.906` | `.988` |

Chain/fork TPR (`.889`-`.910` throughout) and true-edge FPR (`0` at
every `N`) behaved normally at every sample size, isolating the effect
to the overlap motif exactly as every prior charter in this line
predicted.

Decision: **The `p=30` floor for the shared-node-overlap shape, at this
specific signal strength (`~.135` cross-branch correlation) and
screening threshold (D-023's `alpha=.0001`), is `N=1750`.** `N=1600` is
a genuine near-miss (`.786`, `.014` below gate) — closer to the
boundary than `N=1500` was, consistent with a real, locatable crossover
rather than noise, per this charter's own non-monotonicity caveat
(which did not trigger here: the transition was clean).

Rationale: This is the second charter in the `p=30` overlap line (after
D-026) to land a numeric prediction almost exactly on target — the
crossover fell inside the single 150-unit-wide predicted interval, not
merely somewhere in a vague "higher `N`" direction. Combined with
D-010/D-011's original `N=700`-`750` floor-location exercise for the
general DPI mechanism, this project now has two independently derived,
methodologically identical examples of the same finding: a
back-of-envelope power calculation, checked against one or two real
data points, can locate an operational floor to within a narrow range
before running the full search — evidence the underlying detection-
power model is doing real explanatory work, not just curve-fitting
after the fact.

Consequences: `docs/validated_operating_ranges.md`'s D-026 REASSESS row
should be updated: the shared-node-overlap shape's `p=30` floor is
**`N=1750`, not merely ">1500, unlocated."** `N=1500` and `N=1600`
remain REASSESS and should not be used for this shape at `p=30`. This
floor is specific to this DGP's exact signal strength (`~.135`) and
D-023's exact screening threshold (`alpha=.0001`) — a different weak
signal strength, or a different `p`-driven threshold, would need its
own floor search, not an assumption that `1750` transfers.

## D-028: Bootstrap stability filtering rescues the overlap DGP's p=30 floor cases (R4e)

Date: 2026-08-30

Stage: R4e / Stage 3

Status: PROCEED at `N = 1500`, `N = 1600`, and `N = 1750`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage3e_charter.md`

Question: Does the same post-hoc bootstrap-stability filter that
rescued Stage 3b's `p=15` overlap failure (D-020) also rescue D-026/
D-027's `p=30` REASSESS cases (`N=1500`, `.762`; `N=1600`, `.786`, both
below the `.80` gate) — misses `6`-`16x` smaller than Stage 3b's
starting point — without regressing the already-passing `N=1750`?

Prior specification: `docs/stage3e_charter.md` reused Stage 3b's exact
grid (`pi_min in {.80, .90, .95, .98}`) and four-part gate unmodified,
on the `p=30` overlap DGP at `N=[1500, 1600, 1750]`, 60 replicates each
(30 development / 30 validation), `B=500`. Predicted — as an analogy
from Stage 3b, not from prior `p=30` bootstrap evidence, since none
existed — that filtering would rescue both `N=1500` and `N=1600`,
plausibly at a `pi_min` at or below Stage 3b's own `.80`.

Evidence: `results/generated/stage3e_overlap_p30_filter/decision.json`,
zero errors, runtime 1851s (~31 min). **All three `N` PROCEED**, all
selecting the smallest candidate, `pi_min=.80`:

| `N` | baseline overlap TPR | filtered (validation) overlap TPR | true-edge FPR |
|---|---|---|---|
| `1500` | `.800` (dev) | `.850` | `0` |
| `1600` | `.742` (dev) | `.900` | `0` |
| `1750` | `.825` (dev) | `.900` | `0` |

Chain/fork indirect TPR (`.90`-`.97`) and final false-edge rate (`<=
.00016`, `0` at two of three `N`) never regressed relative to baseline
at any `N`, matching the gate's safe-by-construction criteria exactly.
This run's own baseline TPRs (fresh 60-replicate draws, different seeds
from D-026/D-027's floor-search evidence) differ slightly from
D-026/D-027's numbers (`.800`/`.742`/`.825` here vs. `.762`/`.786`/
`.815` there) but tell the same story: `N=1500` and `1600` sit at or
below the `.80` gate pre-filtering, `1750` sits just above it. See
`docs/stage3e_report.md`, `overlap_tpr_vs_pi_min.png`,
`before_after_filtering.png`.

Decision: **The charter's directional prediction was confirmed exactly,
including the specific `pi_min`.** Filtering at `pi_min=.80` — Stage
3b's own selected threshold, not a more aggressive one — rescues both
`N=1500` and `N=1600` at `p=30`, and does not regress `N=1750`.
Contrary to a naive expectation that "harder to detect" would mean
"harder to fix," the smaller `p=30` misses needed no more aggressive a
filter than the much larger `p=15` miss did.

Rationale: This is the second rescue demonstration in the project (after
D-020) and the first to test whether a validated rescue *threshold*
value, not just the rescue *mechanism*, transfers across a `p` change
on the same DGP shape and signal strength. It does, without
recalibration — consistent with the mechanism separating edges by
resampling stability, a property of the DGP's signal-to-noise structure
rather than of `p` itself. Combined with D-026/D-027's own on-target
numeric predictions, this is now the third consecutive `p=30` overlap
charter in this line whose predeclared, evidence-grounded prediction
landed correctly, not merely directionally.

Consequences: A real dataset with this DGP shape stuck at `p=30`,
`N=1500`-`1600` need not collect `1750`+ samples to reach a valid
result for the overlap motif specifically — it can instead apply
`pi_min=.80` filtering at its existing `N`, at the cost of `B=500`x
resampling compute, a real tradeoff each user must weigh (this charter
does not resolve whether that tradeoff is worth it in general). This
does not authorize skipping D-027's floor-finding approach when more
data is feasible to collect, nor generalize to other weak-signal shapes,
signal strengths, or `p` values not yet tested this way.
`docs/validated_operating_ranges.md`'s bootstrap-stability-filtering row
(Stage 3b, D-020) should be extended to note this `p=30` confirmation at
the same `pi_min=.80`, rather than adding a wholly new row, since the
selected threshold and mechanism are unchanged — only the tested `p`
and specific `N` values are new.

## D-029: Lower p does NOT lower the overlap shape's floor below N=1500 (R5a)

Date: 2026-08-30

Stage: R5a / Stage 2

Status: REASSESS at `N=750`, PROCEED at `N=1500`, at **both** `p=5` and `p=10`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage2j_charter.md`

Question: Motivated by real behavioral/psychological datasets typically
having `p=5`-`10`, does the general `N=750` floor hold for the
shared-node-overlap shape at these lower `p`, since fewer null pairs
should let screening use a looser `alpha` — reversing the mechanism
that raised the overlap floor to `N=1750` at `p=30` (D-026/D-027)?

Prior specification: `docs/stage2j_charter.md` predicted **PROCEED at
`N=750`** for the overlap shape at both `p=10` (overlap + chain motif +
2 noise) and `p=5` (overlap motif only, zero noise columns — false-edge
rate undefined there, disclosed in advance). Screening alpha
re-selected at `p=10` via D-013/D-023's own methodology (grid `{.05,
.01, .005, .001, .0005, .0001}`, eligibility recall `>=.99`/FDR
`<=.05`); `p=5` fixed at D-013's original `alpha=.001` (selection is
meaningless with zero null pairs).

Evidence: `results/generated/stage2j_floor_check/decision.json`, zero
errors on all rows that were meant to run, runtime 26s.

| `p` | `N` | status | overlap TPR | clean-clique rate |
|---|---|---|---|---|
| 10 | 750 | REASSESS (no eligible dev. alpha) | — | — |
| 10 | 1500 | PROCEED | `.814` | `.866` |
| 5 | 750 | REASSESS | `.606` | `.305` |
| 5 | 1500 | PROCEED | `.836` | `.902` |

At `p=10`, `N=750` never reached the composition gate at all: **no
candidate screening `alpha` cleared this charter's own selection
eligibility** (recall `>=.99` and FDR `<=.05` on development) — every
alpha in the grid was either too strict (missing true pairs, failing
recall) or too loose (failing FDR), a decisive result, not a near-miss.
`p=5`'s `N=750` overlap TPR (`.606`) and clean-clique rate (`.305`) are
close to D-018's own original `p=15` `N=750` numbers (`.569`-`.633`
TPR, `~.26`-`.29` clean-clique rate) — **essentially unchanged from the
`p=15` floor already known**, not improved by the ten-fold reduction in
null-pair count.

Decision: **This charter's directional prediction was wrong.** Lower
`p` does not rescue `N=750` for the shared-node-overlap shape; the
floor stays at `N=1500`, the same value D-017/D-018 established at
`p=15`. `N=1500` PROCEEDs comfortably at both lower `p` (overlap TPR
`.81`-`.84`, true-edge FPR `0` throughout).

Rationale: The screening-pressure mechanism this charter reasoned from
is real (D-023 showed it going *up*, this charter's own `p=10` selected
`alpha=.0005` — slightly *tighter*, not looser, than `p=15`'s `.001`,
because the specific true:null ratio and grid interact non-monotonically
rather than tracking null-pair count alone) but it was never the
dominant factor for this specific floor. **The overlap shape's `N=750`
failure is governed by the per-pair detection power of its weak
(`~.135`) cross-branch correlation at fixed `N` — a property of the
correlation's Fisher-z power curve, which does not depend on how many
*other* variables or null pairs exist in the dataset.** Screening
pressure only matters when it is severe enough to move the selected
`alpha` by an order of magnitude, as it did going from `p=15` to `p=30`
(`.001` to `.0001`, D-023) — a much larger shift than anything seen
between `p=5`/`10`/`15` here. This explains the full pattern now on
record: `p=5`, `10`, `15` all share the same `N=1500` floor for this
shape; only `p=30` pushed it higher, to `N=1750` (D-026/D-027).

A secondary, narrower finding: `p=10`'s screening-alpha selection step
itself narrowly missed its own validation recall bar (`.9864` vs. the
required `.99`), even though the composition gate that used the
selected alpha still PROCEEDed comfortably at `N=1500`. This reflects
that charter's own selection thresholds (`recall>=.99`, `FDR<=.05`)
being deliberately stricter than Stage 2/2e's established precedent
(`recall>=.80`, `FDR<=.10`), not a real detection problem — a `.9864`
recall is not a practically meaningful shortfall. Future charters
reusing this selection methodology should default to Stage 2/2e's own
thresholds unless there is a specific reason to tighten them, to avoid
manufacturing confusing near-misses like this one.

Consequences: `docs/validated_operating_ranges.md`'s shared-node-overlap
row should be extended: the shape's `N=1500` floor (previously
established only at `p=15`/`30`) now also holds at `p=5` and `p=10` —
**this floor is effectively `p`-invariant across the tested range
`[5, 30]` at `N=750` failing / `N=1500` passing, except that `p=30`
additionally requires `N=1750`, not `1500`, for the reason above.** Do
not assume any `p < 15` gets an easier ride than `p=15` for this
specific shape — the opposite of this charter's own prediction. This
does not change the general `N=750` DPI/composition floor for
strong-signal shapes (disjoint-triad, hub), which remains untested below
`p=15` for those shapes specifically, though there is no mechanism-level
reason to expect it to move. Real behavioral datasets with `p=5`-`10`
and a shape resembling this weak-signal overlap pattern should budget
for `N>=1500`, the same as at `p=15`, not assume a lower `p` grants any
relief.

## D-030: Sequential/greedy engine reproduces Stage 1b's own limitation, not a new one (R6a)

Date: 2026-08-30

Stage: R6a / Stage 4 (new engine)

Status: REASSESS — but equivalent to the conservative engine's own
original result on this identical evidence, not worse

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4a_charter.md`

Question: Does the sequential/greedy conditioning engine (rank
candidates by association strength, confirm the strongest immediately,
test the rest by conditioning on already-confirmed neighbors, with
permanent pruning) correctly recover the three smallest known motifs
(chain, fork, triangle) at Stage 1b's own original `N` grid and
selection rule — the smallest falsifiable slice, deliberately reusing
Stage 1b's exact DGP, seeds, and gate before touching the actual
motivating weak-shape question (deferred to Stage 4b)?

Prior specification: `docs/stage4a_charter.md` reused
`docs/stage1b_charter.md`'s exact DGP (`N in [100..1000]`, strengths
`[.3,.5,.7]`, `balanced`/`moderate`/`strong` triangle families, 500
replicates, same alpha grid) and gate (lexicographically-first adjacent
eligible alpha pair on development, confirmed on validation). The
charter explicitly asked for a *direct* comparison against Stage 1b's
own recorded numbers at matching cells, not just an independent
PROCEED/REASSESS call — flagging in advance that a bare REASSESS would
not, by itself, indicate a defect in the new mechanism if the numbers
matched Stage 1b's own.

Evidence: `results/generated/stage4a_sequential/decision.json`, zero
errors, runtime 93s. **Selected development pair `(0.05, 0.10)`;
REASSESS on validation**, failing only "triangle genuine-edge pruning
FPR" — at strength `.7` (the `strong`, most-asymmetric triangle family),
FPR reaches `.19` (`N=500`, `alpha=.05`) against the `.10` gate. Chain
and fork indirect-edge TPR passed at every validation cell.

**The direct comparison is the informative part.** Across all 486
matching `(motif, n, strength, alpha)` cells against Stage 1b's own
on-disk evidence (`results/generated/stage1b_dpi/aggregate_metrics.csv`,
its *original* result — not D-008, which is Stage 1g's later,
differently-scoped refinement using a narrower `N in [750,1000,1500,2000]`
grid and margin-robust selection; **the charter's own citation of "D-008
evidence" for this comparison was imprecise and is corrected here**):

- At the exact cells that drove this charter's REASSESS (`N in
  [500,750,1000]`, strength `.7`, `alpha in {.05,.10}`), the sequential
  engine's triangle FPR is within `.01`-`.02` of Stage 1b's own FPR at
  every cell (e.g. `N=500, alpha=.05`: `.194` sequential vs. `.184`
  Stage 1b) — **this REASSESS is inherited from Stage 1b's own original
  charter having the identical problem at this identical `N` range**,
  which is exactly why the conservative engine's own arc needed Stage
  1c through 1g (extending to `N=2000`-`3000`, margin-robust selection)
  before reaching D-008's PROCEED. It is not a new failure mode
  introduced by the sequential design.
- Overall, mean absolute delta across all 486 cells is small (indirect
  TPR `.021`, true-edge FPR `.012`), confirming the two engines'
  underlying per-edge conditional-independence test behaves the same
  way when both engines end up testing the same edge.
- **A genuinely new, unpredicted finding**: at small `N` (`100`-`300`),
  the sequential engine's true-edge FPR runs consistently *below* Stage
  1b's own (mean delta `-.020`, up to `-.257` at the most extreme
  cells) — it wrongly prunes true triangle edges *less* often than the
  conservative engine at these `N`. This follows directly from the
  design: the two highest-ranked edges of a triangle are confirmed
  immediately, with no conditional test at all, so at most one of a
  triangle's three edges can ever be wrongly pruned under the
  sequential engine, versus all three being independently at risk under
  the conservative engine's symmetric per-edge test.

Decision: **PROCEED to Stage 4b**, not because this charter itself
PROCEEDed (it did not, per its own frozen gate), but because the
Consequences section's actual condition for continuing — "no material
regression against Stage 1b's own numbers" — is met. The mechanism is
behaviorally equivalent to the validated conservative mechanism on the
smallest falsifiable slice, and diverges in one specific, understood,
favorable direction (small-`N` triangle robustness) rather than an
unexplained one.

Rationale: This charter deliberately reused Stage 1b's original,
since-superseded grid rather than Stage 1g's refined one, specifically
so that any REASSESS here would be diagnosable against a known baseline
rather than ambiguous. That design choice paid off directly: without
the cell-by-cell comparison, this REASSESS could have been
misread as "the greedy mechanism doesn't work," when the actual finding
is "the greedy mechanism works exactly as well as the already-validated
one on this slice, and this specific `N` range's marginal alpha problem
was already known and already solved once, by extending `N` and
refining selection, not by fixing DPI itself." Re-deriving that same fix
here was not this charter's job.

Consequences: This charter does **not** authorize any user-facing
exposure of the sequential engine, a default `engine` parameter, or a
claim that it needs less data than the conservative engine for any
shape — Stage 4b (hub/overlap components, the shape this whole
initiative is motivated by) and Stage 4c (the cascading-error stress
test) remain open, per the R6a milestone in
`outline/information_network_technical_build_plan_v3_2026-08-30.md`.
`docs/validated_operating_ranges.md` should record this charter's status
as informational only — no operating range is validated by Stage 4a
itself. The small-`N` asymmetry finding above is worth carrying into
Stage 4b's design (it may generalize to larger components, or it may
not — worth checking explicitly, not assumed).

## D-031: Sequential engine dramatically closes the overlap shape's N=750 gap (R6b)

Date: 2026-08-30

Stage: R6b / Stage 4 (new engine)

Status: PROCEED (hub, both `N`; overlap `N=1500`). Overlap `N=750`:
**near-miss REASSESS** — clears the raw TPR gate, narrowly misses the
stricter comfort-margin requirement.

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4b_charter.md`

Question: Does the sequential engine, run end-to-end (fused screening +
conditioning, no pre-flagged input) on the isolated hub and overlap
DGPs, PROCEED at `N=750` for the overlap shape — the exact `N` and DGP
where D-018's composed conservative pipeline REASSESSed (TPR `.569`)
despite D-017 showing the conditioning mechanism itself works fine when
handed a clean component (TPR `.858`)?

Prior specification: `docs/stage4b_charter.md` reused Stage 1k's hub and
Stage 1L's overlap DGPs unmodified, predicted hub PROCEEDs comfortably
at both `N` (plausibly beating D-015's own margins, per the targeted-
conditioning argument), and predicted overlap "a real possibility of
PROCEED at `N=750`" as an explicitly falsifiable, not foregone,
prediction — explicitly stating this isolated-DGP test already engages
the motivating question because the sequential engine has no
pre-flagged-input step to bypass the all-pairs-simultaneously
requirement the way Stage 1L's hand-fed test did.

Evidence: `results/generated/stage4b_hub_overlap/decision.json`, zero
errors, runtime 98s.

| shape | N | status | selected alpha | indirect TPR | true-edge FPR | margin |
|---|---|---|---|---|---|---|
| hub | 750 | PROCEED | 0.10 | `.894` | `0` | `.094` |
| hub | 1500 | PROCEED | 0.10 | `.909` | `0` | `.100` |
| overlap | 750 | REASSESS (near-miss) | 0.20 | `.818` | `0` | `.018` |
| overlap | 1500 | PROCEED | 0.10 | `.899` | `0` | `.099` |

**Direct comparison** (`conservative_comparison.csv`), the informative
part:

| shape | N | sequential TPR | D-015/D-017 hand-fed TPR | D-018 composed TPR |
|---|---|---|---|---|
| hub | 750 | `.894` | `.854` | — |
| hub | 1500 | `.909` | `.887` | — |
| overlap | 750 | **`.818`** | `.858` | **`.569`** |
| overlap | 1500 | `.899` | `.894` | `.817` |

Decision: **Hub PROCEEDs at both `N`, slightly exceeding the
conservative engine's own hand-fed numbers** (consistent with the
targeted-conditioning hypothesis: conditioning only on the actual shared
neighbor, not every other node in the component, costs less power).
**Overlap at `N=750` is the central result**: sequential TPR (`.818`)
sits almost exactly at D-017's hand-fed conservative ceiling (`.858`)
and **recovers `86%` of the entire gap** between D-018's composed-
pipeline REASSESS (`.569`) and that ceiling — using the exact same raw
data-generating process and signal strength D-018 REASSESSed on. It
clears this charter's raw `.80` TPR gate outright; it misses only the
stricter, deliberately conservative `.02` comfort-margin requirement
(margin `.0175`), by a trivial amount relative to sampling noise at 1000
validation replicates. This is **not** the same kind of REASSESS as
D-018's (TPR `.231` below gate, decisive) — it is a near-miss on a
buffer requirement layered on top of an already-cleared primary
threshold.

Rationale: This is the first evidence in this project's history that
directly attacks D-018's specific composed-pipeline failure and
substantially fixes it, without collecting more data and without the
`B=500`x bootstrap-filtering cost D-020/D-028 required — using only a
different composition *order*, applied to raw data the sequential
engine was never told was "clean." The remaining `.04` gap between
sequential's `.818` and D-017's `.858` hand-fed ceiling is plausibly
explained by the sequential engine still requiring each cross-branch
pair to individually clear its own marginal candidacy threshold before
any conditioning is attempted at all — a residual, much weaker version
of the detection-power limitation D-017/D-018 originally identified, not
eliminated but sharply reduced by no longer requiring all four
simultaneously.

Consequences: This is genuinely promising but **not yet a validated
operating range for anything** — per the R6a milestone in
`outline/information_network_technical_build_plan_v3_2026-08-30.md`,
both this charter's own near-miss status at `N=750` and Stage 4c's
cascading-error stress test remain open before any user-facing claim.
Two concrete next steps this result motivates, neither undertaken here:
(1) a small alpha-grid or replicate-count refinement specifically at
overlap `N=750` to check whether the `.0175` margin near-miss is
noise-boundary-sensitive or a real, stable shortfall; (2) extending this
same isolated-DGP comparison to a full noisy `p=15` composed network
(mirroring Stage 2d after Stage 1L) to confirm the effect survives
embedding in a larger candidate pool, since this charter's own
DGP has no noise columns and therefore does not yet test whether the
sequential engine's fused screening step degrades differently than the
conservative engine's separate screening step once many more null pairs
are present. `docs/validated_operating_ranges.md` should record this as
a promising, unresolved signal, not a floor.

## D-032: Overlap's apparent "no floor" is a metric artifact, not a genuine finding; hub's is real (R6c)

Date: 2026-08-30

Stage: R6c / Stage 4 (new engine)

Status: PROCEED at every tested `N` for both shapes, per the charter's
literal gate — **but this entry corrects the overlap half of that
result before it is used for anything**, per this project's own
self-correction discipline (D-019, D-023 precedent)

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4d_charter.md`. The correction below was reached by
inspecting diagnostic columns this charter itself required as evidence
(`conditionally_tested_pairs`, `confirmed_pairs`), not by re-opening the
frozen gate.

Question: How low can the sequential engine go below `N=750`, and does
its predeclared early-stop condition (transition matching the base
mechanism's known `[600,700]` range) hold?

Prior specification: `docs/stage4d_charter.md` tested `N=[300, 500, 600,
650, 700]` plus the `N=750` bookend from Stage 4b, predicting hub tracks
the base mechanism's known transition and flagging overlap's floor as
the open question.

Evidence: `results/generated/stage4d_floor_search/decision.json`, zero
errors, runtime 226s. **Every cell PROCEEDs except overlap at `N=750`**,
which REASSESSes by the same `.0175` near-miss margin already recorded
in D-031 (confirming the bookend merge is correct — identical numbers).
The **early-stop condition is formally NOT MET**, but for two very
different reasons per shape:

**Hub: a genuine, verified finding.** Indirect TPR is flat (`.895`-
`.911`) across the entire `N=300`-`750` range, and the diagnostic
`conditionally_tested_pairs` column is exactly `3.00` (all 3 indirect
child-child pairs) at *every* `N`, including `300` — meaning every
indirect pair reliably clears screening and reaches an actual
conditioning test at every tested `N`. This is not the base mechanism's
own `[600,700]` transition because that reference number was calibrated
on Stage 1's *worst-case* asymmetric triangle grid (one true edge as
weak as strength `.3`); hub's fixed strength-`.5` child-child induced
correlation (`~.25`) is comfortably separated from noise at every `N`
tested here. **The comparison target itself, not hub's result, was the
wrong reference for this specific DGP** — a charter-design lesson, not
a claim that hub transcends the base test's own statistical limits.

**Overlap: the apparent improvement at low `N` is an artifact, verified
directly, not a genuine result.** Indirect TPR *rises* as `N` falls
(`.878` at `N=300` vs. `.818` at `N=750`) — backwards from every prior
finding in this project. Diagnostic evidence explains why:
`conditionally_tested_pairs` for overlap **falls** with `N` (`5.44` at
`300` to `5.97` at `750`, out of 10 possible), and a direct, independent
re-check (300 fresh replicates outside the charter's own pipeline,
counting how many of the 4 weak cross-branch pairs even clear screening)
confirms it: only `3.42`/`4` clear screening at `N=300`, vs. `3.96`/`4`
at `N=750`. **A cross-branch pair that never becomes a candidate is
scored identically to one correctly identified as spurious and
pruned** — both are simply absent from the final graph. At low `N`,
screening's own reduced power to detect the weak (`~.135`) cross-branch
correlation causes *more* of these pairs to never be tested at all,
which this charter's TPR metric cannot distinguish from the engine
correctly reasoning about them. **The apparent low-`N` overlap PROCEED
results are not evidence the sequential engine handles this shape well
below `N=750` — they are evidence the metric cannot tell "correctly
pruned" from "never evaluated" apart, and should not be read as a floor
in either direction.**

Decision: Hub's flat, verified robustness down to `N=300` is accepted as
a real finding. **No conclusion is drawn about the overlap shape's floor
below `N=750`** — this charter's chosen metric is not fit for that
purpose at low `N`, and a corrected version (reporting screening-
candidacy rate for the 4 cross-branch pairs as its own tracked
quantity, separate from final pruned/retained status) would be needed
before this specific question could be answered. The user's original
motivating question — "if the results are consistent with what we did
before, call it off quickly" — is answered for hub (yes, consistent,
call it off) and left genuinely open for overlap, for a reason the
predeclared plan did not anticipate.

Rationale: This is the same "stable does not mean correct" caution the
outline's Section 2.3 states for bootstrap stability, applied to a new
case: **absent does not mean correctly pruned.** Catching this required
looking past the single gate metric at the diagnostic columns this
charter's own "Required evidence" section asked for — a direct
vindication of collecting that evidence even though the frozen gate
didn't strictly require it to render a PROCEED/REASSESS verdict.
Reporting this charter's literal PROCEED-at-every-cell result for
overlap without this correction would have been a false positive
finding entering the record, exactly the failure mode this project's
decision-log discipline exists to prevent.

Consequences: `docs/validated_operating_ranges.md` should record hub's
robust `N=300`-`750` range for the sequential engine as informational
(still no validated status pending Stage 4c). **It must explicitly flag
that overlap's floor below `N=750` remains unknown, with the specific
reason (metric conflates non-detection with correct pruning) stated,
not merely "untested."** A future charter wanting to answer "how low can
overlap go" would need a corrected metric — e.g., reporting the
screening-candidacy rate for the 4 cross-branch pairs alongside TPR, and
gating on TPR only among replicates where all 4 were actually
candidates — before trusting any `N` below `750` for this shape under
either engine.

## D-033: Candidacy-conditional metric reveals a second, unexplained pattern (R6d)

Date: 2026-08-30

Stage: R6d / Stage 4 (new engine)

Status: PROCEED at every tested `N` (`300`-`750`) on the corrected gate
— **but the predeclared expectation this charter was built to check did
not hold, and this entry does not claim to know why yet**

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4e_charter.md`, including its own predeclared prediction

Question: Once screening candidacy is separated from conditioning
correctness for the overlap shape's 4 cross-branch pairs, does
`conditional_accuracy` show the normal, non-decreasing-in-`N` pattern
(confirming D-032's diagnosis was complete), or does it still rise as
`N` falls (meaning that diagnosis was incomplete)?

Prior specification: `docs/stage4e_charter.md` predicted the corrected
metric would remove the backwards pattern D-032 found and predeclared
that a still-backwards result would mean "the artifact explanation
itself was incomplete and needs further diagnosis before trusting
either metric" — stated as a real possible outcome, not assumed away.

Evidence: `results/generated/stage4e_candidacy_metric/decision.json`,
zero errors, runtime 184s.

| N | candidacy rate | conditional accuracy (selected alpha) |
|---|---|---|
| 300 | `.874` | `.861` (alpha `.20`) |
| 500 | `.955` | `.844` (alpha `.20`) |
| 600 | `.978` | `.830` (alpha `.20`) |
| 650 | `.963` | `.922` (alpha `.10`) |
| 700 | `.991` | `.828` (alpha `.20`) |
| 750 | `.975` | `.917` (alpha `.10`) |

**The predeclared expectation did not hold — candidacy rate behaves
normally (rises with `N`, as expected), but conditional accuracy is
mildly *higher*, not lower, at small `N`.** Because different `N` cells
selected different alphas (`.10` vs. `.20`), the table above is not a
clean apples-to-apples curve by itself. A direct, alpha-held-fixed
re-check resolves that ambiguity and shows the pattern is real, not a
selection-of-alpha artifact: at **every** tested alpha (`.05`, `.10`,
`.20`, `.30`), conditional accuracy on validation declines modestly and
consistently as `N` rises from `300` to `750` (e.g. at alpha `.10`:
`.934` at `N=300` down to `.917` at `N=750`; at alpha `.20`: `.861` down
to `.825`). A further per-pair breakdown confirms this is uniform across
all 4 individual cross-branch pairs (each pair's own accuracy-given-
candidate at alpha `.10` runs `~.93` at `N=300` vs. `~.90`-`.92` at
`N=750`), not an artifact of one specific pair dominating the pooled
average.

Decision: **Accept the finding as real** (it survives alpha-controlled
and per-pair checks) **and explicitly decline to explain it.** A
plausible but unverified hypothesis: at low `N`, a cross-branch pair
only becomes a candidate at all if its *marginal* sample correlation
happens to be unusually large relative to its small true population
value (`~.135`) — essentially a favorable sampling fluctuation. That
same fluctuation has no particular reason to also inflate the
*conditional* (partial-correlation) test after controlling for the
shared node, since the two test different quantities — so candidates
selected this way at low `N` may still get correctly pruned at a normal
rate, while at high `N`, a much larger and more complete set of
candidates (including more genuinely borderline cases now within
reach of detection) dilutes the pool with pairs that are intrinsically
harder to correctly classify. **This hypothesis is not verified here**
and should not be treated as established.

Rationale: This is the second time in two consecutive charters that a
straightforward, well-motivated fix to a diagnosed measurement problem
(D-032's non-detection confound) has produced a still-surprising result
rather than the expected clean confirmation. Per this project's own
falsification-first discipline, the correct response to a predeclared
prediction failing twice in a row on the same question is to stop and
report the finding honestly, not to keep patching the metric
speculatively until it produces the "expected" answer — that would
risk exactly the kind of post hoc rationalization this project's
decision-log discipline exists to prevent.

Consequences: **Overlap's floor question remains genuinely open, and
this project should not report any `N` recommendation for this shape
under the sequential engine, favorable or unfavorable, until this
pattern is either explained or ruled out as noise with a dedicated,
narrowly-scoped charter** (e.g., directly testing the selection-effect
hypothesis above by comparing the marginal-correlation distribution of
candidate vs. non-candidate cross-branch pairs at matched `N`). This is
not merely "more data needed" — it is a real, reproducible, currently
unexplained property of the conditioning mechanism on this specific
weak-signal shape, and deserves scrutiny before Stage 4c or any
composed, noisy-network extension of this work proceeds, since an
unexplained mechanism-level anomaly is a poor foundation to build
further charters on. `docs/validated_operating_ranges.md` should record
this explicitly as an open anomaly, not as either a floor or a
non-result.

## D-034: The anomaly is explained — a fixed alpha is miscalibrated across N, not a mystery (R6e)

Date: 2026-08-30

Stage: R6e / Stage 4 (new engine)

Status: Anomaly explained; D-033's original hypothesis is **rejected**,
replaced by a mundane, well-understood mechanism

Decision timing: Descriptive, per `docs/stage4f_charter.md`'s own
predeclared sub-questions — no gate, evaluated as stated in advance

Question: D-033's two sub-questions — does marginal detection strength
predict conditional outcome among candidates (Q1), and is the low-`N`
candidate pool genuinely easier or just noisily selected (Q2)?

Evidence: `results/generated/stage4f_anomaly_diagnostic/summary.json`,
zero errors, runtime 16s.

| N | alpha | candidates | Q1 corr(|r_marginal|,|r_partial|) | Q2 mean |r_partial| | fraction correctly pruned |
|---|---|---|---|---|---|
| 300 | .10 | 6090 | `.635` | `.0390` | `.938` |
| 500 | .10 | 7338 | `.344` | `.0327` | `.934` |
| 750 | .10 | 7865 | `.155` | `.0281` | `.913` |
| 300 | .20 | 6874 | `.473` | `.0400` | `.864` |
| 500 | .20 | 7677 | `.218` | `.0339` | `.824` |
| 750 | .20 | 7956 | `.096` | `.0286` | `.807` |

**Both sub-questions came back opposite to D-033's original hypothesis,
and together they explain the anomaly completely.** Q1: marginal and
partial correlation are *not* independent — they are meaningfully
correlated at low `N` (`.63` at `N=300`, alpha `.10`) and only fade
toward independence as `N` grows (`.15` at `N=750`), the opposite of
"weak and `N`-stable." Q2: mean `|r_partial|` among candidates is
*larger*, not similar or smaller, at low `N` (`.039` vs. `.028`). **The
"marginal detection is an unrelated fluke" hypothesis is rejected on
both counts** — low-`N` candidates are not easier; if anything, their
partial correlations run noisier and larger.

Despite that, accuracy is still higher at low `N` — and the reason is a
simple, previously-overlooked fact about the significance test itself.
A direct calculation of the exact `|r_partial|` needed to reach
significance at `alpha=.10` (the Fisher-z critical value) is `.0953` at
`N=300` but only `.0601` at `N=750` — **the bar for "significant" itself
rises as `N` falls**, because a fixed `alpha` requires a bigger observed
effect at smaller `N` to clear the same threshold. At `N=300`, the
observed mean `|r_partial|` (`.039`) sits comfortably below that
elevated bar (`.41x` of it); at `N=750`, the observed mean (`.028`) sits
much closer to its own, lower bar (`.47x` of it) — a smaller safety
margin, hence more frequent (though still infrequent) wrong retentions.

Decision: **This is not a mystery requiring further diagnosis — it is
the same phenomenon D-012 already exists to correct for on the
conservative engine, showing up here because the sequential engine does
not yet have an equivalent fix.** D-012 fit an `alpha(N)` formula
specifically because a fixed significance level is miscalibrated across
`N` for exactly this reason (looser at small `N`, stricter at large `N`,
in a way unrelated to the actual quantity being tested). Stage 4a-4f all
used a single, `N`-independent `alpha` for the sequential engine's
conditioning step, by original design (Stage 4a's charter chose this
deliberately as the simplest first test). **The overlap shape's
apparent low-`N` "improvement" was this same known miscalibration
effect, not evidence the engine reasons better with less data.**

Rationale: This project's own established caution — a fixed `alpha`
does not mean a fixed burden of proof across `N` — was already learned
once, for the conservative engine, at real cost (multiple charters,
D-009 through D-012). It reappeared here because the sequential engine's
charters have not yet re-derived an equivalent `N`-adjusted threshold,
not because the sequential mechanism itself has any new or different
flaw. Two diagnostic charters (Stage 4e, Stage 4f) were needed to reach
this explanation cleanly, but the explanation itself, once found, is
unsurprising and consistent with everything already known about this
project's own statistical tests.

Consequences: **No overlap-shape `N` recommendation is authorized by
Stage 4b/4d/4e/4f's fixed-alpha evidence** — all of it was collected
under a threshold now known to be miscalibrated across the tested `N`
range, in the specific direction that flatters small `N`. Before this
shape's floor can be honestly assessed under the sequential engine, a
follow-up charter would need to fit an `N`-adjusted alpha for this
engine's conditioning step (mirroring D-012's own methodology), then
re-run the floor search under that corrected threshold — not assumed to
land at the same numbers Stage 4d/4e reported, in either direction.
Hub's own Stage 4d result is very unlikely to be affected in the same
way (its true/indirect signal separation is wide enough that threshold
miscalibration should not change the qualitative PROCEED outcome), but
this has not been explicitly re-checked with a calibrated alpha either,
and should be a light confirmatory check alongside the overlap
follow-up, not assumed. `docs/validated_operating_ranges.md` should
record this explanation and retract any implication that overlap's
floor is favorable or unfavorable at any `N` below `750` until the
recalibrated evidence exists.

## D-035: Recalibrated alpha(N) PROCEEDs at every tested N — the conditioning mechanism is sound (R6f)

Date: 2026-08-30

Stage: R6f / Stage 4 (new engine)

Status: PROCEED at all five held-out `N`

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4g_charter.md`

Question: Once the sequential engine's `alpha` is properly calibrated
per `N` (mirroring D-012's own methodology), does the overlap shape's
conditioning mechanism hold up across `N=[400, 550, 625, 675, 725]` —
the first evidence for this shape collected under a threshold not
already known to be miscalibrated (D-034)?

Prior specification: `docs/stage4g_charter.md` fit four candidate
`alpha(N)` forms from Stage 4e's own evidence (argmax `conditional_
accuracy` per `N`, subject to true-edge FPR `<= .10`), selected by R²,
then validated the single predicted `alpha_hat` at five interpolated
held-out `N` never simulated before.

**Implementation correction, made before any evidence was generated for
this charter (`mintnet.experiments.stage4g_fit`'s own docstring):** the
charter's literal fitting target (argmax accuracy alone) degenerates —
accuracy rises monotonically as `alpha` shrinks while candidacy falls
monotonically, so an unconstrained argmax always selects the single
strictest grid value at every `N`, which is not a meaningful "best"
alpha. A candidacy-rate floor of `.80` (matching this project's own
standard threshold convention) was added to keep the fitting target
interior and meaningful. Fitting points: `N=300` &rarr; `alpha=.2`;
`500`/`600` &rarr; `.05`; `650`/`700` &rarr; `.01`; `750` &rarr; `.005`
— a clean, monotonically decreasing curve, the expected shape.

Evidence: `results/generated/stage4g_alpha_calibration/decision.json`,
zero errors, runtime 22s. Selected form: **inverse_sqrt** (R² `.966`).

| N | alpha_hat | status | candidacy rate | conditional accuracy | margin |
|---|---|---|---|---|---|
| 400 | `.1211` | PROCEED | `.881` | `.913` | `.100` |
| 550 | `.0527` | PROCEED | `.890` | `.970` | `.100` |
| 625 | `.0281` | PROCEED | `.886` | `.980` | `.100` |
| 675 | `.0140` | PROCEED | `.855` | `.992` | `.100` |
| 725 | `.0015` | PROCEED | `.688` | `.999` | `.100` |

**All five held-out cells PROCEED comfortably** — conditional accuracy
`.913`-`.999`, well above the `.80` gate at every point, with the
binding margin constraint consistently the true-edge FPR side (FPR
stays near `0` throughout, so its margin caps near the `.10` ceiling
rather than accuracy driving the result).

**One disclosed caveat, not smoothed over:** candidacy rate at the
largest held-out `N` (`725`) drops to `.688` — well below the `.80`
floor the fitting procedure itself required at the six known points.
The fitted curve's predicted `alpha` becomes very strict at `N=725`
(`.0015`), pushing accuracy toward `1.0` at the cost of candidacy. The
smooth interpolating curve does not perfectly preserve the `.80`
candidacy constraint everywhere between fitting points — it was fit to
satisfy that constraint only at the six known `N`, not guaranteed
in-between.

Decision: **The sequential engine's conditioning mechanism itself is
sound for the overlap shape across this entire held-out range, once
`alpha` is properly calibrated to `N`.** D-034's anomaly is fully
resolved: it was never a property of the engine's reasoning, only of
testing it with a threshold that made low `N` look artificially easy.
This does **not** mean "the overlap shape's floor is now `N=400`" —
that claim would need the *candidacy* side of the picture reconciled
too (a low candidacy rate, even alongside high accuracy, means many
cross-branch pairs go unevaluated in practice), and this charter's own
`N=725` cell already shows the fitted curve does not automatically keep
both sides comfortable simultaneously.

Rationale: This closes the loop opened by D-032 (the original metric
artifact) through D-034 (the miscalibration explanation) — three
charters were needed to go from "surprising number" to "explained and
now correctable," each one narrowing the question rather than
rationalizing the previous result. That the fix, once applied, produces
clean PROCEEDs with large margins across the whole tested range is
itself evidence the underlying diagnosis (D-034) was correct, not just
plausible.

Consequences: The sequential engine's overlap-shape conditioning
mechanism is validated, under a calibrated `alpha(N)`, across `N in
[400, 725]` (interpolation only — this charter's own fitting range is
`[300, 750]`, do not extrapolate outside it). **This is still not a
full floor recommendation**: a proper "how low can this go" answer
needs the candidacy-rate side reconciled (e.g., a combined criterion
requiring both `conditional_accuracy` and `candidacy_rate` to clear
their own floors simultaneously, which this charter's fitted formula
was not required to guarantee off the exact fitting points), and remains
evidence from the isolated, no-noise overlap DGP, not a composed,
screening-realistic `p=15` network. Stage 4c's cascading-error stress
test remains the unconditional precondition for any user-facing claim,
per the R6a milestone. `docs/validated_operating_ranges.md` should
record this as: the conditioning mechanism is now trustworthy across
this `N` range under calibration, but the practical floor question
(accounting for candidacy) remains open.

## D-036: No cascading-error effect detected — the predeclared prediction was wrong (R6g)

Date: 2026-08-31

Stage: R6g / Stage 4 (new engine)

Status: Descriptive, no gate, per `docs/stage4c_charter.md`. Q1's
predeclared prediction ("a real, non-trivial increase") is **rejected**
by clean, decisive evidence.

Decision timing: Predeclared sub-questions evaluated after results, per
`docs/stage4c_charter.md`

Question: Does adding 5 pure-noise columns to Stage 1's asymmetric
`strong` triangle measurably increase the sequential engine's rate of
wrongly pruning the weak-but-real `(1,2)` edge (Q1), leave the
conservative engine roughly unaffected (Q2), and — when the sequential
engine does fail under contamination — is a noise column specifically
implicated in the failing conditioning test (Q3)?

Prior specification: `docs/stage4c_charter.md` predicted a "real,
non-trivial increase" in sequential wrong-pruning under noise, driven by
a noise column occasionally becoming a false shared-neighbor for the
weak edge; predicted little to no increase for the conservative engine,
since a partially-contaminated component simply breaks clique validity
and disables DPI. Paired design: identical triangle draw at
`noise_count=0` and `noise_count=5` per replicate, both engines on the
same data, `N=[100,200,300]`, `alpha in {.05,.10}`.

Evidence: `results/generated/stage4c_cascading_error/decision.json`
(via `summary.json`), zero errors, runtime 53s.

| N | alpha | seq. delta (noise=5 minus noise=0) | cons. delta | Q3 (noise implicated among wrong seq. prunes) |
|---|---|---|---|---|
| 100 | .05 | `0.0000` | `-.238` | `.0024` |
| 100 | .10 | `0.0000` | `-.389` | `.0058` |
| 200 | .05 | `0.0000` | `-.348` | `.0006` |
| 200 | .10 | `0.0000` | `-.478` | `.0029` |
| 300 | .05 | `0.0000` | `-.354` | `.0007` |
| 300 | .10 | `0.0000` | `-.434` | `.0008` |

**Q1 is rejected outright, not just weakly supported: the sequential
engine's weak-edge wrong-pruning rate is bit-for-bit identical with and
without noise contamination, at every single tested `(N, alpha)` cell.**
Q3 explains why directly: a noise column is implicated in fewer than
`.6%` of the sequential engine's (already frequent, `59%`-`84%`) wrong
prunings — the joint requirement for contamination (a noise column must
spuriously correlate with *both* endpoints of the target pair
simultaneously, not just one) is a far stronger filter than the
charter's prediction assumed. **Q2 is confirmed, and more strongly than
predicted**: the conservative engine's wrong-pruning rate *drops*
substantially with noise (`-.24` to `-.48`), not merely stays flat —
contamination reliably breaks clique validity (intact rate falls from
`.59`-`.98` to `.18`-`.48`), disabling DPI, which happens to help here
specifically because the untested edge is a genuine true edge that
should be retained.

Decision: **No evidence of the predicted cascading-error pathway in
this specific stress test.** The charter's own prediction is corrected,
not defended: the mechanism this charter set out to catch — a false
early confirmation propagating into an unrelated wrong decision — did
not occur in any of the `12,000` replicates run per condition, at any
tested `N` or `alpha`.

Rationale: The near-zero contamination rate has a clear, verified
statistical explanation (the joint-correlation requirement), not an
unexplained gap — this is a genuine, decisive negative result, not an
inconclusive one. It should not, however, be read as "cascading error
is not a real risk for this engine in general." Two specific limits of
this test, stated plainly: (1) the baseline wrong-pruning rate here is
already very high (`59%`-`84%`, from the well-known weak-signal
detection-power problem alone, unrelated to noise) — a contamination
effect would need to be large to show up as an additional increment on
top of an already-saturated baseline, and this test cannot rule out a
smaller effect being masked this way; (2) this tests exactly one
DGP (a 3-node triangle plus unrelated noise) and one contamination
pathway (spurious pairwise correlation) — a larger component, a
different noise structure (e.g., noise correlated *with* a real node
rather than independent of it), or a scenario with a lower, non-
saturated baseline wrong-pruning rate could behave differently and has
not been tested.

Consequences: This is the number the R6a milestone required, and it
reads favorably — but it answers "was cascading error detected in this
specific stress test," not "is cascading error impossible for this
engine." Any future user-facing exposure of the sequential engine should
cite this result precisely (zero contamination detected in `12,000`
replicates per condition, under the two caveats above), not
overgeneralize it to "the engine has no cascading-error risk."
Combined with D-031 (hub/overlap PROCEED), D-032-D-035 (the overlap
metric-and-calibration arc, now resolved), and this charter, the
sequential engine has cleared every precondition this project set for
it — but no charter in this line has yet tested it composed with a
larger, noisy candidate network (mirroring Stage 2's own role after
Stage 1), which remains the natural next step before any real-dataset
recommendation. `docs/validated_operating_ranges.md` should record this
result with both caveats intact, not as an unqualified clearance.

## D-037: Composed p=15 pipeline dramatically beats D-018 at N=625/700 — and finds a real bug at N=750 (R6h)

Date: 2026-08-31

Stage: R6h / Stage 4 (new engine)

Status: PROCEED at `N=625` and `N=700`. `N=750` REASSESSed for a
disclosed, structural reason — not a substantive finding about that `N`.

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4h_charter.md`

Question: Embedded in D-018's exact `p=15` noisy network, using Stage
4g's fitted `alpha(N)` formula unmodified, does the sequential engine
PROCEED where the conservative engine REASSESSed (`N=750`, TPR `.569`)
or barely PROCEEDed (`N=1500`, TPR `.817`)?

Prior specification: `docs/stage4h_charter.md` tested `N=[625, 700,
750]` — three of Stage 4g's own validated points, `750` chosen as the
primary comparison against D-018 — reusing Stage 4g's fitted formula's
single predicted `alpha` per `N`, no new selection.

Evidence: `results/generated/stage4h_composed_noise/decision.json`,
runtime 24s.

| N | status | alpha | overlap TPR | candidacy rate | conditional accuracy | contamination rate | D-018 baseline |
|---|---|---|---|---|---|---|---|
| 625 | PROCEED | `.0281` | `.986` | `.888` | `.984` | `0` | — |
| 700 | PROCEED | `.0076` | `.998` | `.835` | `.997` | `0` | — |
| 750 | REASSESS | `-.0044` | — | — | — | — | `.569` (D-018) |

**`N=625` and `N=700` PROCEED spectacularly** — composite overlap TPR
`.986` and `.998`, both **higher than D-018's own `N=1500` PROCEED**
(`.817`), using less than half the data, with zero contamination
detected and chain/fork/true-edge behavior clean throughout. The
required candidacy/conditional-accuracy decomposition confirms this is
not a repeat of D-032's artifact: candidacy is high (`.84`-`.89`, most
cross-branch pairs genuinely get evaluated) and conditional accuracy is
near-perfect (`.984`-`.997`) — a real result on both halves of the
metric, not an inflated one.

**`N=750` failed for a structural reason, not a substantive one: Stage
4g's fitted `alpha(N)` formula predicts a *negative* alpha
(`-.0044`) exactly at `N=750`**, causing every replicate to error before
producing any evidence. Checked directly: the fitted `inverse_sqrt`
curve crosses zero between `N=725` (`.0015`, still positive) and
`N=750` — and `N=750` was never itself tested as a held-out point in
Stage 4g (it was one of the six *fitting* points, not one of the five
held-out validation points), so this specific failure mode was never
caught before now. **This is a real correction to Stage 4g's own scope
claim**: `docs/stage4g_charter.md`'s "validated for interpolation within
`[300, 750]`" did not actually verify the formula returns a valid
probability at `750` itself, only at points strictly between fitting
points.

Decision: **The composed-pipeline result at `N=625`/`700` is accepted as
strong, genuine evidence** that the sequential engine achieves at these
`N` what the conservative engine could not achieve even at double the
sample size. **No claim is made about `N=750`** — it is neither PROCEED
nor a genuine REASSESS on the merits, it is an un-evaluated cell due to
a formula defect. The direct D-018 comparison this charter was built
around therefore cannot be made at the exact matching `N` — it is made
at `625`/`700` instead, which is if anything a *more* favorable
comparison (less data, still dramatically ahead of D-018's `1500`-`N`
result).

Rationale: This is the second time a fitted curve's own boundary has
produced a result its own validation didn't check (compare: D-012's
explicit `[700,3000]` "do not extrapolate" note came from a similar
awareness) — but here the boundary point was silently *inside* the
claimed range, not outside it, which is a subtler and more easily missed
version of the same discipline. The lesson generalizes: a fitted
formula's own **fitting points** are not automatically safe to
re-evaluate later — only the explicitly held-out validation points carry
that guarantee. Future `alpha(N)`-style charters should hold out (or
separately re-verify) the boundary fitting points too, not just interior
interpolation points.

Consequences: The sequential engine's composed, `p=15`, noisy-network
performance is now validated at `N=625` and `N=700` for the overlap
shape, both dramatically outperforming the conservative engine's own
composed result at more than double the sample size. `N=750` remains
untested under a working `alpha`; a small follow-up (re-fitting Stage
4g's formula with `750` itself held out and re-verified, or simply
computing and checking the single value at `750` before trusting it)
would resolve this specific gap cheaply, without needing new simulation
beyond what Stage 4e already provides. `docs/validated_operating_ranges.md`
should record the `625`/`700` results as the headline finding of this
entire overlap-shape investigation (D-026 through D-037), with the
`N=750` gap noted as an open, cheaply fixable loose end — not folded
into a false "REASSESS at N=750" reading. Stage 4c's cascading-error
caveats and the "not yet stress-tested at this network size" note still
apply before any user-facing recommendation.

## D-038: Dropping N=750 from the fitting set relocates the boundary gap rather than fixing it (R6i)

Date: 2026-08-31

Stage: R6i / Stage 4 (new engine)

Status: REASSESS. `N=400/550/625/675` PROCEED under the refit formula;
`N=725` and `N=750` both fail with an invalid (negative) predicted
alpha.

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4i_charter.md`

Question: Does re-fitting the overlap-shape `alpha(N)` formula with
`N=750` moved from the fitting set into the held-out validation set
repair D-037's finding that the formula predicts a negative alpha
exactly at `N=750`?

Prior specification: `docs/stage4i_charter.md` re-fit on five points
(`300, 500, 600, 650, 700`, dropping `750`), added a fitting-point
validity self-check, and tested the refit formula's single predicted
`alpha_hat` at six held-out `N` (`400, 550, 625, 675, 725, 750`), all
freshly simulated.

Evidence: `results/generated/stage4i_alpha_repair/decision.json`,
runtime 14.4s.

| N | status | alpha_hat | candidacy rate | conditional accuracy | true-edge FPR |
|---|---|---|---|---|---|
| 400 | PROCEED | `.1209` | `.880` | `.913` | `.0002` |
| 550 | PROCEED | `.0504` | `.885` | `.971` | `0` |
| 625 | PROCEED | `.0251` | `.878` | `.983` | `0` |
| 675 | PROCEED | `.0107` | `.832` | `.994` | `0` |
| 725 | REASSESS | `-.0023` | — | — | — |
| 750 | REASSESS | `-.0083` | — | — | — |

**The fitting-point self-check (this charter's own new safeguard)
passed cleanly** — the refit formula returns a valid probability at all
five of its own fitting `N`. The repair worked exactly as designed at
the fitting boundary. **But the held-out boundary moved, not closed**:
the refit `inverse_sqrt` curve is slightly steeper than Stage 4g's
original (parameters `(-0.358, 9.577)` vs. `(-0.344, 9.307)`), so its
zero-crossing lands *earlier* — between `N=700` and `N=725` instead of
`N=725` and `N=750`. `N=725`, which PROCEEDed cleanly under Stage 4g's
original formula (D-037's own table: `alpha=.0015`), now fails too.
`N=750` remains negative, more negative than before (`-.0083` vs.
`-.0044`).

Decision: **REASSESS.** Removing one boundary fitting point does not
repair the underlying issue — it relocates the zero-crossing rather
than eliminating it. This confirms the charter's own predeclared
REASSESS branch: "dropping one boundary fitting point was not
sufficient to fix the underlying issue... a formula is not the right
artifact for `N=750` specifically." No new `alpha(N)` formula supersedes
Stage 4g's original. `N=400/550/625/675` are validated at this refit's
values, but those four `N` were already known-good (Stage 4g's own
formula gives nearly identical positive alphas there, per D-037's
table) — this charter adds no practical coverage below `N=700`, and it
costs Stage 4g's own valid `N=725` result in the same stroke.

Rationale: A two-parameter `inverse_sqrt` curve fit on five or six
points near a genuine zero-crossing is not well-constrained right at
that crossing — small changes in which points are included shift where
the curve crosses zero by a comparable amount to the gap itself
(`~25`-`50` in `N` terms, against a `~25`-unit spacing between tested
points). This is a *sample-density* problem near the crossing, not a
fitting-target problem; the fix this charter tried (excluding one
point) cannot address a problem of that shape, because it can only ever
relocate which point is excluded, never add resolution near the
crossing itself.

Consequences: The sequential engine's overlap-shape `alpha(N)` rule
remains Stage 4g's original formula, valid on `[400, 725]` (not `[400,
750]` as previously scoped) — `N=725` and `N=750` are both now
explicitly **not** covered by any validated formula and must not be
used with a fitted `alpha`. Per this charter's own REASSESS
consequences, the right artifact for `N=750` specifically is a
**lookup value**, not a fitted extrapolation: Stage 4e's own
already-validated point at `N=750` (`alpha=.005`, `accuracy>=.80`,
`candidacy>=.80` by construction of `compute_fitting_points`'s own
selection rule) remains directly usable as a lookup value if `N=750`
evidence is ever needed again, without trusting any curve through that
region. A future charter wanting genuine coverage near `N=700`-`750`
would need **new simulated points densely spaced inside that range**
(e.g. `710, 720, 730, 740`) to properly constrain the curve near its
crossing, not a re-selection of which existing points to fit on. Stage
4h's own accepted `N=625`/`700` results (D-037) are unaffected — both
sit safely inside the now-narrower `[400, 725]` valid range.

## D-039: Dense sampling narrows the N=700-750 gap substantially but does not close it (R6j)

Date: 2026-08-31

Stage: R6j / Stage 4 (new engine)

Status: REASSESS overall, but a genuine, large partial win. `N=725` —
the exact point Stage 4i's repair broke — now PROCEEDs cleanly, along
with `705, 715, 735`. Only `N=745` (held-out) and `N=750` (a fitting
point) still produce an invalid negative alpha.

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4j_charter.md`

Question: Does adding four new fitting points densely spaced inside the
`N=700`-`750` gap (`710, 720, 730, 740`) resolve D-038's finding that
the curve's zero-crossing is a sample-density problem, not a fitting-
target problem?

Prior specification: `docs/stage4j_charter.md` fit on ten points (six
reused verbatim from Stage 4e, four new dense points, all freshly
simulated at `2,000` replicates each) and held out nine points,
including five dense-region midpoints (`705, 715, 725, 735, 745`) —
critically re-testing `N=725`, which Stage 4i's refit broke.

Evidence: `results/generated/stage4j_dense_refit/decision.json`,
runtime `370s`.

| N | region | status | alpha_hat | candidacy | conditional accuracy |
|---|---|---|---|---|---|
| 400 | coarse | PROCEED | `.1214` | `.881` | `.913` |
| 550 | coarse | PROCEED | `.0542` | `.892` | `.970` |
| 625 | coarse | PROCEED | `.0301` | `.892` | `.979` |
| 675 | coarse | PROCEED | `.0163` | `.869` | `.990` |
| 705 | dense | PROCEED | `.0087` | `.847` | `.994` |
| 715 | dense | PROCEED | `.0063` | `.809` | `.997` |
| **725** | dense | **PROCEED** | `.0039` | `.786` | `.998` |
| 735 | dense | PROCEED | `.0016` | `.696` | `.998` |
| 745 | dense | REASSESS | `-.0006` | — | — |
| 750 (fitting pt.) | — | self-check FAIL | `-.0018` | — | — |

**The dense-sampling hypothesis is confirmed, directionally and
substantially.** D-038's diagnosis was that the zero-crossing under-
determination is a density problem, testable by adding local support —
this charter did exactly that and the crossing genuinely moved, from
between `N=700`/`725` (Stage 4i, D-038) to between `N=735`/`745`, a
`~4x` narrowing of the unresolved gap (`25` units wide vs. Stage 4i's
effective `~25`-`50` unit uncertainty band, now pushed `20`-`45` units
further out). **`N=725` specifically — the casualty of Stage 4i's
repair — is fully restored and PROCEEDs with a comfortable margin**
(candidacy `.786`, accuracy `.998`, both well clear of their floors).

**It still does not fully close.** `N=745` (held out) and `N=750` (a
fitting point, caught by the self-check) both produce invalid negative
alphas. Candidacy rate is falling steadily across the dense region
(`.881` at `400` down to `.696` at `735`) even as accuracy keeps rising
— the fitted `alpha` shrinks as `N` grows (by design, to keep pace with
Fisher-z's tightening significance threshold), but a shrinking `alpha`
also screens out more cross-branch pairs before conditioning ever gets
to test them. This is the same underlying tension `alpha(N)` exists to
manage in the first place, now visibly approaching its steep end near
`N=750` rather than a new artifact of this charter's fitting.

Decision: **REASSESS**, but record the dense-region result as a
substantive partial success, not a wash. Per the charter's own partial-
success reporting requirement: this is exactly the "narrows without
closing" outcome the charter's REASSESS branch anticipated, which
"argues for even denser sampling in a future charter" rather than a
structural-discontinuity finding. The evidence here supports that
reading directly — the crossing moved in the expected direction by
roughly the amount predicted, it did not stay put or move irregularly.

Rationale: This project's four-parameter candidate forms (linear,
log-linear, power law, inverse-sqrt) are all still globally fit across
the entire `[300, 750]` range from just ten points, only four of which
sit inside the `700`-`750` gap itself. A curve with this few local
degrees of freedom near a genuine crossing will keep being sensitive to
exactly which points are included until either (a) the crossing region
has enough points that the *local* slope is well-estimated on its own,
largely independent of the far end of the range (`N=300`), or (b) a
different functional form is used that does not force one global shape
across the whole domain. Four dense points moved the needle by `~4x`;
this is consistent with diminishing but still-present returns from
finer sampling.

Consequences: **The sequential engine's overlap-shape `alpha(N)`
formula validated range is now `[400, 735]`** — a real improvement over
Stage 4i's `[400, 725]` (D-038) and Stage 4g's original `[400, 725]`
(D-037 corrected the original overbroad `[400, 750]` claim). `N=725`
is fully restored, unlike after Stage 4i. `N=740`-`750` remain
unresolved and must not be used with any fitted `alpha` — Stage 4e's
own lookup value for `N=750` (`alpha=.005`) remains the right fallback
there, per D-038's original recommendation, still standing. **A future
charter wanting to close the final `[740, 750]` gap** should add points
even more densely inside that specific 10-unit-wide interval (e.g.
`742, 744, 746, 748`) rather than repeating this charter's `10`-unit
spacing — the diminishing-but-present-returns pattern observed here
suggests this would work, at increasing simulation cost for
diminishing practical value (the interval left is now only `10` units
wide, `1.3%` of the full `[400, 750]` validated range). This is likely
not worth pursuing further unless a specific downstream use needs
`N=740`-`750` exactly. Stage 4h's accepted `N=625`/`700` results
(D-037) remain unaffected throughout.

## D-040: Overlap's miscalibration does not generalize — D-012's existing formula PROCEEDs across every shape/strength cell tested (R6k)

Date: 2026-08-31

Stage: R6k / Stage 4 (new engine)

Status: PROCEED. All 36 cells (3 motifs x 4 strengths x 3 sample sizes)
PROCEED using D-012's already-frozen `alpha(N)` formula, unmodified, no
new fitting.

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4k_charter.md`

Question: Does D-012's existing `alpha(N)` formula — built for the
conservative engine, reused unmodified here — generalize to the
sequential engine across a grid of shapes (chain, fork, hub-with-2-
children) and signal strengths (`0.30`-`0.70`, bracketing overlap's own
historically-difficult `~.135` correlation from both sides), or does
overlap's D-034 miscalibration reflect a general weak-signal property
of the engine?

Prior specification: `docs/stage4k_charter.md` tested `36` cells (`3
motifs x 4 strengths x 3 N in [750, 1000, 1500]`, all inside D-012's
own validated `[700, 3000]` range), gated on `conditional_accuracy
>= .80` (margin `.02`) and true-edge FPR `<= .10` (margin `.02`), `1,000`
replicates per cell.

Evidence: `results/generated/stage4k_shape_strength_sweep/decision.json`,
runtime `18.4s`.

**All 36 cells PROCEED — a clean, unqualified result.** Candidacy rate
`.86`-`1.0` throughout (rising with `N` as expected, and lowest at
`strength=0.30`, the weakest and hardest cell tested); conditional
accuracy `.82`-`.94`, comfortably above the `.80` floor in every cell.
No re-fitting, no per-shape or per-strength recalibration — the exact
same formula, the exact same three `alpha` values (one per `N`,
`.1476`/`.1313`/`.1084`), applied identically across all three motifs
and all four strengths.

**Margins are real but some are thin, worth naming explicitly, not
just citing the aggregate PROCEED**: the six smallest margins all occur
at `N=750` (the general floor point, where `alpha` is largest and the
formula has the least room to spare): `hub, strength=0.70, N=750`
(margin `.022`, barely above the `.02` requirement, accuracy `.822`);
`chain, strength=0.50, N=750` (`.042`); `chain, strength=0.70, N=750`
(`.044`); `hub, strength=0.50, N=750` (`.044`); `fork, strength=0.50,
N=750` (`.048`). Every one of these clears the gate, but `N=750` is
where this formula would first show trouble if it were going to, and
it is worth watching if any future charter pushes this combination
harder (e.g. a stress test at `N` closer to `700`, D-012's own lower
boundary).

**One mildly counterintuitive but plausible pattern**: conditional
accuracy at `N=750` is not monotonically increasing with `strength` —
e.g. hub's accuracy is `.856` at `strength=.40` but only `.822` at
`strength=.70`. A larger true indirect correlation being *harder* to
correctly prune, not easier, makes sense once conditioning is
considered: a stronger marginal correlation leaves a larger residual
partial correlation after conditioning on the shared cause, which is
more likely to still cross the significance threshold at a fixed
`alpha` — the same reason `alpha(N)` exists in the first place, now
visible along the strength axis too, not just the `N` axis. This is
descriptive, not a gate failure anywhere, and not further investigated
by this charter.

Decision: **PROCEED, and treat this as the answer to the R6a
milestone's broader shape/signal-strength precondition for chain, fork,
and hub-type shapes.** Overlap's D-032-D-039 miscalibration story does
**not** generalize — it reflects something specific to the overlap
shape's own DGP (its five-variable, dual-triangle topology and fixed
`-0.25` precision structure), not a systemic weak-signal problem with
the sequential engine. D-012's existing, already-frozen formula — built
years before the sequential engine existed, using triads only — needed
no changes at all to cover this entire new grid.

Rationale: This charter deliberately tested strengths on both sides of
overlap's own difficulty level (`0.30` implies indirect correlation
`.09`, weaker than overlap's `~.135`; `0.40` implies `.16`, just above
it) specifically so a null result here could not be dismissed as "just
not weak enough." `strength=0.30` is if anything a harder case than
overlap ever posed, and it still PROCEEDs cleanly (candidacy `.86`-
`.98`, accuracy `.90`-`.94` — actually the *highest* accuracy band of
any strength tested, since the induced indirect correlation is weak
enough that few pairs risk incorrectly surviving conditioning once they
do clear screening). Combined with the DGP's structural symmetry (every
motif reduced to exactly two direct edges and one indirect pair), this
is a genuinely apples-to-apples test, not one favorable to a particular
outcome.

Consequences: **Chain, fork, and hub(2-children) motifs are now
validated for the sequential engine's isolated conditioning at `N in
[750, 1000, 1500]` across `strength in [0.30, 0.70]`, using D-012's
existing formula unmodified** — no new alpha(N) rule needed for these
shapes. This substantially derisks a user-facing recommendation for
these shape types specifically, though **it still does not authorize
one on its own**: this charter is isolated-only (no screening, no
noise, no composed pipeline), and Stage 4c's cascading-error caveats
were tested only for the triangle shape, not these three. **The
overlap shape remains the one exception requiring its own dedicated
`alpha(N)` treatment** (Stage 4g/4i/4j, validated `[400, 735]`) — this
result reinforces, rather than undermines, treating that as a shape-
specific finding rather than evidence of a broader defect. A natural
next step, if pursued, would be a composed/noisy version of this same
sweep (mirroring Stage 4h's own treatment of overlap), to close the
isolated-vs-composed gap for chain/fork/hub the way Stage 4h closed it
for overlap.

## D-041: Composed/noisy chain-fork-hub PROCEEDs cleanly on every cell — the isolated-vs-composed gap closes without recalibration (R6l)

Date: 2026-08-31

Stage: R6l / Stage 4 (new engine)

Status: PROCEED. All 6 cells (`2` strengths x `3` sample sizes) PROCEED,
using D-012's already-frozen `alpha(N)` formula, unmodified, on a new,
noisy `p=15` chain/fork/hub network.

Decision timing: Predeclared gate evaluated after results, per
`docs/stage4l_charter.md`

Question: Does D-012's existing `alpha(N)` formula, already validated
in isolation for chain/fork/hub (D-040), continue to hold once embedded
in a full `p=15` network with `96` competing null pairs and noise
columns — the composed-pipeline step Stage 4h took for overlap — or
does screening pressure expose a gap the isolated test could not see
(mirroring D-018's own finding for the conservative engine on the
overlap shape specifically)?

Prior specification: `docs/stage4l_charter.md` tested `6` cells
(`strength in [0.30, 0.50]` x `N in [750, 1000, 1500]`, Stage 4k's own
exact grid), gated on chain/fork/hub indirect TPR `>= .80`, true-edge
FPR `<= .10`, and final false-edge rate not exceeding screening's own
rate by more than `.01`, `2,000` replicates per cell.

Evidence: `results/generated/stage4l_composed_noise_chain_fork_hub/
decision.json`, runtime `51.0s`.

| strength | N | status | chain TPR | fork TPR | hub TPR | true-edge FPR | screening FER | final FER |
|---|---|---|---|---|---|---|---|---|
| 0.30 | 750 | PROCEED | `.913` | `.926` | `.914` | `0` | `.148` | `.129` |
| 0.30 | 1000 | PROCEED | `.935` | `.917` | `.923` | `0` | `.132` | `.116` |
| 0.30 | 1500 | PROCEED | `.914` | `.920` | `.905` | `0` | `.108` | `.097` |
| 0.50 | 750 | PROCEED | `.855` | `.869` | `.857` | `0` | `.149` | `.120` |
| 0.50 | 1000 | PROCEED | `.864` | `.870` | `.886` | `0` | `.130` | `.107` |
| 0.50 | 1500 | PROCEED | `.895` | `.872` | `.880` | `0` | `.109` | `.091` |

**All 6 cells PROCEED — a clean, unqualified result, same as Stage 4k's
isolated sweep.** All indirect TPRs comfortably above `.80` (smallest
margin `.055`, `strength=.50, N=750`); true-edge FPR exactly `0`
throughout; final false-edge rate always *below* the screening-stage
rate (never triggers the `.01` tolerance check, since conditioning only
ever removes candidates, never adds them). No isolated-vs-composed
comparison table is produced (per this charter's own reporting
requirement, that table is generated only for failing cells, and none
failed).

**The same counterintuitive strength pattern D-040 noted reappears
here**: TPR at `strength=0.30` (`.91`-`.94`) is *higher* than at
`strength=0.50` (`.86`-`.90`) across every `N`, the same direction as
Stage 4k's isolated result. This is consistent with D-040's own
explanation (a stronger true correlation leaves a larger residual
partial correlation after conditioning, more likely to still cross the
significance threshold) rather than a new, composed-pipeline-specific
effect — the pattern transfers unchanged from isolation to composition,
which is itself a small piece of corroborating evidence that nothing
qualitatively different is happening once noise and competition are
added.

Decision: **PROCEED.** This closes the isolated-vs-composed gap for
chain/fork/hub the way Stage 4h closed it for overlap — but with a
different outcome: Stage 4h needed Stage 4g's dedicated per-shape
`alpha(N)` recalibration to succeed at `N=625`/`700` (D-037); this
charter needed **no new fitting at all**, the exact same formula and
the exact same three `alpha` values Stage 4k already used in isolation
carried over unchanged into a `96`-null-pair, `6`-noise-column,
screening-realistic setting.

Rationale: The charter's own diagnostic apparatus (isolated-vs-composed
candidacy/accuracy comparison) was built specifically to distinguish a
screening-detection-power failure (candidacy dropping under
competition, mirroring D-018) from a conditioning-mechanism failure —
neither triggered, because nothing failed. This is a stronger, cleaner
result than could have been assumed in advance: Stage 1's original
motif families (chain, fork, hub) apparently do not share overlap's
sensitivity to embedding in a larger, noisier network, at least across
the strength/`N` range tested here.

Consequences: **Chain, fork, and hub(2-children) are now validated for
the sequential engine's composed, noisy conditioning at `N in [750,
1000, 1500]`, `strength in [0.30, 0.50]`, using D-012's existing
formula with no shape-specific recalibration** — the same formula
already used throughout Stage 2/3 for the conservative engine. Combined
with D-040, **the R6a milestone's broader shape/signal-strength
precondition is now substantially satisfied for these three shape
types**, leaving Stage 4c's cascading-error stress test (tested only on
the triangle shape so far, per its own disclosed caveats) as the one
remaining precondition before any user-facing recommendation for
chain/fork/hub-type shapes specifically. The overlap shape's own
dedicated `alpha(N)` treatment (Stage 4g/4i/4j, validated `[400, 735]`)
remains necessary and unaffected — this result does not retroactively
simplify or change that shape's requirements, it confirms overlap was
the DGP-specific exception, not chain/fork/hub. Not tested here: signal
strengths outside `[0.30, 0.50]`, hub with more than 2 children (Stage
4b/4d's own hub result, using a different child count, is not touched
by this charter), or any `p` other than `15`.

## D-042: Chain/fork/hub show a real, small cascading effect Stage 4c's triangle did not — likely explained by the triangle's own asymmetric design (R6m)

Date: 2026-08-31

Stage: R6m / Stage 4 (new engine). **Descriptive, no gate**, per this
charter's own established rationale — no established acceptable
cascading-error rate exists anywhere in this project.

Status: Data generated and reported per `docs/stage4m_charter.md`. Not
a PROCEED/REASSESS decision (this charter has no gate); the finding
itself is the deliverable.

Decision timing: Predeclared sub-questions (Q1/Q2/Q3) evaluated after
results, per `docs/stage4m_charter.md`.

Question: Does Stage 4c's triangle-shape finding (D-036: no meaningful
noise-attributable increase in wrong-pruning) generalize to chain,
fork, and hub(2-children) at a deliberately weak, uniform signal
strength (`0.15`)?

Prior specification: `docs/stage4m_charter.md` tested `36` cells (`3`
motifs x `3` N `in [100, 200, 300]` x `2` alpha `in {.05, .10}` x `2`
noise_count `in {0, 5}`), pooling wrong-pruning across both direct
edges per motif, `2,000` replicates per cell, both engines on identical
paired data.

Evidence: `results/generated/stage4m_cascading_error_chain_fork_hub/
summary.json`, runtime `87.2s`.

**Q1 — Does noise contamination measurably increase the sequential
engine's wrong-pruning rate? Answer: yes, a small but real effect,
unlike D-036's clean null.** Across all `18` (motif, N, alpha) cells,
the sequential wrong-prune-rate delta (`noise=5` minus `noise=0`) is
**positive in `17` of `18` cells and exactly zero in the remaining
one — never negative** (sign-test `p < .001` against the null of no
systematic direction). Magnitude is small in absolute terms: mean delta
`.0017`, largest single-cell delta `.0045` (chain, `N=100, alpha=.10`).

**Q2 — Does the conservative engine show the same pattern? Answer: no
— the mirror-image pattern, exactly as D-036 predicted.** Every one of
the same `18` cells shows a **negative** conservative delta (range
`-.0012` to `-.0070`) — noise contamination *reduces* the conservative
engine's wrong-pruning rate, because a stray noise correlation breaks
clique completeness for that component, disabling DPI and letting the
untested (genuinely real) edge pass through unpruned. The `conservative
clique-intact rate` collapses sharply from `noise=0` to `noise=5` in
every cell (e.g., chain `N=300, alpha=.10`: `.093` to `.021`),
confirming the mechanism directly.

**Q3 — When the sequential engine wrongly prunes under `noise=5`, is a
noise column specifically implicated? Answer: yes, consistently, at a
low but non-trivial rate.** Ranges `.0007`-`.0157` across all cells and
motifs (no clean monotonic pattern by `N` or `alpha`) — this is the
direct mechanistic confirmation that when the small excess wrong-
pruning occurs, a noise variable is disproportionately often part of
the reason, not coincidental.

**Cross-motif comparison**: chain (`.0015`), fork (`.0018`), and hub
(`.0017`) show near-identical mean deltas — **no motif is meaningfully
more or less susceptible than the others**; the effect is a property of
the weak-uniform-strength condition, not a specific topology.

**Why this diverges from D-036, with a specific mechanistic
explanation, not just a different number:** Stage 4c's triangle fixture
is **structurally asymmetric** — the weak tested edge (`-.08` partial
correlation) shares the DGP with two much stronger anchor edges (`-.45`,
`-.25`). Those anchors reliably out-rank any noise column in the `|z|`-
based confirmation order, so they become the weak edge's tested
neighbors almost every time — noise essentially never gets the chance
to be selected as a "confirmed shared neighbor" before a genuine anchor
edge already is. **Chain/fork/hub's `strength=0.15` condition has no
such anchor**: every edge, real and spurious alike, is comparably weak,
so a noise column has a real, if small, chance of out-ranking a genuine
edge in the confirmation order and becoming available as a conditioning
variable. D-036's reassuring null was in part a property of the
triangle's own asymmetric design providing structural protection, not
evidence the cascading pathway is universally negligible.

Decision: **No gate, per this charter's design — the finding is
reported plainly.** This is the first Stage 4 result to actually detect
the cascading-error pathway the sequential engine's design has been
flagged as risking since planning. It is small in absolute magnitude
(well under half a percentage point at any tested cell) and occurs
against an already-high baseline wrong-pruning rate (`.17`-`.68`, since
`strength=0.15` is deliberately hard) — but it is statistically robust
(`17/18` cells same direction) and mechanistically explained (Q3), not
an artifact of one noisy cell.

Rationale: This charter's uniform-weak-strength design was chosen
specifically because it removes the structural protection Stage 4c's
asymmetric triangle had — the goal was to test the pathway somewhere it
could actually show up, and it did. This is exactly the kind of result
the R6a milestone's cascading-error precondition exists to surface: not
a blanket "safe" or "unsafe" verdict, but a quantified, disclosed number
tied to a specific, understood condition (uniformly weak signal,
comparable to overlap's own historically weak correlation) rather than
every use of the engine.

Consequences: **Any future user-facing exposure of the sequential
engine, for any shape, must disclose this small but real cascading-
error rate specifically for uniformly-weak-signal conditions** — D-036's
reassuring result should not be generalized past the triangle's own
asymmetric design that likely produced it. For shapes/strengths with a
clear strong-vs-weak asymmetry (mirroring the triangle), D-036's near-
zero finding may still be a reasonable expectation; for shapes where
all edges are comparably weak (mirroring overlap's own historical
difficulty, and this charter's `strength=0.15` condition), a small,
non-zero cascading effect should be assumed present until measured
otherwise. Combined with D-040/D-041, chain/fork/hub now have every
named R6a milestone precondition addressed — the answer is not a clean
"no risk" the way the triangle's own D-036 result was, but a specific,
quantified, small risk, which is itself a complete and honest answer to
the milestone's question. This charter tests only one weak-strength
condition, one noise-column count (`5`), and one contamination pathway
(independent noise) — the magnitude at other strengths, larger noise
counts, or noise correlated with a real node remains untested.

## D-043: Overlap's noise-driven cascading effect is a clean null like the triangle's — but a new, noise-independent structural pathway is found instead (R6n)

Date: 2026-08-31

Stage: R6n / Stage 4 (new engine). **Descriptive, no gate**, per Stage
4c/4m's own established rationale.

Status: Data generated and reported per `docs/stage4n_charter.md`. Not
a PROCEED/REASSESS decision (no gate); the finding is the deliverable.

Decision timing: Predeclared sub-questions (Q1/Q2/Q3/Q4) evaluated
after results, per `docs/stage4n_charter.md`.

Question: Does overlap — the shape with this engine's single largest
claimed win (D-037) — show a noise-driven cascading effect like Stage
4m's chain/fork/hub (D-042), or a clean null like Stage 4c's triangle
(D-036)? And does overlap's own structure (the opposite-triangle nodes,
a pathway unique to this DGP) contribute a *different* kind of
cascading risk, independent of noise?

Prior specification: `docs/stage4n_charter.md` tested `12` cells (`N in
[100, 200, 300]` x `alpha in {.05, .10}` x `noise_count in {0, 5}`),
pooling wrong-pruning across overlap's `6` true direct edges, `2,000`
replicates per cell, both engines on identical paired data, explicitly
making no directional Q1 prediction in advance.

Evidence: `results/generated/stage4n_cascading_error_overlap/
summary.json`, runtime `68.5s`.

**Q1 — clean null, matching Stage 4c's triangle, not Stage 4m's
chain/fork/hub.** Sequential delta (`noise=5` minus `noise=0`) is
`.0000`-`.0001` at every one of the `6` (N, alpha) cells — no
measurable noise-attributable effect. This matches the charter's own
stated hypothesis: overlap's direct edges (`-0.25`, moderate strength)
sit far closer to the triangle's strong-anchor regime than to Stage
4m's deliberately weak `strength=0.15` condition, so noise columns
essentially never out-rank a genuine edge for early confirmation.

**Q2 — same mirror pattern as both prior charters.** Conservative delta
is negative in every cell (`-.0013` to `-.0128`), the same clique-
breaking mechanism confirmed a third time, now DGP-independent across
three structurally distinct fixtures (asymmetric triangle, uniform-weak
motifs, moderate-uniform overlap).

**Q3 — near-zero, consistent with Q1's clean null.** Noise-implication
rate `.0000`-`.0048` across cells — there is very little wrong-pruning
to implicate anything in, since the baseline wrong-prune rate itself
falls sharply with `N` (`.21` at `N=100` down to `.0018` at `N=300,
alpha=.10` — overlap's moderate-strength direct edges are considerably
easier to detect correctly than Stage 4c/4m's deliberately weak test
conditions, visible directly in the three-way comparison table).

**Q4 — the new question this charter added finds something the noise
axis alone could not: a real, small, noise-***independent*** structural
pathway.** The opposite-triangle-node implication rate is
**consistently nonzero at every `N`/`alpha` cell** (`.0204`-`.0625`) and,
critically, **identical between `noise_count=0` and `noise_count=5`** at
every matching cell — direct confirmation that this pathway does not
require noise to exist. When the sequential engine wrongly prunes a
true direct edge, a node from the *opposite* triangle (overlap's own
shared-node structure, not an injected variable) is implicated in
roughly `2%`-`6%` of those wrongly-pruned instances, in a noise-free
network just as much as a noisy one.

Decision: **No gate, per this charter's design.** Overlap's answer on
the *noise* axis is reassuring and matches the triangle's own clean
result, not chain/fork/hub's small-but-real effect — consistent with
overlap sitting in the "protected," strong-enough-edges regime Stage
4m's own explanation predicted. But Q4 surfaces a genuinely new finding
neither Stage 4c nor Stage 4m's designs could have found, since neither
DGP has a structural "opposite branch": a small, structural cascading
pathway specific to overlap's own shared-node topology, present with or
without noise.

Rationale: Q4 exists because overlap's DGP is not just "another weak-
signal shape" — it is the only Stage 4 fixture with a second triangle
sharing a node, giving the engine a structurally plausible *wrong*
explanation (the opposite triangle's own nodes) available as a
candidate "shared confirmed neighbor" independent of any noise. That
this rate is flat across `noise_count` is the direct evidence it is a
structural, not stochastic, effect — adding noise columns does not
meaningfully compete with or crowd out this pathway, it simply doesn't
interact with it.

Consequences: **Overlap's headline result (D-037: `N=625`/`700` beating
the conservative engine's `N=1500`) is not threatened by noise-driven
cascading error** — that specific risk is now measured and negligible,
matching D-036's own triangle finding. **A small, structural, noise-
independent risk is disclosed instead**: roughly `2%`-`6%` of wrongly-
pruned direct edges (themselves already rare at the `N` overlap is
actually used at) trace to the opposite triangle's own nodes, not to
external noise. Any future user-facing exposure of the sequential
engine for overlap-shaped (shared-node, multi-cluster) DGPs should
disclose this specific, quantified structural pathway alongside the
noise-based number, since it is a different mechanism requiring its own
mention, not a restatement of D-036/D-042's noise-focused findings.
Combined with D-037-D-042, the overlap shape now has every named R6a-
adjacent cascading-error question answered as thoroughly as chain/fork/
hub's. This charter tested only `noise_count in {0, 5}` and one
contamination pathway per Stage 4c/4m's own precedent; whether the
opposite-triangle rate changes at larger `N` (inside overlap's own
validated `[400, 735]` `alpha(N)` range, not tested here since this
charter deliberately used Stage 4c/4m's smaller, harder `N` grid)
remains open for a future charter if the magnitude ever becomes
practically relevant.

## D-044: R6a milestone resolved — sequential engine recommended with disclosed caveats for four shapes, within tested ranges (R6a Resolution)

Date: 2026-08-31

Stage: R6a Resolution / Stage 4 (synthesis, no new evidence)

Status: Synthesis complete. Deliverable: `docs/stage4o_recommendation.md`.

Decision timing: Rubric fixed before the verdict was drafted, per
`docs/stage4o_charter.md`. No new simulation; every claim traces to
D-030 through D-043.

Question: Does the sequential/greedy conditioning engine clear the
outline's own R6a milestone (materially lower `N` than the conservative
engine, without an unacceptable cascading-error rate)?

Decision: **Cleared per-shape, with disclosed caveats, for overlap,
chain, fork, and hub(2-children), each within its own specifically
tested `N`/strength range** — not a blanket clearance, and not
extendable to any untested shape, `N`, strength, or `p`. Full detail,
including the per-shape rubric table, the `N`-by-method and effect-size-
by-method viability matrices, and the explicit boundary-of-recommendation
section, is in `docs/stage4o_recommendation.md` (not restated here).

Rationale: The rubric was mechanical specifically so this entry would
not become a place to round a mixed record up to a cleaner verdict than
it earned — every shape carries at least one disclosed, quantified
caveat (overlap: a small structural cascading pathway independent of
noise, D-043; chain/fork/hub: a small noise-driven cascading effect,
D-042), and the recommendation document says so explicitly rather than
only in the fine print.

Consequences: `docs/stage4o_recommendation.md` is now the authoritative
answer to "should this engine be used, and for what" — future work
should point to it rather than re-deriving the answer from the raw
D-030-D-043 arc. It surfaces five prioritized next steps (most
importantly: closing overlap's isolated-vs-composed testing gap, and
testing this engine against Stage 3's bootstrap-stability rescue
mechanism, which has never been tried with it at all) but does not
authorize any of them — each remains its own future charter's decision.
This closes the R6a milestone as project governance; it does not close
the project, and does not touch the outline's separate, unstarted R6
milestone (broad benchmarking against incumbents).

## D-045: Canonical benchmark reveals two disclosure-worthy findings — a thin, sampling-sensitive margin at overlap's own N=1500, and a metric caveat on the sequential engine's clean sweep (R6p)

Date: 2026-08-31

Stage: R6p / Stage 4 (public benchmark, both engines, both networks)

Status: Data generated per `docs/stage4p_charter.md`. Hub-based network
is clean, as expected. Overlap-based network surfaces two findings that
must be disclosed alongside this benchmark's own headline table, not
smoothed over.

Decision timing: Gate evaluated after results, per
`docs/stage4p_charter.md`. Both findings below were not predicted in
advance — the charter explicitly anticipated overlap/sequential
divergence from the specialized formula below `N=750`, but not these
two specific patterns.

Evidence: `results/generated/stage4p_canonical_benchmark/decision.json`,
runtime `716s`.

**Hub-based `p=15` network: clean, as the charter's own design intended.**
Both engines PROCEED at every `N` except one thin, isolated miss
(conservative, `N=500`, fork indirect TPR `.792`, `.008` below the
`.80` floor — surrounded by clean PROCEEDs at `N=400` and `N=600`, read
as an isolated sampling-noise miss, not a trend). This is new evidence:
the conservative engine had never been run on this exact chain/fork/hub
network before this charter.

**Overlap-based `p=15` network, finding 1 — the conservative engine
REASSESSes at every tested `N`, including `N=1500`, apparently
diverging from D-018's own recorded `N=1500` PROCEED.** Composite
overlap TPR: `.728`(`400`), `.648`(`500`), `.599`(`600`), `.579`(`750`),
`.666`(`1000`), `.791`(`1500`) — a U-shaped dip, new information, since
D-018 only ever tested `N=750` and `N=1500` and never saw the
intermediate points. **The `N=1500` result specifically (`.791`) sits
just under the `.80` gate, where D-018 recorded `.817`** — a `.026`
difference. This is not read as a contradiction: D-018's own `N=1500`
margin was already thin (`.817 - .80 = .017`, smaller than its own
`N=750` REASSESS's distance from the line), and this charter draws an
**independently seeded sample** (a new stream tag, not a replay of
Stage 2d's own seeds) — a draw landing on the other side of an already-
thin margin is plausible sampling variation, not evidence D-018 was
wrong. The new, disclosure-worthy finding is that **this margin is
thinner and more sampling-sensitive than D-018's own binary REASSESS-
at-750/PROCEED-at-1500 framing suggested**, and the newly-visible dip at
intermediate `N` (worst at `750`, exactly the point already flagged as
REASSESS) is itself new information about the shape of this specific
weak-signal problem across `N`, not previously observed.

**Overlap-based `p=15` network, finding 2 — the sequential engine
PROCEEDs at every tested `N` including `400`-`600`, but this specific
result carries a known metric caveat and should not be read as beating
or superseding Stage 4g/4i/4j's own `[400, 735]` finding.** This
charter's gate uses the same coarse, pooled indirect-edge TPR metric
Stage 2d/4h/4l always used (`_score`'s own `_tpr` computation: a pair
that never becomes a candidate defaults to "pruned" in the final
adjacency, exactly as a correctly-conditioned pair would) — **this is
precisely the non-detection-conflation artifact D-032 diagnosed and
built the candidacy-conditional metric to correct.** Direct check at
`N=400`: `58.4%` of validation replicates already score a perfect
`1.0` composite TPR, true-edge FPR is exactly `0`, and the DGP-specific
candidacy decomposition this benchmark does not compute would be needed
to confirm how much of this apparent strength reflects genuine correct
conditioning versus pairs that simply never cleared screening. **This
charter's own overlap/sequential PROCEED cells should therefore be read
as descriptive, not as independently confirming viability below `N=400`
the way Stage 4g/4i/4j's properly-decomposed metric does within its own
`[400, 735]` range** — this is exactly the caveat the charter's own
consequences section anticipated in spirit (divergence from the
specialized findings is informative, not a contradiction), just
manifesting as an inflated-agreement risk rather than a disagreement.

Decision: **Report both findings plainly in the benchmark's own
public-facing presentation, not only in this entry.** The side-by-side
table stands as generated evidence, but any external presentation of
this benchmark must carry: (1) a note that overlap/conservative's
`N=1500` cell reflects a thin, sampling-sensitive margin, not a
retraction of D-018; (2) a note that overlap/sequential's composite-TPR
PROCEED cells use a metric known to be conflatable with non-detection,
and Stage 4g/4i/4j's own decomposed `[400, 735]` finding remains the
more trustworthy source for that specific shape/engine combination.

Rationale: This project's own established discipline (D-032's own
history) is exactly why this pattern was worth catching rather than
reporting the clean-looking table at face value. Building a consistent,
public-facing benchmark on a coarser, more comparable metric was a
deliberate, disclosed tradeoff in `docs/stage4p_charter.md` (needed for
apples-to-apples comparison against the conservative engine, which
has no direct "candidacy" concept); this entry is the disclosure that
tradeoff's own consequences require.

Consequences: `docs/stage4o_recommendation.md`'s own per-shape verdicts
and `N`-threshold matrix are **unaffected** — this benchmark does not
change any prior charter's PROCEED/REASSESS finding, per
`docs/stage4p_charter.md`'s own consequences section. The benchmark
report and any future public-facing use of it must carry both caveats
above. A genuine follow-up, if the thin `N=1500`/overlap/conservative
margin ever matters for a specific decision, would be a dedicated
repeated-sampling charter (multiple independent seeds at exactly
`N=1500`) to characterize the margin's own sampling distribution rather
than trusting either single draw (D-018's or this charter's).

## D-046: N=1750/2000 give the conservative engine a confident overlap floor; the sequential engine's composite-TPR sweep was mostly honest, with a small, shrinking gap (R6q)

Date: 2026-08-31

Stage: R6q / Stage 4 (benchmark repair, two independent parts)

Status: Both parts complete. Part A: PROCEED with comfortable margin at
both new `N`. Part B: descriptive re-scoring, `decomposed-metric
PROCEED` at every `N`.

Decision timing: Both gates/comparisons evaluated after results, per
`docs/stage4q_charter.md`.

Question: (A) Does the conservative engine reach a genuinely confident
threshold on the overlap-based `p=15` network past `N=1500`'s thin
margin? (B) How much of the sequential engine's clean composite-TPR
sweep on the same network (Stage 4p, D-045) reflects genuine
correctness versus non-detection inflation (D-032)?

Evidence: `results/generated/stage4q_a_higher_n/decision.json` (runtime
`29.4s`), `results/generated/stage4q_b_decomposed_metric/comparison.json`
(runtime `72.3s`).

**Part A — yes, a genuinely confident floor exists at `N=1750`.**

| N | status | overlap TPR | margin above .80 | comfortable (`>=.032`)? |
|---|---|---|---|---|
| 1750 | PROCEED | `.839` | `.039` | yes |
| 2000 | PROCEED | `.850` | `.050` | yes |

Both new `N` clear not just the `.80` gate but the `.032` D-011-scale
comfort threshold, with margin *increasing* from `1750` to `2000` — the
expected shape of a genuine floor, not a knife-edge crossing. **`N=1750`
is the recommended threshold for the conservative engine on this
specific weak-signal shape at `p=15`** going forward, replacing
`N=1500` as the point anyone should actually rely on, though `N=1500`'s
own PROCEED (D-018) is not retracted — it remains a valid, just thin,
result.

**Part B — the composite metric's non-detection inflation is real but
small, and shrinks toward zero as `N` grows.**

| N | composite TPR | candidacy rate | conditional accuracy | gap |
|---|---|---|---|---|
| 400 | `.869` | `.922` | `.858` | `.011` |
| 500 | `.873` | `.955` | `.867` | `.006` |
| 600 | `.866` | `.974` | `.863` | `.004` |
| 750 | `.867` | `.991` | `.865` | `.001` |
| 1000 | `.883` | `.998` | `.883` | `.0003` |
| 1500 | `.894` | `1.000` | `.894` | `.0000` |

**Conditional accuracy clears `.80` at every single `N`**, including
`400` (`.858`) — Stage 4p's own composite-TPR PROCEED sweep (D-045) was
**not** primarily an artifact; it was mostly genuine, with a small,
quantified inflation (largest at `N=400`, `.011`, about `1.1`
percentage points) that shrinks as candidacy rate approaches `1.0`
(essentially every cross-branch pair clears screening by `N=1000`).

Decision: **Both findings resolve, rather than deepen, D-045's own
disclosed concerns.** Part A gives the project a genuinely confident
`N` recommendation for the conservative engine on this shape
(`N=1750`), not just a barely-passing one. Part B confirms the
sequential engine's own composite-TPR sweep on overlap was trustworthy
in direction and magnitude, even though the specific metric used was
known to carry inflation risk — the actual risk realized was small.

Rationale: Both parts were designed to directly test, not assume, the
size of the problems D-045 flagged, rather than either dismissing them
or treating them as more severe than warranted without measurement.
That the sequential/overlap gap shrinks monotonically with `N`
(matching candidacy rate's own approach to `1.0`) is the expected
signature of a genuine non-detection effect fading as screening power
increases, not a coincidence.

Consequences: `docs/validated_operating_ranges.md` should record
`N=1750` as the conservative engine's own confident recommendation for
the overlap shape at `p=15` (superseding `N=1500` as the practical
recommendation, without retracting `N=1500`'s own valid-but-thin
PROCEED). Part B's comparison table should be cited wherever Stage 4p's
own overlap/sequential sweep is referenced, so the small, quantified
non-detection gap travels with the result rather than being either
ignored or overstated. `docs/stage4o_recommendation.md`'s own per-shape
verdicts remain unaffected — this charter, like Stage 4p before it, is
supplementary evidence, not a change to any prior PROCEED/REASSESS
finding.

## D-047: MINT's conservative engine outperforms EBICglasso on noisy composed networks, matches it on the clean triangle (R6)

Date: 2026-09-01

Stage: R6 / Stage 5a (first comparator-benchmarking charter)

Status: Descriptive verdict, no PROCEED/REASSESS gate — per
`docs/stage5a_charter.md`'s own decision structure, this charter tests
an external comparator, not MINT's own correctness, so the project's
PROCEED/REASSESS/STOP vocabulary does not apply here.

Decision timing: Predeclared before results — the acceptable-recovery
threshold (mean validation F1 `>= .90`, held at every larger tested
`N`) was fixed in `mintnet.experiments.stage5a_reporting`'s own module
docstring before the full-scale run was launched.

Question: On strictly Gaussian data — EBICglasso's own native
assumption class and MINT's own fully validated territory — does
MINT's conservative engine (per-edge screening + conditional-
independence pruning) occupy a materially different sample-efficiency
or accuracy position than EBICglasso (graphical lasso + extended-BIC
penalty selection, `gamma=.5`), on DGP shapes already characterized
across Stages 1-4?

Prior specification: `docs/stage5a_charter.md`. Five shapes (composed,
noisy `p=15` chain/fork/hub; composed, noisy `p=15` shared-node
overlap; three-node balanced/moderate/strong triangle, no noise), `N
in [400, 500, 600, 750, 1000, 1500, 1750]`, `2,000` replicates per
cell, MINT using D-012's general `alpha(N)` formula uniformly (an
implementation-time scope simplification, documented in `stage5a.py`'s
own module docstring — overlap's specialized formula from Stage
4g/4i/4j is a fitted curve object, not a closed-form constant, and its
fitting inputs are not present in this worktree).

Evidence: GitHub Actions run
`https://github.com/imh-ds/mintnet/actions/runs/33480707225` (35
matrix shards, one per `(dgp, N)` cell, plus one aggregation job — run
on CI rather than locally after a single-machine multi-process attempt
stalled on BLAS-thread oversubscription well past its estimated
runtime). Aggregated evidence: `raw_metrics.csv` (280,000 rows),
`report.json`, `stage5a_report.md`, `f1_by_n_by_shape.png`.

| DGP shape | MINT floor N | EBICglasso floor N | Verdict |
|---|---|---|---|
| chain_fork_hub | 400 | none (never reaches `F1>=.90` on this grid) | MINT more sample-efficient |
| overlap | 400 | none (never reaches `F1>=.90` on this grid) | MINT more sample-efficient |
| triangle_balanced | 400 | 400 | no material difference |
| triangle_moderate | 400 | 400 | no material difference |
| triangle_strong | 400 | 400 | no material difference |

**On the two composed, noisy `p=15` networks, MINT is not just
somewhat ahead — EBICglasso never clears the acceptable-recovery bar
anywhere on the tested grid.** On `chain_fork_hub`, MINT's F1 runs
`.954`-`.966` across `N`, essentially flat and already high at `N=400`
(recall is perfect, `1.000`, at every `N` for both methods — the gap is
entirely in precision: MINT `.917`-`.939` vs. EBICglasso `.731`-`.762`,
i.e. EBICglasso retains roughly `2`-`3x` as many false edges).
EBICglasso's own SHD (`2.1`-`2.4`) does not meaningfully improve as `N`
grows across this whole grid, while MINT's SHD falls from `.63` to
`.47` — EBICglasso's global L1 penalty is not resolving the noise
columns (`6` pure-noise variables at `p=15`) the way MINT's per-edge
screening step does. The `overlap` shape shows the identical pattern
at smaller magnitude (MINT F1 `.910`-`.959`; EBICglasso flat around
`.879`-`.889`). On the three-node, noise-free triangle fixtures, the
two methods are indistinguishable — both floor at `N=400` and track
each other closely at every strength level, exactly the outcome
expected on a DGP with no nuisance variables for a screening step to
help with.

**A second, unplanned finding: runtime.** MINT's per-replicate fit is
`2`-`3` orders of magnitude faster than EBICglasso's own `100`-point
regularization path (chain_fork_hub: MINT `~0.01s`, EBICglasso
`1.6`-`2.8s`; the triangle fixtures, at `p=3`, still show EBICglasso
`50`-`500x` slower despite the trivial dimensionality). This was not a
predeclared metric with its own pass/fail line, but the charter's own
"moderate compute" niche language (outline Section 22.2) is directly
borne out by it.

Decision: **Descriptive, not a gate.** Per the charter's own explicit
non-goal, no claim of MINT's general superiority is made — this result
is scoped to strictly Gaussian data on five specific DGP shapes at
`p in {3, 15}`, using EBICglasso's own literature-default `gamma=.5`
and MINT's own already-frozen `alpha(N)` formula (D-012's general
form, not overlap's own specialized one — see the scope note above).
Both methods enter this comparison with settings fixed before this
charter's data was drawn, per its own fair-comparison rules.

Rationale: The result is more favorable to MINT than the charter's own
framing anticipated ("does not need to dominate all comparators," per
outline Section 22.2) — but the mechanism is specific and
non-mysterious, not a general claim: EBICglasso's single global
sparsity penalty must simultaneously suppress every noise-driven edge
across the whole `p x p` matrix, while MINT's per-edge screening step
(Fisher-z evidence, `p`-specific `alpha`) tests each candidate pair on
its own evidence before DPI conditioning ever runs. On the noise-free
triangle, where there is nothing for that per-edge step to filter out,
the two methods converge, which is the expected null result and a
useful check that this is not simply "MINT wins everything."

Consequences: R6's own top-level question ("does the method occupy a
meaningful niche compared with incumbents?") now has a first, real
answer for the Gaussian, shared-assumption case: yes, specifically on
networks with nuisance/noise variables, where MINT's targeted screening
step out-performs EBICglasso's global penalty at every tested `N`, at
substantially lower compute cost, while remaining comparable on the
smallest, cleanest case. This does not touch any Stage 1-4
PROCEED/REASSESS verdict — those concern MINT's own internal validity,
unaffected by an external comparator's performance. Per the charter's
own explicit non-goals, this result does **not** extend to nonlinear,
non-Gaussian, or mixed-type data (reserved for a future charter
contingent on Stage 8), nor to the sequential/greedy engine (reserved
for a future charter once its own per-shape caveats resolve into one
general recommendation). `docs/validated_operating_ranges.md` should
record this finding in a new top-level section.

## D-048: MINT's advantage over EBICglasso shrinks, not grows, with more noise columns — likely explained by a screening-alpha confound, not a wrong mechanism (R6)

Date: 2026-09-01

Stage: R6 / Stage 5b (first follow-up to D-047)

Status: Descriptive verdict, no gate — same standing as D-047.

Decision timing: Predeclared before results — `docs/stage5b_charter.md`
fixed the "confirms" vs. "complicates" reading (monotone-non-decreasing
F1 gap, `.01`-F1 sampling tolerance) before the run was launched.

Question: Does the MINT-minus-EBICglasso F1 gap D-047 found grow as the
number of pure-noise (nuisance) columns grows, as the stated mechanism
("MINT's per-edge screening filters noise EBICglasso's global penalty
does not") predicts?

Prior specification: `docs/stage5b_charter.md`. Same two noisy `p=15`
shapes as D-047 (chain_fork_hub, overlap), noise multiplier `in {1, 2,
3}` (native noise-column count x multiplier: `chain_fork_hub` `6/12/18`
extra columns, `overlap` `4/8/12`), `N in {500, 1500}`, strength `.5`
unchanged, `2,000` replicates per cell.

Evidence: GitHub Actions run
`https://github.com/imh-ds/mintnet/actions/runs/33534728141` (6 shards,
one per `(dgp, noise multiplier)`, plus aggregation — using the newly
generalized `.github/workflows/sharded_benchmark.yml`, its first reuse
beyond Stage 5a). `raw_metrics.csv` (48,000 rows), `report.json`,
`stage5b_report.md`, `gap_by_noise_multiplier.png`.

| DGP shape | N | noise multiplier | MINT F1 | EBICglasso F1 | gap |
|---|---|---|---|---|---|
| chain_fork_hub | 500 | 1 | `.9513` | `.8569` | `.0943` |
| chain_fork_hub | 500 | 2 | `.9406` | `.8707` | `.0699` |
| chain_fork_hub | 500 | 3 | `.9255` | `.8682` | `.0573` |
| chain_fork_hub | 1500 | 1 | `.9666` | `.8435` | `.1231` |
| chain_fork_hub | 1500 | 2 | `.9543` | `.8455` | `.1088` |
| chain_fork_hub | 1500 | 3 | `.9430` | `.8493` | `.0937` |
| overlap | 500 | 1 | `.9192` | `.8865` | `.0327` |
| overlap | 500 | 2 | `.9162` | `.8926` | `.0236` |
| overlap | 500 | 3 | `.9139` | `.9010` | `.0128` |
| overlap | 1500 | 1 | `.9503` | `.8803` | `.0700` |
| overlap | 1500 | 2 | `.9456` | `.8845` | `.0611` |
| overlap | 1500 | 3 | `.9389` | `.8933` | `.0456` |

**The predeclared reading is COMPLICATES, cleanly.** The gap shrinks
monotonically as noise multiplier rises from `1` to `3`, at both `N`,
for both shapes — the opposite of the charter's own predicted
direction. `report.json`'s own `monotone_non_decreasing` flag: `False`.
MINT still wins every single cell (the gap never crosses zero on this
grid), but the margin roughly halves from multiplier `1` to `3`.

**Diagnosis, from the per-method numbers, not just the gap.** MINT's
own F1 *declines* as noise multiplier rises (e.g. chain_fork_hub
`N=500`: `.9513` to `.9255`), driven entirely by falling precision —
recall stays perfect (`1.0000`) at every cell. EBICglasso's own F1
*rises* over the same range (chain_fork_hub `N=500`: `.8569` to
`.8682`; overlap `N=500`: `.8865` to `.9010`). This has a specific,
non-mysterious likely explanation: EBICglasso's own selection criterion
(`docs/stage5a_charter.md`'s own formula,
`EBIC = -2L + E*ln(N) + 4*gamma*E*ln(p)`) has an explicit `ln(p)`
penalty term — as `p` grows with added noise columns, EBIC becomes
*more* conservative automatically, correctly compensating for the
larger number of possible false edges. **MINT's own screening step in
this charter used a single fixed `alpha=.001` at every noise
multiplier, not re-derived for the larger `p`** (`p` reaches `27` for
chain_fork_hub at multiplier `3`, up from `15` at multiplier `1`) —
this is exactly the kind of `p`-dependent recalibration Stage 2's own
arc already established is necessary (`.001` at `p=15`, `.0001` at
`p=30`, outline Section 16's own v3 revision note) but which this
charter's implementation did not carry over. A fixed per-pair `alpha`
run against a growing number of noise-noise pairs lets more false
positives through in absolute terms even though each pair's own
false-positive rate is unchanged — precisely the precision decline
observed.

Decision: **COMPLICATES**, exactly as the charter's own predeclared
branch anticipated for this outcome — flagged for its own diagnosis
before further R6 charters build on the original "grows with noise"
framing. The diagnosis above is a **plausible mechanistic account, not
yet a separately tested one** — this charter did not vary MINT's
`alpha` alongside `p`, so the claim that a `p`-adjusted `alpha` would
restore or change the pattern is a hypothesis for a follow-up charter,
not a demonstrated finding.

Rationale: This is the discipline this project's whole R6 arc exists
to enforce — a favorable-looking result (D-047) got a specific,
falsifiable follow-up prediction, and that prediction was wrong in a
way that surfaces a real, previously undisclosed limitation of *this
charter's own MINT configuration* (fixed `alpha` across a `p` sweep),
not a limitation of MINT's own established practice (which already
knows to re-derive `alpha` per `p`). Reporting the shrinking gap
honestly, and diagnosing rather than dismissing it, is exactly the
"never reinterpret a result to fit the prior narrative" principle
`docs/stage5b_charter.md` itself commits to.

Consequences: `docs/validated_operating_ranges.md`'s Stage 5a/R6
section should be amended to note this scope limitation explicitly —
D-047's own two-shape result used a fixed noise-column count per shape,
and its "MINT wins" finding should not be assumed to hold at
arbitrarily larger `p` without `alpha` also being re-derived for that
`p`. A natural next charter (not yet written) would re-run this same
noise-multiplier sweep using a `p`-adjusted `alpha(N, p)` at each
multiplier (mirroring Stage 2's own per-`p` recalibration) to test the
diagnosis directly, before any claim about how MINT's niche scales with
network size is made. The signal-strength sweep flagged as a follow-up
in `docs/stage5a_charter.md`'s own recommendation should wait until
this `alpha`-recalibration question is resolved, since strength and
`p`-adjustment are both open variables and should not be conflated in
one charter.

## D-049: p-adjusted screening alpha fixes MINT's own precision decline, but EBICglasso's p-aware penalty still narrows the gap in most conditions — a two-effect result, not a clean restoration (R6)

Date: 2026-09-01

Stage: R6 / Stage 5c (follow-up to D-048's own diagnosis)

Status: Descriptive verdict, no gate — same standing as D-047/D-048.

Decision timing: Predeclared before results — `docs/stage5c_charter.md`
fixed the three-way reading (restores / confirms-confound-not-mechanism
/ neither) before the run was launched.

Question: Does re-deriving MINT's screening `alpha` per `p` (a
disclosed log-linear interpolation of Stage 2's own two calibrated
anchor points, `.001` at `p=15`, `.0001` at `p=30`, replacing Stage
5b's fixed `.001`) restore the "gap grows with noise" prediction D-048
found violated?

Prior specification: `docs/stage5c_charter.md`. Identical grid to
Stage 5b (`chain_fork_hub`, `overlap`; `N in {500, 1500}`; noise
multiplier `in {1, 2, 3}`; strength `.5`; `2,000` replicates per cell),
one substitution: MINT's screening `alpha` is `alpha(p)` instead of
fixed `.001`. DPI's own `alpha(N)` (D-012's formula) unchanged.

Evidence: GitHub Actions run
`https://github.com/imh-ds/mintnet/actions/runs/33551121806` (12
shards — one per `(dgp, N, noise multiplier)` cell, the workflow's
first three-dimension use — plus aggregation). `raw_metrics.csv`
(48,000 rows), `report.json`, `stage5c_report.md`,
`gap_by_noise_multiplier_vs_d048.png`.

| DGP | N | mult. | MINT F1 (alpha(p)) | EBICglasso F1 | gap (alpha(p)) | gap (D-048, fixed alpha) |
|---|---|---|---|---|---|---|
| chain_fork_hub | 500 | 1 | `.9507` | `.8560` | `.0948` | `.0943` |
| chain_fork_hub | 500 | 2 | `.9548` | `.8661` | `.0888` | `.0699` |
| chain_fork_hub | 500 | 3 | `.9584` | `.8700` | `.0884` | `.0573` |
| chain_fork_hub | 1500 | 1 | `.9639` | `.8448` | `.1191` | `.1231` |
| chain_fork_hub | 1500 | 2 | `.9658` | `.8510` | `.1148` | `.1088` |
| chain_fork_hub | 1500 | 3 | `.9705` | `.8523` | `.1183` | `.0937` |
| overlap | 500 | 1 | `.9194` | `.8893` | `.0300` | `.0327` |
| overlap | 500 | 2 | `.9309` | `.8933` | `.0375` | `.0236` |
| overlap | 500 | 3 | `.9368` | `.8965` | `.0403` | `.0128` |
| overlap | 1500 | 1 | `.9518` | `.8799` | `.0719` | `.0700` |
| overlap | 1500 | 2 | `.9536` | `.8852` | `.0683` | `.0611` |
| overlap | 1500 | 3 | `.9489` | `.8908` | `.0581` | `.0456` |

**The predeclared reading is "CONFIRMS THE CONFOUND BUT NOT THE
MECHANISM," and the per-method numbers show why in more nuanced detail
than that binary label alone conveys — this is a genuine two-effect
result, not a clean restoration or a clean rejection.**

1. **The diagnosed confound is confirmed directly.** MINT's own
   precision, which *declined* with noise multiplier under D-048's
   fixed `alpha` (e.g. chain_fork_hub `N=500`: `.913` to `.870`), now
   *improves* under `alpha(p)` (chain_fork_hub `N=500`: `.912` to
   `.925`; every one of the eight MINT precision series in this
   charter's own table rises with noise multiplier, not falls). The
   `p`-adjustment did exactly what it was diagnosed to do.
2. **But the gap does not cleanly restore to "grows with noise"
   either — three of four `(dgp, N)` series are now far flatter (near-
   noise-level) than D-048's own decline, and one reverses direction
   entirely.** `chain_fork_hub` at both `N`, and `overlap N=500`, show
   gaps that are roughly flat or *increasing* with noise multiplier
   (`overlap N=500`: `.0300` to `.0403`, a genuine reversal from
   D-048's own `.0327` to `.0128` decline). Only `overlap N=1500` still
   declines beyond the predeclared `.01`-F1 tolerance (`.0719` to
   `.0581`), which is what kept the automated reading from crossing
   into "RESTORES."
3. **EBICglasso's own precision keeps improving with noise multiplier
   too, at a similar or slightly faster rate** (e.g. chain_fork_hub
   `N=500`: `.758` to `.780`) — its `ln(p)` EBIC penalty is doing real,
   legitimate work exactly as D-048 diagnosed, independent of whatever
   MINT does. The two `p`-aware effects (MINT's now-corrected
   precision, EBICglasso's own built-in penalty) are both operating on
   the same axis simultaneously, which is why the net gap is closer to
   flat than cleanly growing.

Decision: Predeclared branch **"CONFIRMS THE CONFOUND BUT NOT THE
MECHANISM"** fires as specified. Read plainly: D-048's diagnosis was
correct as far as it went (MINT's fixed `alpha` was a real, fixable
confound), but D-047's original "MINT's advantage grows with noise"
framing is **not** restored by fixing it alone — EBICglasso is not a
static comparator being outrun by a fixed penalty; its own selection
criterion is itself noise-count-aware, and that awareness continues to
narrow MINT's margin (or, in one condition, reverse the earlier
narrowing into flatness rather than growth) even once MINT's own
precision problem is corrected.

Rationale: Reporting three of four series as "much flatter, one even
reversed" rather than compressing this into a single pass/fail
sentence is itself the point of the predeclared multi-branch structure
— a binary "confirmed/not confirmed" framing would have hidden the
genuine, disclosed mixed pattern the actual numbers show. This is
exactly the kind of texture this project's own decision-log discipline
exists to preserve rather than smooth over.

Consequences: `docs/validated_operating_ranges.md`'s D-048 amendment
should be updated to reflect this less pessimistic, but not fully
restored, picture: MINT's advantage over EBICglasso on noisy composed
networks does **not** collapse as `p` grows once screening `alpha` is
properly `p`-adjusted (unlike D-048's own fixed-`alpha` reading), but
neither does it reliably grow — the net relationship is closer to flat
with shape-and-`N`-specific variation. Neither D-047 nor D-048 is
retracted; both remain valid readings of their own, distinct
configurations (fixed `alpha` vs. `p`-adjusted `alpha`, respectively).
The signal-strength sweep flagged in `docs/stage5a_charter.md`'s own
recommendation can now proceed using this charter's own `alpha(p)`
mechanism as the default going forward for any further `p`-varying R6
work, since it is now the better-tested configuration of the two.

**Infrastructure note, since this charter also tested three-dimension
sharding for the first time:** total wall-clock (`~2h03m`) was only
marginally faster than Stage 5b's own two-dimension, six-shard run
(`~2h07m`), far less than the roughly 2x improvement expected from
eliminating the diagnosed serial-fallback (D-048's own consequences
section, mirrored in `.github/workflows/sharded_benchmark.yml`'s own
header comment). Both shard counts (`6` and `12`) sit comfortably under
the concurrency ceiling observed empirically during Stage 5a (`~19`-
`20` concurrent jobs), so both runs already had full available
parallelism at the shard-count level — the fix was directionally
correct (no shard now contains more than one task) but its measured
benefit was small, likely because each additional shard's own fixed
per-job overhead (runner provisioning, checkout, `pip install -e .`,
observed roughly `1`-`2` minutes) grows in relative importance as
shard count increases and each shard's own payload shrinks, partially
offsetting the parallelism gained. Not remeasured by a controlled
comparison (same run repeated at each shard granularity) — stated as
an observed, plausible account from this one paired comparison, not a
established scaling law.

## D-050: MINT's advantage over EBICglasso grows sharply with signal strength — EBICglasso's own precision collapses at strong effects, MINT's stays flat (R6)

Date: 2026-09-01

Stage: R6 / Stage 5d (the deferred second axis, following D-047/D-049)

Status: Descriptive, no gate — same standing as every prior R6 charter.

Decision timing: Predeclared before results — `docs/stage5d_charter.md`
stated explicitly that this axis had no sharp a priori prediction, and
committed to classifying whatever trend the evidence showed (rather
than a confirm/refute branch) and to reporting a recall check
independently of that trend.

Question: Does the MINT-minus-EBICglasso F1 gap (D-047, using `alpha(p)`
per D-049) grow, shrink, or stay flat as signal strength varies, and
does recall — perfect for both methods in every cell tested so far —
stay perfect here too?

Prior specification: `docs/stage5d_charter.md`. Same two shapes
(chain_fork_hub, overlap), `N in {500, 1500}`, noise held at each
shape's own native column count (`p=15` for both), strength `in {.3,
.5, .7}`, `alpha(p)` (`= .001` exactly at this `p`, identical to
D-047's own original value), `2,000` replicates per cell.

Evidence: GitHub Actions run
`https://github.com/imh-ds/mintnet/actions/runs/33567686017` (12
shards, one per `(dgp, N, strength)` cell, plus aggregation).
`raw_metrics.csv` (48,000 rows), `report.json`, `stage5d_report.md`,
`gap_by_strength.png`.

| DGP | N | strength | MINT F1 | MINT recall | EBICglasso F1 | EBICglasso recall | gap |
|---|---|---|---|---|---|---|---|
| chain_fork_hub | 500 | .3 | `.9764` | `1.0000` | `.9327` | `1.0000` | `.0437` |
| chain_fork_hub | 500 | .5 | `.9518` | `1.0000` | `.8561` | `1.0000` | `.0957` |
| chain_fork_hub | 500 | .7 | `.9489` | `1.0000` | `.6835` | `1.0000` | `.2654` |
| chain_fork_hub | 1500 | .3 | `.9790` | `1.0000` | `.9420` | `1.0000` | `.0370` |
| chain_fork_hub | 1500 | .5 | `.9616` | `1.0000` | `.8358` | `1.0000` | `.1258` |
| chain_fork_hub | 1500 | .7 | `.9627` | `1.0000` | `.6715` | `1.0000` | `.2913` |
| overlap | 500 | .3 | `.9295` | `.9999` | `.9248` | `1.0000` | `.0048` |
| overlap | 500 | .5 | `.9196` | `1.0000` | `.8883` | `1.0000` | `.0313` |
| overlap | 500 | .7 | `.9196` | `1.0000` | `.8073` | `1.0000` | `.1123` |
| overlap | 1500 | .3 | `.9573` | `1.0000` | `.9240` | `1.0000` | `.0333` |
| overlap | 1500 | .5 | `.9476` | `1.0000` | `.8757` | `1.0000` | `.0719` |
| overlap | 1500 | .7 | `.9522` | `1.0000` | `.7898` | `1.0000` | `.1624` |

**The predeclared classification is unambiguous: `increasing`, at
every one of the four `(dgp, N)` series, no exceptions and no
non-monotonicity.** This is the cleanest, least caveated result in the
whole R6 arc to date. The recall check also confirms cleanly: recall
is `1.0000` in every cell but one (`overlap, N=500, strength=.3`:
`.9999`, one dropped edge out of thousands of replicates — not a
meaningful departure), so, as in every prior R6 charter, **the entire
gap remains a precision (false-edge) story, not a detection story** —
see the conversation's own plain-language framing: this is not about
either method missing real effects, it is about EBICglasso keeping
more edges that are not real.

**Mechanism, read directly from precision, not just F1.** MINT's own
precision is remarkably flat across strength (chain_fork_hub `N=500`:
`.957` to `.909`, actually declining slightly; overlap `N=500`: `.873`
to `.856`, also roughly flat) — MINT's screening step is not
particularly sensitive to how strong the true edges are. **EBICglasso's
own precision collapses as strength increases** — chain_fork_hub
`N=500`: `.882` at strength `.3` down to `.526` at strength `.7`;
`N=1500` similarly, `.897` to `.512`. At strength `.7`, EBICglasso is
retaining roughly twice as many false edges as at strength `.3` (SHD
rises from under `1` to nearly `6` at `chain_fork_hub`). This was not
diagnosed to a specific mechanism inside this charter (out of scope,
per the charter's own "no strong directional prediction" section) —
a plausible direction for a future diagnosis: stronger true partial
correlations may inflate the *empirical* covariance's off-diagonal
noise-noise and noise-signal entries through finite-sample estimation
coupling, making EBICglasso's own regularization path relatively less
able to distinguish genuine near-zero entries from estimation noise
riding on the stronger true signal. Stated as a hypothesis, not a
tested finding.

Decision: Reported as found, per the charter's own commitment to state
whatever trend appears rather than fit a preconceived one. No
confirm/refute language applies (this axis had no sharp prediction to
test against).

Rationale: This is the first R6 result where the two methods'
qualitative behavior diverges sharply rather than the gap merely
widening or narrowing modestly — worth flagging plainly for the
eventual paper's discussion, since "MINT's edge is largest precisely
where the underlying effects are strongest" is a stronger and more
surprising claim than a monotonic trend of similar cells would suggest
on its own, and should not be softened into an aggregate "MINT trends
better with strength" sentence that hides how large the divergence gets
at `.7`.

Consequences: Completes the two-axis characterization
`docs/stage5a_charter.md`'s own recommendation called for (noise-count:
D-048/D-049; strength: this charter). `docs/validated_operating_ranges.md`
should record this finding in its own Comparator benchmarking section.
The plausible mechanism above (estimation-noise coupling under strong
true correlations) is a natural candidate for a future diagnostic
charter, not asserted here as established.

## D-051: PC's skeleton beats both MINT and EBICglasso on precision, but misses real edges MINT and EBICglasso both catch — a second incumbent with a genuinely different failure mode (R6)

Date: 2026-09-01

Stage: R6 / Stage 5e (second comparator charter, second incumbent)

Status: Descriptive verdict, no PROCEED/REASSESS gate — same standing
as every prior R6 charter; this charter tests an external comparator,
not MINT's own correctness.

Decision timing: Predeclared before results — the `0.01` F1 tolerance
and the `>=4`-of-`7` majority rule for "comparable to or better" were
fixed in `mintnet.experiments.stage5e_reporting`'s own module docstring
before the run was launched.

Question: Does the PC algorithm's skeleton phase (subset-conditioning
independence tests, no orientation phase implemented at all — see
`docs/stage5e_charter.md` for why that scope resolves the
"entangled with direction-finding" concern raised in review before this
charter was frozen) occupy a materially different position than MINT's
conservative engine and EBICglasso, on the identical draws D-047's own
numbers were computed on?

Prior specification: `docs/stage5e_charter.md`. Same five shapes and
`N` grid as Stage 5a, `alpha_pc=0.01` fixed (not tuned), condition
seeds reused verbatim from `stage5a._condition_seed` so every cell
draws the same data as D-047 — a paired comparison, not merely a
comparable one. MINT and EBICglasso were not re-run; their numbers
below are D-047's own, hardcoded in `stage5e_reporting.py` from
`results/generated/stage5a_comparator_benchmark/stage5a_report.md`.

Evidence: GitHub Actions run
`https://github.com/imh-ds/mintnet/actions/runs/33589193320` (35
matrix shards, one per `(dgp, N)` cell, plus one aggregation job — all
36 jobs succeeded). Aggregated evidence: `raw_metrics.csv` (70,000
rows), `report.json`, `stage5e_report.md`, `pc_vs_d047_f1.png`.

| DGP shape | matches MINT (of 7) | matches EBICglasso (of 7) | Verdict |
|---|---|---|---|
| chain_fork_hub | 7/7 | 7/7 | PC comparable to or better than MINT |
| overlap | 7/7 | 7/7 | PC comparable to or better than MINT |
| triangle_balanced | 7/7 | 7/7 | PC comparable to or better than MINT |
| triangle_moderate | 2/7 | 2/7 | PC trails both materially |
| triangle_strong | 0/7 | 0/7 | PC trails both materially |

**On the two composed, noisy `p=15` networks, PC's skeleton is not just
comparable to MINT — it has *better* precision than MINT's own, at
every tested `N`, while matching MINT's perfect recall.**
`chain_fork_hub`: PC precision `.945`-`.950` vs. MINT's own D-047
precision `.917`-`.939`; `overlap`: PC precision `.972`-`.977` vs.
MINT's `.840`-`.927` (wider gap than chain_fork_hub). PC's recall stays
at `1.0` on `chain_fork_hub` and `.997`-`1.000` on `overlap`, matching
this arc's own recall-is-perfect pattern. Both comparisons beat
EBICglasso by a wide margin (EBICglasso F1 `.839`-`.889` across both
shapes, unchanged from D-047). On `triangle_balanced` (the DGP with no
nuisance variables and three equal-strength true edges) all three
methods are effectively indistinguishable, F1 `~1.0` throughout — the
expected null result, consistent with D-047's own finding there.

**On `triangle_moderate` and `triangle_strong`, PC's recall degrades
substantially more than either incumbent's on the identical DGP —
this is a difference of degree, not a wholly new phenomenon.** These
two shapes each have one deliberately weak true edge (partial
correlation `-.12` at `moderate`, `-.08` at `strong` —
`src/mintnet/simulation/motifs.py`'s own precision matrices), and
**D-047 already showed both MINT and EBICglasso with imperfect recall
on these same two shapes at low `N`** (MINT `.868`, EBICglasso `.953`
at `triangle_strong, N=400`). The auto-generated report text's own
recall-check sentence ("unlike every prior R6 charter... new
information") overstates this — recall imperfection here is not new to
the arc. **What is new is the magnitude: PC's recall on the identical
weak edge is substantially worse than either incumbent's at the same
`N`** — `triangle_strong, N=400`: PC recall `.720` vs. MINT `.868` vs.
EBICglasso `.953`; the gap narrows but does not close by `N=1750`
(PC `.923` vs. MINT `.986` vs. EBICglasso `.999`). `triangle_moderate`
shows the identical pattern at smaller magnitude.

Decision: **Descriptive, not a gate.** PC is a genuinely different
incumbent from EBICglasso — its own decision rule (subset-conditioning
independence tests, edge removed on the *first* subset that fails to
reject) trades toward higher precision and lower recall on weak edges,
the opposite direction from EBICglasso's own single global penalty
(which this arc has consistently found under-penalizes noise,
i.e. trades toward lower precision). No claim of general PC inferiority
or superiority is made — per `docs/stage5e_charter.md`'s own decision
structure, a mixed, shape-dependent picture is the complete answer.

Rationale: PC's own decision rule structurally explains the direction
of both effects, though the exact quantitative mechanism was not tested
here (stated as a plausible reading, not established): removing an
edge as soon as *any* one subset test fails to reject independence is,
in effect, an OR-rule across many tests — for a strong true edge this
does no harm (every subset should reject), but for a weak true edge it
means many chances to be wrongly declared independent by one
underpowered test among several, which plausibly explains why PC's
recall on the weak-edge triangle shapes is worse than a method (MINT)
that also does per-edge conjunctive testing but over a single, fully-
specified conditioning set rather than many candidate subsets, and worse
than EBICglasso's joint estimation (which does not test subsets at
all). On the composed noisy networks, the same OR-rule works in PC's
favor for precision: many chances to detect that a noise-noise or
noise-signal pair is independent via *any* subset, which plausibly
explains why PC's precision there beats both MINT's and EBICglasso's.

Consequences: R6 now has two structurally different incumbents on
record, not one. The two-incumbent picture is richer than either alone:
on the composed noisy networks (this project's own primary DGP
interest, per D-047's own framing), MINT sits between PC (higher
precision, lower recall on weak edges) and EBICglasso (lower precision,
comparable recall) — no single incumbent dominates, and MINT's own
niche is that it does not trade recall for precision the way PC does,
while still beating EBICglasso's precision by a wide margin. On the
weak-signal triangle shapes, MINT and EBICglasso both handle the weak
edge better than PC does, another point in favor of MINT's own
niche relative to PC specifically, not just relative to EBICglasso.
Does not retroactively alter D-047 through D-050 (all remain valid
readings of the EBICglasso comparison specifically) or any Stage 1-4
PROCEED/REASSESS verdict. Extends the same continuous-Gaussian scope
limitation already disclosed in `docs/validated_operating_ranges.md`.
`docs/validated_operating_ranges.md` should record this finding in its
own Comparator benchmarking section. The plausible OR-rule mechanism
above is a candidate for a future diagnostic charter (e.g. testing
whether a stricter PC variant, such as requiring rejection at every
tested subset rather than the first, changes the recall picture), not
asserted here as established.

**Correction, added the same day this entry was first recorded, after
direct questioning surfaced that the "Consequences" paragraph above
understated the result:** "MINT sits between PC and EBICglasso, no
single incumbent dominates" is misleading as stated. On both composed
noisy networks, **PC's F1 is higher than MINT's at every tested `N`,
not merely comparable** — `chain_fork_hub`: PC matches MINT's perfect
recall (`1.0`) and has *better* precision at every `N` (`.945`-`.950`
vs. MINT's `.917`-`.939`), so PC strictly dominates MINT there, not
just "trades differently." `overlap`: PC's recall is marginally below
MINT's at low `N` (`.997` vs. MINT's perfect `1.0`) but its precision
is high enough (`.97`+ vs. MINT's `.84`-`.93`) that PC's F1 still wins
comfortably at every `N`. This is not an artifact of an unfair setup
favoring PC — if anything the reverse: MINT's own `alpha(N)` was
originally calibrated via truth-informed simulation on these exact DGP
shapes in earlier charters, while PC's `alpha=.01` is a generic
literature value with no relationship to these specific networks, so
MINT had the tuning advantage here and still lost on F1. **The correct
reading: MINT's own comparative niche on the composed noisy networks —
this project's own primary DGP interest — is beating EBICglasso, not
dominating incumbents in general; PC beats MINT there on the metric
that matters most.** What remains genuinely in MINT's favor: it still
beats PC specifically on recall for weak true edges (the
triangle_moderate/strong finding above, unaffected by this correction),
and it remains meaningfully faster than PC (roughly `2`-`6x`, smaller
than the `2`-`3` orders of magnitude margin over EBICglasso). The
per-cell evidence table earlier in this entry is unaffected by this
correction — only the summary interpretation is revised.

## D-052: A material share of MINT's residual false positives never reach DPI at all — a concrete, partial explanation for D-051's precision gap (R6)

Date: 2026-09-01

Stage: R6 / Stage 5f (diagnostic follow-up to D-051's own corrected finding)

Status: Descriptive attribution, no PROCEED/REASSESS gate, no algorithm
change — per `docs/stage5f_charter.md`'s own scope, this charter
explains an existing finding via pure post-hoc measurement; it does
not modify or retune MINT's pipeline.

Decision timing: Predeclared before results — the MATERIAL (`>=.5`
passthrough share) / PARTIAL (`>.1` and `<.5`) / MINIMAL (`<=.1`)
thresholds, and the `>=4`-of-`7` majority rule, were fixed in
`docs/stage5f_charter.md` and `stage5f_reporting.py`'s own module
docstring before the run was launched.

Question: Does `compose_screen_then_prune`'s own documented scope
limit — DPI conditioning is only applied within validated 3/4/5-node
clique candidate components, so any screened-in false edge that lands
in a non-clique or isolated-pair component is passed through into the
final graph completely untested — account for a material share of
MINT's own residual false positives on the two composed noisy networks
where D-051 found PC's precision beats MINT's?

Prior specification: `docs/stage5f_charter.md`. Same DGPs
(`chain_fork_hub`, `overlap`), same full `N` grid, same condition seeds
and `alpha(N)`/screening `alpha` as D-047/D-051 — identical draws, zero
modification to MINT's own pipeline. Every final edge is categorized
`dpi_conditioned` or `passthrough_unconditioned` using
`compose_screen_then_prune`'s own unmodified `shapes` output, then
cross-referenced against ground truth.

Evidence: Local run (MINT's own per-replicate cost is cheap, no CI
sharding needed — `results/generated/stage5f_diagnostic/`),
`2,000` replicates per `(dgp, N)` cell, all `14` cells `0` errors.
`raw_metrics.csv` (28,000 rows), `report.json`, `stage5f_report.md`.

| DGP shape | material | partial | minimal | Reading |
|---|---|---|---|---|
| chain_fork_hub | 0/7 | 7/7 | 0/7 | PARTIAL at every tested N |
| overlap | 5/7 | 2/7 | 0/7 | MATERIAL at 5/7 tested N |

**`chain_fork_hub`: passthrough-unconditioned edges are a real but
non-dominant `~28`-`40%` of MINT's own false positives**, roughly
stable across `N` (`.285` at `N=400` to a peak `.396` at `N=1500`, back
to `.344` at `N=1750` — no clean monotone trend). **`overlap`:
passthrough-unconditioned edges are the *majority* explanation at most
tested `N`, and the largest share exactly where D-047/D-051 found the
biggest MINT-vs-incumbent gap on this shape** — `.769`-`.823` at `N in
{400, 500, 600, 750}`, still substantial but below the material
threshold at `N in {1500, 1750}` (`.487`, `.457`). The share's own
decline at high `N` is consistent with a natural mechanism, not a
contradiction: as `N` grows, screening's own per-pair power increases
(fewer noise-driven candidate edges survive screening at all — D-013's
own finding), which plausibly means fewer noise variables remain
available to accidentally chain a false edge into a validated clique
component, shifting the *mix* of surviving false edges toward
passthrough being relatively less dominant even as the shape of the
underlying mechanism is unchanged. This was not directly tested here
and is stated as a plausible reading, not established.

Decision: **The hypothesis is supported, materially on `overlap` and
partially on `chain_fork_hub`.** DPI's own clique-shape scope is a
real, concrete, and now-measured contributor to MINT's residual false
positives on both composed noisy networks — not the sole explanation
(PARTIAL, not MATERIAL, on `chain_fork_hub`; even on `overlap`'s own
MATERIAL cells, roughly a fifth to a quarter of false positives are
`dpi_conditioned`-and-wrongly-retained, so DPI's own examined decisions
still contribute too), but a real structural gap, not a marginal one.

Rationale: This directly and concretely explains part of why PC — which
never gives up on an edge regardless of its local component shape —
achieves higher precision than MINT on these same networks (D-051).
The larger passthrough share on `overlap` relative to `chain_fork_hub`
is also consistent with `overlap`'s own larger MINT-vs-PC F1 gap in
D-051 (MINT F1 `.910`-`.959` on overlap vs. PC's `.985`-`.988`, a wider
gap than `chain_fork_hub`'s own MINT `.954`-`.966` vs. PC's
`.970`-`.973`) — the shape with the bigger passthrough problem also has
the bigger precision gap, a coherent (if not independently proven
causal) pattern across the two DGPs tested.

Consequences: Identifies a concrete, actionable candidate for a
**future implementation charter**: extending DPI's own conditioning to
examine non-clique or smaller (e.g. 2-node) components, rather than
passing them through untested. Per this charter's own explicit
non-goals, that is a real algorithm change requiring its own fresh
validation (new false-edge-rate and true-edge-recall gates, not
assumed safe just because it plausibly improves precision here) — not
authorized or attempted by this diagnostic charter. Does not alter
D-047 through D-051; this charter explains an existing finding, it does
not re-test it. The OR-rule/multiple-testing hypothesis from D-051's
own rationale remains untested and is not ruled out as an additional,
co-occurring contributor — this charter measured one specific
mechanism, not all plausible ones. `docs/validated_operating_ranges.md`
should record this finding in its own Comparator benchmarking section.

## D-053: Growing-subset DPI matches or beats full-component DPI everywhere tested, with zero recall cost — but the composed networks need conditioning dimension beyond 3 in a real minority of cases (mi-native track, Stage 6a)

Date: 2026-09-01

Stage: mi-native / Stage 6a (first mi-native charter; no new estimator)

Status: Descriptive, no production pipeline change — per
`docs/stage6a_charter.md`'s own decision structure, this is a
diagnostic comparison on the existing Fisher-z partial-correlation
primitive, run to scope a future conditional-MI estimator, not to
authorize a change to `compose_screen_then_prune`.

Decision timing: Predeclared before results — the `.01` accuracy
tolerance, the majority-of-tested-N convention, and the search-depth
cap of `4` were all fixed in `docs/stage6a_charter.md` itself before
this run.

Question: Does a PC-style growing-conditioning-set search (test size
1, escalate only if nothing prunes, using MINT's own screened
candidate graph as the starting adjacency) resolve at lower dimension
than the current full-component design, recover any of D-052's own
passthrough-unconditioned false-positive gap, and reveal the actual
maximum conditioning dimension this project's validated DGPs require?

Prior specification: `docs/stage6a_charter.md`. Two tiers: isolated
motifs (triad, hub, 5-node overlapping-triangles, no screening/noise,
`N in {750, 1500}`) and the composed, noisy `p=15` networks
(`chain_fork_hub`, `overlap`, identical draws to D-047/D-051/D-052),
`2,000` replicates per cell, both mechanisms run on identical data.

Evidence: Local run (`results/generated/stage6a_conditioning_architecture/`,
gitignored), all `18` cells (`5` isolated shapes x `2` N, `2` composed
shapes x `7` N) `0` errors. `raw_metrics.csv`, `conditioning_sizes.csv`
(`333,348` candidate-edge rows across both composed shapes), `report.json`,
`stage6a_report.md`.

| shape | max size used | accuracy reading | recall reading |
|---|---|---|---|
| triangle (all 3) | 1 | identical to full-component at both N | identical |
| hub | 2 | comparable-or-better at both N | no cost |
| overlap_isolated | 3 | comparable-or-better at both N | no cost |
| chain_fork_hub (composed) | 4 (cap) | comparable-or-better at 7/7 N | no cost |
| overlap (composed) | 4 (cap) | comparable-or-better at 7/7 N | no cost |

**The triad control passed exactly as required** (a 3-node component
has only one other member, so growing-subset search can never test
anything beyond size 1, and must reproduce full-component DPI's own
numbers bit-for-bit — it did, at both `N`, a built-in correctness
check on the new implementation, not just a scientific result).

**On the composed noisy networks — the setting that actually matters —
precision improves substantially and consistently, with zero measured
recall cost at any tested N, on either shape.** `overlap`: precision
`.838`-`.927` (full-component) to `.946`-`.967` (growing-subset) across
the whole `N` grid, SHD falling by roughly half to three-quarters at
every `N` (e.g. `N=750`: `2.089` to `.545`); F1 `.909`-`.959` to
`.971`-`.983`. `chain_fork_hub`: a smaller but consistent gain,
precision `.913`-`.939` to `.921`-`.947`, F1 `.951`-`.966` to
`.956`-`.971`. **Recall stayed at exactly `1.0000` for growing-subset
DPI at every single composed-tier cell** — the same perfect recall
full-component DPI already had. This is a meaningful, non-obvious
result: growing-subset DPI uses the identical OR-rule logic PC's own
skeleton search uses (D-051's own explanation for PC's precision
advantage), but does **not** show PC's own weak-edge recall cost here.
The plausible reason (not directly tested, but consistent with the
architecture): growing-subset DPI only ever runs on pairs that already
passed MINT's own unconditional screening step first — unlike PC,
which tests every pair from scratch — so it inherits screening's own
recall-preserving property that PC never had access to.

**Dimension finding, the charter's own central deliverable, from the
full per-candidate-edge distribution (not just the shape-level max):**
the overwhelming majority of decisions resolve at size `1`
(`96.8%` of all `127,050` chain_fork_hub candidate-edge decisions;
`55.6%` of all `206,298` overlap candidate-edge decisions). `overlap`
has a real secondary mass at size `3` (`40.2%` of decisions) — the
5-node two-triangle structure's own genuine 3-variable conditioning
need, matching `overlap_isolated`'s own clean-motif finding exactly.
**The search-depth cap (`4`) was reached on both composed shapes, not
just theoretically but at a measurable rate**: `1.30%` of
chain_fork_hub's candidate edges and `2.87%` of overlap's landed at
size `4`, and among those, `140` (`chain_fork_hub`) and `3,473`
(`overlap`) — roughly `8.5%` and `58.7%` of their own size-`4` group
respectively — were genuine cap-truncations (`cap_reached=True`: the
component still had untested larger subsets when the search stopped),
not cases that happened to resolve exactly at `4`. **This means the
true required conditioning dimension on the composed noisy networks is
not cleanly bounded at `3`, or even at `4`, for a real minority of
candidate edges** — a long tail exists whose true dimension this
charter's own disclosed cap did not measure.

Decision: **Descriptive; no change to the production pipeline.**
Growing-subset DPI is a strong candidate for a future implementation
charter on the Gaussian baseline itself (would need its own accuracy
gate, not assumed safe from a diagnostic comparison alone, per this
charter's own non-goals) — but this decision's primary purpose is
scoping `mi-native`: **most decisions need only single-variable
conditioning, but a real (if small) minority on the composed networks
need dimension `3` or more, with an uncharacterized tail beyond `4`.**

Rationale: The precision gain concentrating on `overlap` and tracking
almost exactly the two shapes D-052 flagged (passthrough-unconditioned
edges being D-052's own measured problem, MATERIAL specifically on
`overlap`) is consistent, not coincidental — growing-subset DPI
examines every connected component, not just validated cliques, so it
directly closes the exact gap D-052 measured, and the size of the
precision gain on each shape tracks the size of D-052's own
passthrough share on that same shape.

Consequences: For `mi-native`'s own next charter (the conditional-MI
estimator itself): a single-variable conditional-MI-plus-local-
permutation method (Runge, 2018) would correctly handle the large
majority of real decisions, but **cannot be the only mechanism built** —
the composed networks demonstrably need multivariable conditioning
(dimension `>= 3`, with a measured, non-trivial tail beyond `4`) for a
real share of edges, concentrated on shapes with genuine multi-way
shared-node structure like `overlap`. The estimator-validation charter
must plan for at least `|S| <= 3` support from the start, and should
either extend the cap further or explicitly characterize the accuracy
cost of whatever cap is chosen, rather than assume `4` is safe just
because it was this charter's own arbitrary starting choice. Separately,
flagging for a future (not this charter's own) decision: growing-subset
DPI's strong, recall-free precision gain on the *existing* Gaussian
baseline is itself worth a dedicated implementation charter on `main`,
independent of `mi-native`'s own progress — noted here, not acted on.
`docs/validated_operating_ranges.md` should record this finding.
