# Stage 2c Mixed Triad/Hub Composition Report (R3d)

Status: **PROCEED at both tested N**

## Run

`configs/stage2c_composition.yaml`: `p=15` (chain, fork, and a 4-node hub
with 3 children, plus 5 noise columns), screening at `alpha=.001`, DPI
via the generalized `mintnet.pipeline.compose` at `alpha=f(N)`, `N =
[750, 1500]`, 2000 replicates. 4,000 raw rows, zero errors, runtime 23.0s.

## Decision table

`results/generated/stage2c_composition/decision.json`:

| N | status | dpi_alpha | indirect TPR | true-edge FPR | screening FER | final FER | triad/hub rate |
|---|---|---|---|---|---|---|---|
| 750 | **PROCEED** | .1476 | .820 | .000 | .00101 | **.00101** | .965 |
| 1500 | **PROCEED** | .1084 | .853 | .000 | .00120 | **.00120** | .958 |

## Every prior finding replicated in the mixed-shape network

- **Screening and final false-edge rates are identical at `N=1500`**
  (`.0012043` both) and **nearly identical at `N=750`** (screening
  `.00101075` vs. final `.00100000` — one fewer false edge survives to
  the final rate, not literally zero difference), closely reproducing
  D-014's finding that DPI cannot rescue isolated false positives — now
  in a network where DPI is also acting on 4-node hub components, not
  only 3-node triads. (Corrected 2026-08-30, second peer review: the
  original text overstated this as "identical" at both `N`.)
- **True-edge retention is perfect** (`FPR = 0` at both `N`), matching
  both D-014 (triads) and D-015 (hub in isolation).
- **Indirect-edge TPR landed almost exactly where the pre-charter check
  predicted** (`.820` observed vs. `.823 +/- .005` predicted at `N=750`
  from a 1500-replicate simulation run before freezing the charter) — a
  successful pre-specified prediction, not independent confirmation
  (the pre-charter check and the frozen run share the same DGP and code
  assumptions), but still useful evidence that composing two validated
  shapes in one network doesn't introduce a new, unpredicted interaction.
- **Shape-validation rate** (`~.96`) matches D-014's own `~.96` for the
  triad-only network, suggesting the rate at which a motif fails to form
  its clean candidate shape is a property of screening noise in general,
  not specific to any one motif shape.

## Outcome

**PROCEED at both `N = 750` and `N = 1500`.** The generalized composed
pipeline — screening, then DPI within any validated clique shape (3-node
triad or 4-node hub) — works correctly when both shapes coexist in the
same network and the same screening pass, with no detectable interaction
effect between them. Combined with D-014 and D-015, and the confirmed
byte-for-byte regression check against D-014's original numbers before
this charter ran, the pipeline generalization from Stage 2b's triad-only
version is validated, not merely assumed safe.

This remains scoped to `p=15`, `N in [750, 1500]`, and validated clique
shapes only (sizes 3 and 4). Larger networks, non-clique candidate
components, or components sharing variables across motifs remain
untested.

See `raw_metrics.csv`, `decision.json`, and
`false_edge_rate_comparison.png` under
`results/generated/stage2c_composition/` for complete evidence.
