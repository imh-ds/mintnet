# Stage 1h Per-N Alpha Selection Report (R2h)

Status: **per-N table — no single global status** (see `docs/stage1h_charter.md`)

## Run

Fresh frozen simulation, `configs/stage1h_dpi.yaml`: `N = [100, 200, 300,
500, 750, 1000, 1500, 2000, 3000]`, 23-point alpha grid `[.0001 ... .50]`,
2000 replicates (development 0-999, validation 1000-1999). 3,726,000 raw
rows generated, zero errors. Runtime 815.5s (~13.6 minutes).

**Note on data provenance:** because seed derivation is positional on
each sample size's index in the frozen `sample_sizes` list, the
simulated data at `N = 750, 1000, 1500, 2000` here is byte-identical to
R2c through R2g's data at those same sizes — this run re-simulated it
fresh rather than reading a file, but the underlying draws are the same
seeded outcome, not new independent samples. Only `N = 100, 200, 300,
500, 3000` include any condition not already evaluated at this alpha
resolution in an earlier charter (and `3000` is the only entirely new
sample size). What is new here is the **per-N selection rule** applied to
this data, not fresh replication at the shared `N` values.

## Decision table

`results/generated/stage1h_dpi/decision.json`:

| N | status | selected alpha pair | worst-case margin |
|---|---|---|---|
| 100 | REASSESS | none | — |
| 200 | REASSESS | none | — |
| 300 | REASSESS | none | — |
| 500 | REASSESS | none | — |
| 750 | **PROCEED** | `(0.14, 0.16)` | .032 |
| 1000 | **PROCEED** | `(0.12, 0.14)` | .041 |
| 1500 | **PROCEED** | `(0.10, 0.12)` | .075 |
| 2000 | **PROCEED** | `(0.08, 0.10)` | .087 |
| 3000 | **PROCEED** | `(0.06, 0.08)` | .099 |

Two clean trends at `N >= 750`: the working alpha **decreases** as `N`
grows, and the margin **increases** — more data both lets a stricter
significance threshold work and makes the pass more robust. This is
exactly the shape needed to inform a future `alpha(N)` default rule (not
fit here; see charter).

## Why N < 750 fails: two different kinds of "no"

Reading the worst-case TPR and FPR across the full alpha sweep (development
replicates) at each small `N` shows where the TPR-satisfying region (small
alpha) and the FPR-satisfying region (large alpha) do or do not overlap:

| N | TPR satisfied up to alpha | FPR satisfied from alpha | gap |
|---|---|---|---|
| 100 | .18 | never (worst FPR is still `.137` at `alpha=.50`) | decisive, unbridgeable |
| 200 | .18 | `.50` (barely, `.099`, with TPR already collapsed to `.489`) | decisive, unbridgeable |
| 300 | .18 | ~.35-.40 | wide (~.17-.20), TPR would be ~.60-.65 there — decisive |
| 500 | .18 (`.802`) | .20 (`.099`) | **narrow — one grid step (.02)** |

`N = 100`, `200`, and `300` are **decisive within the tested alpha grid**
(`.0001` to `.50`): there is no alpha in that grid where both criteria
hold at once — pushing alpha up far enough to fix the triangle FPR
destroys chain/fork TPR long before it gets there. This is not a
grid-resolution artifact within the tested range; it is the same kind of
real, wide gap the pooled global charter (R2) diagnosed originally, now
appearing per-sample-size instead of per-family. This is not a proof that
no alpha value whatsoever, at any resolution or magnitude beyond `.50`,
could work — only that none does within the range actually tested.

`N = 500` is different: the gap between `.18` (TPR passes, FPR fails at
`.107`) and `.20` (FPR passes, TPR fails at `.780`) is only one grid step.
This is the same shape as R2f's razor's-edge finding — plausibly
resolvable with finer alpha resolution near `.19`, but even if resolved,
the surviving margin would be thin, consistent with `N = 500` sitting
right at the edge of viability. This is a striking, quantitative
confirmation of R2c's original reasoning for raising the gate floor from
`500` to `750`: `N = 500` is not simply "a bit worse," it is quantitatively
right on the boundary, while `N <= 300` is a clear, decisive no.

## Exploratory evidence: `1 - p_value` as a candidate confidence-style score (non-gating; not a validated calibration)

Brier score of `1 - p_value` against ground truth remains stable and well
below the naive `.25` baseline across the entire extended `N` range,
`100`-`3000` (consistent with every prior round; see
`calibration_summary.csv`).

## Outcome

This charter does not produce one PROCEED/REASSESS; it produces the
evidence table above. Three findings:

1. `N >= 750` is validated across a wide range with a clean, monotonic
   alpha-vs-`N` relationship, strengthening (not just repeating) R2g's
   single-point result at `N in [750, 2000]` and extending it to `3000`.
2. `N <= 300` is a decisive, structural "no" — no alpha rescues it, not a
   resolution problem.
3. `N = 500` is a genuine boundary case with a narrow, possibly-resolvable
   gap, but even in the best case would have little margin — consistent
   with, and now quantitatively explaining, R2c's original choice of a
   `750` floor.

See `raw_metrics.csv`, `aggregate_metrics.csv`, `decision.json`,
`calibration_summary.csv`, and the generated figures (including
`margin_vs_n.png`) under `results/generated/stage1h_dpi/` for complete
evidence.
