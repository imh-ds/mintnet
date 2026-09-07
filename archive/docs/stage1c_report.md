# Stage 1c Conditional-Independence Motif Validation Report (Higher N Floor)

Status: **REASSESS**

## Run

Frozen configuration `configs/stage1c_dpi.yaml`: R2b's DGP, alpha grid, and
seeds, extended with `N in [1500, 2000]` and a raised gate floor of `N >=
750` (dropping `N = 500`). 324,000 raw rows generated, zero errors.

## Decision

`results/generated/stage1c_dpi/decision.json`: **REASSESS**. Development
selection picked adjacent pair `(0.005, 0.01)`, which fails validation on
`triangle genuine-edge pruning FPR` at `strength = 0.7` (`strong` family),
`N = 750` and `N = 1000`.

## The power hypothesis is confirmed

Holding `alpha` fixed and reading `strong`-family FPR across the full `N`
range (development replicates) shows a clean, continuing improvement well
past R2b's `N = 1000` ceiling:

| N | .0001 | .001 | .005 | .01 | .05 | .10 | .20 | .30 | .50 |
|---|---|---|---|---|---|---|---|---|---|
| 500 | .344 | .313 | .281 | .260 | .187 | .141 | .092 | .065 | .036 |
| 750 | .320 | .289 | .223 | .203 | .117 | .089 | .048 | .035 | .016 |
| 1000 | .312 | .269 | .219 | .187 | .111 | .071 | .041 | .025 | .013 |
| 1500 | .259 | .205 | .135 | .116 | .051 | .031 | .016 | .005 | .001 |
| 2000 | .203 | .116 | .075 | .047 | .015 | .007 | .000 | .000 | .000 |

At `alpha = .05` or `.10`, FPR is essentially at zero by `N = 2000`. This is
exactly what the R2b trend predicted: `strong`'s failure is a sample-size
power limitation for its weakest edge, not a structural defect in
conditional-independence pruning. Chain/fork TPR pooled at `N >= 750` is
`.950` at `alpha = .05` and `.902` at `alpha = .10` — comfortable margin
above the `.80` floor at either.

## Why the gate still failed: a selection-methodology artifact, not a mechanism failure

`(0.05, 0.10)` would have passed every validation cell (all three families,
all four `N`) with real margin. The gate instead selected `(0.005, 0.01)`
because development selection scans `alpha` ascending and returns the
*first* adjacent pair whose **pooled** average (across all strengths and all
`N >= 750` at once) clears both thresholds — and at `alpha = .005`/`.01`,
pooled triangle FPR is `.069`/`.056`, under `.10`, even though `strong` at
`N = 750`/`1000` alone is `.22`-`.23` at those alphas. The good performance
at the newly added `N = 1500`/`2000` cells pulls the pooled average down
enough to mask the still-bad `N = 750`/`1000` cells. Validation then checks
every cell individually and catches what pooling hid.

This is the same pooling blind spot that separated R2's aggregate view from
its per-family reality, now appearing between pooled-`N` and per-`N`
instead of between pooled-family and per-family. It is a property of the
**development-selection rule** (smallest pooled-passing `alpha`, evaluated
across a wider and more heterogeneous `N` range than R2b used), not new
evidence against the conditional-independence mechanism itself — the
fixed-`alpha` trend table above is what actually answers the power
question, and it answers it well.

## Exploratory evidence: `1 - p_value` as a candidate confidence-style score (non-gating; not a validated calibration)

Brier score of `1 - p_value` against ground truth (development replicates),
naive-uninformative baseline `.25`:

| N | 100 | 200 | 300 | 500 | 750 | 1000 | 1500 | 2000 | pooled |
|---|---|---|---|---|---|---|---|---|---|
| Brier | .094 | .086 | .082 | .078 | .073 | .076 | .073 | .073 | .079 |

Stable and well below baseline across the full extended `N` range.

## Outcome

**REASSESS.** The charter's specific question — does raising the gate floor
to `N = 750` resolve R2b's failure — is not answered cleanly by this run's
formal PROCEED/REASSESS decision, because the *pooled* development-selection
rule picked an alpha pair that happens to fail at the low end of the
extended `N` range while a substantially better pair existed in the same
tested grid. The underlying scientific question the charter asked — is this
a power limitation — is answered, clearly, by the fixed-alpha trend table:
yes. Per this charter's rules, that observation cannot be used to
retroactively re-select `(0.05, 0.10)` as the R2c decision; a selection rule
that checks every `N` individually rather than a pooled average, if wanted,
must be its own frozen charter before generating new results.

See `aggregate_metrics.csv`, `raw_metrics.csv`, `decision.json`,
`calibration_summary.csv`, and the generated figures under
`results/generated/stage1c_dpi/` for complete evidence.
