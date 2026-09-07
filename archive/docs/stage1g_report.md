# Stage 1g Margin-Robust Selection Report (R2g)

Status: **PROCEED**

## Run

Reused R2f's raw evidence verbatim (`results/generated/stage1f_dpi/raw_metrics.csv`,
2,880,000 rows, zero errors) under the frozen R2g margin-robust
development-selection rule: among adjacent alpha pairs where both members
pass every individual cell, select the pair maximizing the worst-case
margin, not the first pair found.

## Decision

`results/generated/stage1g_dpi/decision.json`: **PROCEED**. Selected pair
`(0.14, 0.15)`. Every validation cell (all three families, all four `N in
[750, 1000, 1500, 2000]`, all three strengths, both alpha values) passes
individually, with real margin:

- Worst-case chain/fork TPR margin: `.031` above the `.80` gate.
- Worst-case triangle FPR margin: `.021` below the `.10` gate.

Both margins are comfortably larger than the `~.01` standard error at 1000
validation replicates — this is not a boundary call.

## Why this pair, not (0.10, 0.11)

R2f's report flagged `(0.10, 0.11)` as a strong candidate the "first
eligible pair wins" rule never reached. The margin-robust rule considered
every adjacent eligible pair in the grid and found `(0.14, 0.15)` has more
worst-case slack across all cells simultaneously — not just at the single
`strong`-family cell that broke `(0.09, 0.10)` in R2f. This is exactly the
outcome the charter intended: a pair chosen for robustness across the full
evidence, not the first one to cross zero.

## Exploratory evidence: `1 - p_value` as a candidate confidence-style score (non-gating; not a validated calibration)

Brier score of `1 - p_value` against ground truth (development replicates,
naive baseline `.25`), unchanged in character from every prior round:

| N | 100 | 200 | 300 | 500 | 750 | 1000 | 1500 | 2000 | pooled |
|---|---|---|---|---|---|---|---|---|---|
| Brier | .096 | .086 | .082 | .079 | .076 | .077 | .074 | .074 | .080 |

## Outcome

**PROCEED.** This closes the R2 through R2g line of Stage 1 evidence.
Conditional-independence pruning via Gaussian partial correlation, at
`alpha` in `[0.14, 0.15]`, correctly distinguishes indirect (chain/fork)
edges from genuine (triangle) edges across all three triangle fixtures, at
`N >= 750`, with margin. The validated scope is specifically: continuous
Gaussian data, `N >= 750`, three-node motifs, `alpha` near `0.14`-`0.15`.
This does not select a public default `alpha` beyond this pair, and does
not by itself authorize a specific Stage 2 design — it authorizes planning
Stage 2 candidate-edge screening using this validated mechanism and scope.

See `raw_metrics.csv` (identical to R2f's), `aggregate_metrics.csv`,
`decision.json`, `calibration_summary.csv`, and the generated figures
under `results/generated/stage1g_dpi/` for complete evidence.
