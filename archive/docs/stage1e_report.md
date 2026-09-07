# Stage 1e Higher-Replicate-Count Report (R2e)

Status: **REASSESS**

## Run

Fresh frozen simulation, `configs/stage1e_dpi.yaml`: R2c/R2d's DGP,
mechanism, `N` grid, and alpha grid, with replicates quadrupled from 500 to
2000 (development 0-999, validation 1000-1999). 1,296,000 raw rows
generated, zero errors. Replicates 0-499 reproduce R2c/R2d's exact data by
construction (seed derivation is positional on replicate index alone).

## Decision

`results/generated/stage1e_dpi/decision.json`: **REASSESS**,
`"no eligible development alpha pair"`. As in R2d, only `alpha = 0.10`
passes every individual `(N, strength)` cell, with no adjacent eligible
partner.

## The extra replicates sharpened the picture instead of dissolving it

At 250 development replicates, the standard error was large enough that
every near-miss was smaller than one standard error — consistent with pure
noise. At 1000 replicates the standard error roughly halves (`~.0095` for
FPR at a true rate of `.10`; `~.0126` for TPR at `.80`), and the two
neighboring alphas resolved in different directions:

**`alpha = .05`** now fails only *one* cell (down from two), but that
cell's miss got proportionally larger, not smaller:

| family | N | strength | FPR | miss vs. new SE |
|---|---|---|---|---|
| strong | 750 | .7 | .128 | **2.9 SE** |

A miss of nearly 3 standard errors is not noise. This is now a real,
if narrow, failure.

**`alpha = .20`** improved: the number of failing chain/fork TPR cells
dropped from 12 to 8, and most of the remaining misses shrank to well
under one standard error (e.g., `.797` against `.80`, `0.24` SE) — consistent
with those specific cells converging toward passing as noise shrinks. A
couple remain more marginal (`.784`, `1.26` SE).

## Outcome

**REASSESS**, and a clearer picture than R2d's, not merely more of the
same ambiguity. The alpha value halfway between `.05` and `.10` (or
between `.10` and `.20`) is where more resolution is needed — the frozen
grid steps directly from `.05` to `.10` to `.20`, and the evidence now
suggests a real, narrow valid region sits close to `.10` without another
tested grid point landing inside it on either side. `.05` is now a
confirmed, non-noise failure; `.20` is a shrinking-but-still-marginal one.
This is a grid-resolution problem, not a replicate-count problem or a
mechanism problem: per `docs/stage1e_charter.md`'s consequences, the next
lever is a finer alpha grid near `[.05, .20]`, not more replicates again.

An exploratory-score check on `1 - p_value` (Brier score against ground
truth, development replicates, flat baseline `.25`; not a calibration
claim) remains stable and low across the full `N` range (`.074`-`.096`,
pooled `.080`), consistent with R2c/R2d.

See `raw_metrics.csv`, `aggregate_metrics.csv`, `decision.json`,
`calibration_summary.csv`, and the generated figures under
`results/generated/stage1e_dpi/` for complete evidence.
