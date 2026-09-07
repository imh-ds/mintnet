# Stage 1 DPI Motif Validation Report

Status: **REASSESS**

## Run

Frozen configuration `configs/stage1_dpi.yaml`: chain, measured-fork, and
triangle (`balanced`/`moderate`/`strong`) Gaussian motifs; `N in [100, 200,
300, 500, 750, 1000]`; strengths `[.3, .5, .7]`; `k = 20`; tau grid `[0, .05,
.10, .15, .20, .25, .30, .40, .50]`; 500 replicates; master seed `20260829`.
243,000 raw rows generated, zero estimator/DGP/Cholesky errors.

## Decision

`results/generated/stage1_dpi/decision.json`:

```
{
  "status": "REASSESS",
  "selected_tau_pair": null,
  "metrics": {},
  "failures": ["no eligible development tau pair"]
}
```

No adjacent tolerance pair in the frozen grid satisfies both gate criteria on
development replicates (0-249) pooled across strengths/families at `N >= 500`.

## Why: development-replicate evidence

Chain/fork indirect-edge pruning TPR (gate: `>= .80`) is satisfied at every
tau in the grid, pooled across `N in [500, 750, 1000]`:

| tau | 0 | .05 | .10 | .15 | .20 | .25 | .30 | .40 | .50 |
|---|---|---|---|---|---|---|---|---|---|
| TPR | .996 | .996 | .994 | .994 | .992 | .991 | .987 | .982 | .938 |

Triangle true-edge pruning FPR (gate: `<= .10`) is **not** satisfied at any
tau in the grid, pooled the same way:

| tau | 0 | .05 | .10 | .15 | .20 | .25 | .30 | .40 | .50 |
|---|---|---|---|---|---|---|---|---|---|
| FPR | .333 | .309 | .287 | .263 | .237 | .217 | .201 | .160 | .117 |

FPR falls monotonically as tolerance increases but has not crossed the `.10`
threshold by `tau = .50`, the top of the frozen grid, and per-`N` breakdown
(500/750/1000) shows the same floor (~.116-.121 at `tau = .50`) rather than
further improvement with sample size. Because chain/fork TPR is not the
binding constraint here, the tolerant-DPI mechanism as chartered cannot reach
a jointly passing tau within the tested tolerance range: sufficient tolerance
to bring triangle FPR under .10 would require extrapolating past the frozen
grid, which the charter does not permit as a post hoc adjustment.

## Outcome

**REASSESS.** Tolerant DPI, applied at the tau values fixed by
`docs/stage1_charter.md`, prunes genuine triangle edges more often than the
gate allows even at its most permissive setting, while chain/fork indirect
pruning is comfortably within tolerance across the whole grid. This is a
property of the DPI mechanism at this tolerance range, not an artifact of
estimator error, sample size, or an incomplete run.

See `aggregate_metrics.csv`, `raw_metrics.csv`, `decision.json`, and the
generated figures under `results/generated/stage1_dpi/` for complete
evidence.
