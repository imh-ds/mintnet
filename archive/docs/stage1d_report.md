# Stage 1d Per-Cell Selection Report (R2d)

Status: **REASSESS**

## Run

Reused R2c's raw evidence verbatim (`results/generated/stage1c_dpi/raw_metrics.csv`,
324,000 rows, zero errors) under the frozen R2d per-cell development-selection
rule: an alpha is eligible only if every individual `(N, strength)` cell,
`N >= 750`, passes both criteria — not merely the pooled average.

## Decision

`results/generated/stage1d_dpi/decision.json`: **REASSESS**,
`"no eligible development alpha pair"`. Checking every development alpha
individually against the per-cell rule:

| alpha | .0001 | .001 | .005 | .01 | .05 | **.10** | .20 | .30 | .50 |
|---|---|---|---|---|---|---|---|---|---|
| per-cell eligible | no | no | no | no | no | **yes** | no | no | no |

Only `alpha = 0.10` is eligible under the per-cell rule, and it is
surrounded on both sides by ineligible alphas — no *adjacent* pair exists,
which the charter requires.

## Why the neighbors fail: near-misses, not a wide gap

`alpha = .05` fails only two cells, both `strong`-family, both barely over
the `.10` FPR gate:

| family | N | strength | FPR |
|---|---|---|---|
| strong | 750 | .7 | .117 |
| strong | 1000 | .7 | .111 |

`alpha = .20` fails several chain/fork TPR cells, all barely under the `.80`
gate:

| motif | N | strength | TPR |
|---|---|---|---|
| chain | 750 | .5 | .776 |
| chain | 1000 | .5 | .780 |
| chain | 1500 | .5 | .788 |
| chain | 1500 | .7 | .792 |
| chain | 2000 | .3 | .760 |
| chain | 2000 | .5 | .780 |
| chain | 2000 | .7 | .768 |
| fork | 1000 | .3 | .796 |
| fork | 1000 | .5 | .788 |
| fork | 1000 | .7 | .792 |
| fork | 1500 | .3 | .784 |
| fork | 2000 | .7 | .792 |

`alpha = .10` itself is clean everywhere: no chain/fork cell below `.80`,
no triangle cell above `.10`.

With only 250 development replicates per cell, the binomial standard error
at a true value of `.80` is `~.025`, and at `.10` is `~.019`. Every failing
cell above misses its threshold by less than one standard error (`.024` for
the worst chain/fork miss, `.017` for the worst triangle miss). This looks
like sampling noise around a genuine boundary near `alpha ~ .10-.15`, not a
systematic failure at `.05` or `.20` — but the charter's rule does not
have a noise allowance, and R2d does not permit adding one after seeing
these numbers.

## Outcome

**REASSESS**, and a third distinct finding in this line of charters. R2
(D-002) found a structural confound (magnitude-ratio comparison). R2c
(D-004) found a selection-methodology artifact (pooled average masking a
per-cell failure). R2d finds neither: the per-cell rule, honestly applied,
finds a single isolated passing alpha with no adjacent partner, and its
near-misses are consistent with replicate-count noise rather than a real
gap. This points at insufficient development replicates for a per-cell
(rather than pooled) decision rule at the resolution of this alpha grid,
not at any remaining flaw in the mechanism itself.

See `raw_metrics.csv` (identical to R2c's), `aggregate_metrics.csv`,
`decision.json`, `calibration_summary.csv`, and the generated figures under
`results/generated/stage1d_dpi/` for complete evidence.
