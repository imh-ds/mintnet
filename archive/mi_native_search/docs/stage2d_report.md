# Stage 2d Overlap-Wiring Report (R3f)

Status: **Split outcome, exactly as predicted — REASSESS at N=750, PROCEED at N=1500**

## Run

`configs/stage2d_composition.yaml`: `p=15` (chain, fork, the shared-node
overlap motif, and 4 noise columns), `VALIDATED_CLIQUE_SIZES` extended to
include 5, screening at `alpha=.001`, DPI at `alpha=f(N)`, `N = [750,
1500]`, 2000 replicates. 4,000 raw rows, zero errors, runtime 56.9s.

## Decision table

`results/generated/stage2d_composition/decision.json`:

| N | status | chain TPR | fork TPR | overlap TPR | true-edge FPR | overlap clean rate |
|---|---|---|---|---|---|---|
| 750 | **REASSESS** | .816 | .815 | **.569** | .000 | **.287** |
| 1500 | **PROCEED** | .868 | .860 | .817 | .000 | .921 |

## The predicted outcome occurred almost exactly

`docs/stage2d_charter.md`'s pre-charter simulation predicted, before any
frozen results existed: `N=750` overlap TPR `~.59` (observed `.569`),
clean-clique rate `~26%` (observed `28.7%`); `N=1500` overlap TPR `~.82`
(observed `.817`), clean-clique rate `~89%` (observed `92.1%`). Every
number landed within a few percentage points of its prediction.

Chain and fork — the two motifs expected to behave normally — did:
`.815`-`.868` TPR at both `N`, consistent with their established
behavior in every prior charter. **Per-motif gating caught exactly the
problem it was designed to catch**: a pooled average across all three
motifs at `N=750` would have been `(.816 + .815 + .569) / 3 = .733` —
still a REASSESS on its own, but by a much smaller, less legible margin,
and at `N` values with more motifs a pooled average could plausibly have
hidden the same problem D-004 already taught this project to watch for.

## Why REASSESS at N=750 is not a failure of the mechanism

The conditioning mechanism itself was already validated on this exact
topology, in isolation, with real margin (D-017: TPR `.858` at `N=750`
when handed a clean component directly). Here, at the same `N`, the
pipeline-level overlap TPR is far lower (`.569`) purely because a clean
candidate clique only forms `28.7%` of the time — the other `71.3%` of
replicates, DPI is correctly *not* applied (per the conservative,
validated-shapes-only design), and the candidate edges screening flagged
(including some correctly-detected but not-yet-pruned cross-branch pairs)
simply pass through un-pruned. This is the screening-detection-power
limitation flagged explicitly in D-017's consequences, now measured
rather than assumed.

## Outcome

**REASSESS at `N=750`, PROCEED at `N=1500`.** Extending
`VALIDATED_CLIQUE_SIZES` to include size 5 is confirmed safe and correct
*when the mechanism gets a chance to run* (matching D-017), but for this
specific DGP's weak cross-branch signal, that chance is unreliable at
`N=750` and reliable at `N=1500`. This is a **DGP- and `N`-dependent
screening-power limitation, not a defect in the generalized pipeline
code** — the same code, same `alpha` values, and same conditioning
mechanism produced a clean PROCEED for the hub shape (D-016) at both
tested `N`, because the hub's signal was strong enough for screening to
detect reliably at `N=750` too.

**Practical consequence**: trusting a size-5 candidate clique for
shared-node-overlap-like weak-signal structures should not be assumed
safe below `N=1500` without separately checking the specific DGP's
detection power, the way this charter did. This is a genuinely different,
narrower floor than the `N=700`-`750` floor established for the
DPI mechanism itself (D-010/D-011) — it is specific to *screening's*
power for this signal strength, a distinct bottleneck from the ones
characterized so far.

See `raw_metrics.csv`, `decision.json`, and
`overlap_clean_clique_vs_tpr.png` under
`results/generated/stage2d_composition/` for complete evidence.
