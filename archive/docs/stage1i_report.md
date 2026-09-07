# Stage 1i N=500-750 Crossover Report (R2i)

Status: per-N table — no single global status (see `docs/stage1i_charter.md`)

## Run

Fresh simulation for `N = [550, 600, 650, 700]` (`configs/stage1i_dpi.yaml`,
same alpha grid, replicate count, and per-N margin-robust selection rule as
R2h), merged with R2h's `N = 500, 750` rows as bookends
(`results/generated/stage1h_dpi/raw_metrics.csv`). 2,484,000 raw rows total
(1,656,000 newly simulated), zero errors. Runtime 753.7s (~12.6 minutes).

## Decision table

`results/generated/stage1i_dpi/decision.json`:

| N | status | selected alpha pair | margin |
|---|---|---|---|
| 500 | REASSESS | none | — |
| 550 | REASSESS | none | — |
| 600 | REASSESS | none | — |
| 650 | REASSESS | (0.14, 0.16) — failed validation | .018 (development) |
| 700 | **PROCEED** | (0.14, 0.16) | .012 |
| 750 | **PROCEED** | (0.14, 0.16) | .032 |

## The crossover is narrower than expected, and thinner than R2h's N=750 result

`500`, `550`, and `600` don't even find a development-eligible alpha pair
— no adjacent pair passes every cell, consistent with R2h's finding that
`N=500` is a genuine (if narrow) boundary case rather than noise. `650` is
a step further: development *does* find `(0.14, 0.16)` eligible, but it
fails validation on triangle FPR — a near-miss, in the same family as
several earlier near-misses in this line of charters (R2d, R2f).

`700` is the first sample size to fully PROCEED — but with a margin of
`.012`, close to the ~`.0095`-`.0126` standard error at 1000 replicates
established in D-006/D-009. This is a real pass, not a coin flip (it's a
positive margin, and validation is a genuinely separate replicate split
from development), but it is *thin* — roughly `1.3` standard errors of
headroom, not the comfortable `3`-`4`x-noise margin R2g/R2h established at
`N=750` (`.032`) and beyond. `750` remains the first sample size with a
clearly comfortable margin.

## Outcome

The crossover sits in a narrow band: **no viable pair at N<=600, a
near-miss at N=650, a thin-but-real pass at N=700, a comfortable pass at
N=750.** This substantially tightens what was previously just "N>=750" as
a round, conservative floor:

- **N=700 is a legitimate, evidence-based floor** if a thin margin is
  acceptable — it passed its own predeclared validation split.
- **N=750 remains the floor to use when a comfortable, noise-robust
  margin matters** (e.g., as a default for autonomous use in
  `docs/validated_operating_ranges.md`).
- **N<=650 is not viable** at this DGP and alpha grid; `650` in particular
  is close but not there.

Per `docs/stage1i_charter.md`'s consequences: this is a broadly monotonic
transition (REASSESS through 600, near-miss at 650, PROCEED from 700 with
increasing margin through 750), not the noisy, non-monotonic pattern that
would have warranted treating the result as inconclusive. The floor can be
reasonably tightened, with the `700` vs `750` distinction stated
explicitly as thin-margin vs comfortable-margin rather than collapsed into
one number.

See `raw_metrics.csv`, `aggregate_metrics.csv`, `decision.json`,
`calibration_summary.csv`, and the generated figures under
`results/generated/stage1i_dpi/` for complete evidence.
