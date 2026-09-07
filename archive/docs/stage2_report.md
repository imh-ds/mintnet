# Stage 2 Candidate-Edge Screening Report (R3)

Status: **PROCEED at both tested N**

## Run

`configs/stage2_screening.yaml`: `p=15` (chain, fork, `moderate` triangle
embedded in 6 noise columns; 9 true candidate pairs, 96 null pairs),
`N = [750, 1500]`, seven candidate rules (uncorrected `alpha in [.001,
.005, .01, .05, .10]`, BH `q in [.05, .10]`), 2000 replicates. 28,000 raw
rows, zero errors, runtime 14.6s.

## Decision table

`results/generated/stage2_screening/decision.json`:

| N | status | rule | threshold | validation recall | validation FDR |
|---|---|---|---|---|---|
| 750 | **PROCEED** | uncorrected | .001 | .9999 | .0109 |
| 1500 | **PROCEED** | uncorrected | .001 | 1.0000 | .0094 |

## Full operating picture (development, pooled): recall is never the constraint — FDR is

| threshold | recall | FDR |
|---|---|---|
| uncorrected .001 | ~1.00 | **.010-.011** (passes) |
| uncorrected .005 | ~1.00 | .045-.047 (passes, not selected — not simplest) |
| uncorrected .01 | ~1.00 | .087-.089 (passes, not selected) |
| uncorrected .05 | ~1.00 | .329-.330 (fails) |
| uncorrected .10 | ~1.00 | .499-.500 (fails) |
| BH q=.05 | ~1.00 | .045-.047 (passes, not selected — uncorrected preferred) |
| BH q=.10 | ~1.00 | .090-.093 (passes, not selected) |

Recall is essentially `1.0` at *every* tested threshold, at both `N` —
the embedded motifs' unconditional correlations are strong enough that
detecting "is there some signal here" is not the hard part of this
problem, matching the pre-registered expectation from `docs/stage2_charter.md`
that the 96:9 null:true imbalance, not statistical power, would be the
binding constraint. FDR tracks the back-of-envelope arithmetic in the
charter closely: at `alpha=.001`, predicted FDR was `~.012`; observed was
`.010`-`.011`.

## Is BH correction necessary here? No — but it isn't harmful either

Both BH thresholds (`q=.05`, `q=.10`) also pass the gate at both `N`. The
charter's predeclared tiebreak (prefer the simplest eligible rule) means
uncorrected `alpha=.001` wins over BH whenever both are eligible, which is
every tested condition here. This answers the charter's central question
directly: for this DGP (a small handful of well-separated true edges
against a much larger pool of null pairs), a simple uncorrected threshold
at a strict enough `alpha` controls false discoveries just as well as BH,
provided that `alpha` is chosen with the null:true ratio in mind rather
than a conventional default like `.05`.

## Outcome

**PROCEED at both `N = 750` and `N = 1500`.** Candidate-edge screening via
per-pair Fisher-z testing on raw correlation works at `p = 15`, using
Stage 1's own validated sample-size regime, with an uncorrected threshold
of `alpha = .001` sufficient — no BH correction required for this
configuration. This validates only the screening step in isolation, at
`p = 15`; it does not authorize composing screening with Stage 1's DPI
pruning into one pipeline, and does not authorize larger networks
(`p = 30` untested).

See `raw_metrics.csv`, `aggregate_metrics.csv`, `decision.json`, and
`screening_operating_curve.png` under `results/generated/stage2_screening/`
for complete evidence.
