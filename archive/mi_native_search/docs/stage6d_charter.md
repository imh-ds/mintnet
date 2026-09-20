# Stage 6d Charter: Re-Validation of the Corrected Local-Permutation Construction (mi-native)

Status: **FROZEN before results**
Date: 2026-09-03

## Background and objective

D-055 (Stage 6c) found, with properly-powered evidence (400
replicates/cell, Wilson CIs), that the local-permutation significance
test was genuinely miscalibrated at `|S| in {1, 2}` under every swept
`k_perm` value -- a confirmed defect in the shuffle *construction*
itself, not a tunable parameter. D-055's own required next step was a
direct comparison against Runge (2018)'s reference implementation
(`tigramite.independence_tests.cmiknn.CMIknn`). That comparison found
three structural discrepancies, now fixed in `mintnet.mi.cmiknn`
(see that module's own updated docstring for the full description):

1. Self-inclusion in each point's own Z-neighbor list (previously
   excluded).
2. **The likely primary cause**: on local-neighborhood exhaustion, the
   reference reuses the last-tried neighbor (an accepted, rare
   collision) rather than reaching outside the neighborhood; the prior
   version fell back to a uniformly random point from the *entire*
   dataset, which could be arbitrarily far in Z-space.
3. Distance metric: Chebyshev/max-norm (matching this module's own
   `estimate_cmiknn` convention), not `scipy`'s Euclidean default.

This charter re-runs **exactly Stage 6c's own design** (same grid, same
gate, same reporting) against the corrected construction only. Nothing
about the experimental design changes -- this is a re-test of a fixed
mechanism, not a new experiment, so it reuses Stage 6c's own charter
text by reference rather than restating it. Any deviation from that
design here is itself a finding, not a redesign.

## Design (identical to Stage 6c's Stage B; see docs/stage6c_charter.md)

- Fixed `k_CMI = 40` (Stage 6c's own Stage A recommendation; not
  re-derived here, since the fix is to the significance test's
  shuffle, not the point estimator).
- `k_perm in {3, 5, 10, 20, adaptive}`, `adaptive = clip(round(0.05 *
  N), 3, 20)`.
- `N in {150, 300, 750}`.
- `|S| in {0, 1, 2, 3}`, same four null conditions
  (`s0_null`..`s3_null`), same DGPs.
- `permutations = 199`, `replicates = 400` per cell.
- Run as isolated GitHub Actions shards via the same
  `mintnet.experiments.stage6c_b` entry point and
  `sharded_benchmark.yml` dispatch used for Stage 6c -- no new
  infrastructure. The runner module and config are unchanged; only the
  underlying `mintnet.mi.cmiknn._restricted_permutation` construction
  it calls has changed.

## Selection and gate (identical to Stage 6c's own)

A regime `(k_CMI, k_perm)` is defensible if, across every tested `N`
and `|S|` cell: the empirical rejection rate at `alpha=.05` falls in
`[.03, .07]` or its Wilson 95% CI contains `.05`, and likewise
`[.005, .015]`/`.01` at `alpha=.01`.

**PROCEED** if at least one swept `k_perm` value is defensible
everywhere -- smallest such value preferred as the operational
default. **REASSESS** otherwise, with the same pattern analysis Stage
6c used (by `|S|`, by `N` within `k_perm`) to characterize any
remaining miscalibration.

**If REASSESS again**: this would mean the three fixes identified are
necessary but not sufficient, or a fourth discrepancy remains
unidentified -- the next step would be a more exacting line-by-line
audit (or reproducing tigramite's own test suite locally against this
project's DGPs) rather than another guess. Not expected, given the
specificity of the D-055 pattern (flat-with-N liberal bias
concentrated exactly where local exhaustion is most plausible) to the
exhaustion-fallback discrepancy, but stated here in case it recurs.

**If PROCEED**: `mi-native` may plan a Stage-1-equivalent composition
charter (D-053/D-054's own named next step), using the selected
`k_perm` as the operational default.

## Explicit non-goals

Identical to Stage 6c's own: no `N=1500`, no composition into DPI, no
`k_perm`-by-`|S|` joint rule beyond what's already swept, no
resolution of `alpha < .01`.

## Required evidence

Same as Stage 6c: resolved configuration, this charter's SHA-256,
commit/runtime metadata, raw per-replicate evidence, per-cell Wilson CI
table, pattern-analysis tables, decision, report. Reported alongside
(not replacing) Stage 6c's own D-055 evidence, so the before/after
comparison is directly visible.
