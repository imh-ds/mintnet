# Stage 1f Fine Alpha-Resolution Report (R2f)

Status: **REASSESS**

## Run

Fresh frozen simulation, `configs/stage1f_dpi.yaml`: R2e's DGP, mechanism,
`N` grid, replicate count (2000: development 0-999, validation 1000-1999),
and per-cell selection rule, with a narrowed alpha grid at 0.01 resolution,
`[.06 ... .25]`. 2,880,000 raw rows generated, zero errors.

## Decision

`results/generated/stage1f_dpi/decision.json`: **REASSESS**. Development
selection found adjacent pair `(0.09, 0.10)` — the first ascending pair
where both members pass every individual cell on development data. It
fails validation at exactly one cell: `strong` family, `N = 750`,
`alpha = 0.09`, FPR `.104` against the `.10` gate — a miss of `.004`.

## The margin is now inside normal sampling noise, and the near miss points at a specific gap in the selection rule

At 1000 replicates per cell, SE for FPR at a true rate of `.10` is `~.0095`.
A `.004` miss is under half a standard error — the smallest, least
decisive failure in this entire line of charters. Reading the same cell
across the fine grid on both development and validation data:

| alpha | .08 | .09 | .10 | .11 |
|---|---|---|---|---|
| development FPR | .100 | .092 | .087 | .082 |
| validation FPR | .116 | **.104** | .098 | .089 |

`alpha = 0.09` was development-eligible only barely (`.092` against `.10`,
an `.008` margin, under 1 SE) and landed on the wrong side of the gate on
an independent validation sample — classic boundary noise. `alpha = 0.10`
and `alpha = 0.11` both hold comfortably on *both* development and
validation data at this cell. A pair of `(0.10, 0.11)` would very likely
have passed the full gate.

That pair was never tested against validation, because the frozen
selection rule returns the *first* ascending adjacent pair where both
members are development-eligible, and `(0.09, 0.10)` satisfied that
condition first — `0.09`'s eligibility being a coin-flip-margin call is not
something the rule accounts for. This is a second, different flaw in the
selection methodology from D-004's pooling artifact: a "first eligible
wins" rule has no way to prefer a pair with more margin over one that
barely, noisily cleared the bar.

## Outcome

**REASSESS**, but for the first time in this line of charters, the
evidence strongly suggests a specific untested pair (`0.10, 0.11`) would
pass, and the reason it wasn't reached is a property of the selection rule,
not the mechanism, the grid resolution, or the replicate count. Per this
charter, that observation cannot be used to retroactively substitute
`(0.10, 0.11)` for the rule's actual output.

See `raw_metrics.csv`, `aggregate_metrics.csv`, `decision.json`,
`calibration_summary.csv`, and the generated figures under
`results/generated/stage1f_dpi/` for complete evidence.
