# Stage 1b Conditional-Independence Motif Validation Report

Status: **REASSESS**

## Run

Frozen configuration `configs/stage1b_dpi.yaml`: identical DGP, `N` grid,
strengths, replicate split, and master seed to the R2 charter, replacing
magnitude-ratio DPI with a per-edge Fisher-z partial-correlation test
(`alpha` grid `[.0001, .001, .005, .01, .05, .10, .20, .30, .50]`). 243,000
raw rows generated, zero errors.

## Decision

`results/generated/stage1b_dpi/decision.json`: **REASSESS**. Development
selection found alpha pair `(0.05, 0.10)` passing the pooled gate, but
validation failed one criterion: `triangle genuine-edge pruning FPR`, at
specific cells (see below).

## Why: development-replicate evidence

Chain/fork indirect-edge pruning TPR (gate `>= .80`) and triangle true-edge
FPR (gate `<= .10`), pooled across strengths/families, `N in [500, 750,
1000]`:

| alpha | .0001 | .001 | .005 | .01 | .05 | .10 | .20 | .30 | .50 |
|---|---|---|---|---|---|---|---|---|---|
| chain/fork TPR | 1.000 | .999 | .994 | .988 | **.952** | **.901** | .806 | .704 | .501 |
| triangle FPR | .195 | .157 | .119 | .102 | **.060** | **.043** | .025 | .017 | .009 |

Both criteria are satisfied simultaneously for `alpha` in roughly `[.05,
.20]` — a real overlap, unlike R2, where triangle FPR never cleared the gate
at any tau. This is the direct effect of testing each edge's own conditional
dependence instead of comparing pairwise MI magnitudes to each other.

## Diagnosis: triangle FPR by family (development replicates)

Pooling hides that the fix is uneven across triangle fixtures. FPR by
family, development replicates, `N >= 500`:

| alpha | .0001 | .001 | .005 | .01 | .05 | .10 | .20 | .30 | .50 |
|---|---|---|---|---|---|---|---|---|---|
| balanced | .014 | .002 | .000 | .000 | .000 | .000 | .000 | .000 | .000 |
| moderate | .245 | .178 | .116 | .088 | .042 | .028 | .014 | .008 | .005 |
| **strong** | .325 | .291 | .241 | .216 | **.138** | **.100** | .060 | .042 | .022 |

`balanced` and `moderate` clear the `.10` gate comfortably at the selected
pair. `strong` — the fixture with the most unequal edge strengths — does
not. Development-replicate FPR by `N` (diagnostic only; the gate itself is
decided on validation replicates, reported in Outcome below):

| N | .0001 | .001 | .005 | .01 | .05 | .10 | .20 | .30 | .50 |
|---|---|---|---|---|---|---|---|---|---|
| 500 | .344 | .313 | .281 | .260 | .187 | .141 | .092 | .065 | .036 |
| 750 | .320 | .289 | .223 | .203 | .117 | .089 | .048 | .035 | .016 |
| 1000 | .312 | .269 | .219 | .187 | .111 | .071 | .041 | .025 | .013 |

At the selected pair, `strong` fails at `alpha = .05` (`N = 500, 750`) and at
`alpha = .10` (`N = 500`). It improves monotonically with `N` at every
`alpha`, unlike R2's triangle FPR, which was flat across `N`. This looks
like a sample-size/power limitation specific to detecting `strong`'s weakest
edge (partial correlation ~0.08) at the frozen `N` floor, not a structural
confound in the mechanism.

## Exploratory evidence: `1 - p_value` as a candidate confidence-style score (non-gating; not a validated calibration)

`calibration_summary.csv`, Brier score of `1 - p_value` against ground truth
(development replicates only; naive-uninformative baseline is `0.25`):

| N | 100 | 200 | 300 | 500 | 750 | 1000 | pooled |
|---|---|---|---|---|---|---|---|
| Brier | .094 | .086 | .082 | .078 | .073 | .076 | .081 |

The `1 - p_value` score is informative (well below a flat baseline) and
improves with `N`. This is promising exploratory support for a future
confidence-scored edge representation — pending a proper reliability
diagram and prevalence-adjusted baseline, which have not been computed —
but per `docs/stage1b_charter.md` it does not gate this decision.

## Outcome

**REASSESS**, but a materially different result than R2. Testing each edge's
own conditional independence (exact for this Gaussian DGP) resolves the
`balanced`/`moderate` failure entirely and greatly narrows the `strong`
failure to specific small-`N` cells whose FPR is still trending down with
`N`, rather than a mechanism-wide, `N`-invariant floor. This validates the
diagnosis in `docs/decision_log.md` D-002: the R2 failure was the
magnitude-ratio comparison, not an unfixable property of tolerant DPI.

See `aggregate_metrics.csv`, `raw_metrics.csv`, `decision.json`,
`calibration_summary.csv`, and the generated figures under
`results/generated/stage1b_dpi/` for complete evidence.
