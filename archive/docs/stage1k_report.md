# Stage 1k Multi-Variable Conditioning Report (R3c)

Status: **PROCEED at both tested N**

## Run

`configs/stage1k_hub.yaml`: a 4-node hub motif (1 hub, 3 children,
strength `.5`), `N = [750, 1500]`, `alpha = f(N)` from the existing D-012
formula (`.1476` at `750`, `.1084` at `1500`) tested directly — no new
grid search. 2000 replicates, zero errors, runtime 4.7s.

## Decision table

`results/generated/stage1k_hub/decision.json`:

| N | alpha | status | indirect TPR | true-edge FPR | margin |
|---|---|---|---|---|---|
| 750 | .1476 | **PROCEED** | .854 | .000 | .054 |
| 1500 | .1084 | **PROCEED** | .887 | .000 | .087 |

## The D-012 formula generalizes to two-variable conditioning without modification

Both `N` clear the `.02` required margin comfortably — `.054` and `.087`,
not thin-margin passes. True-edge retention is perfect (`FPR = 0` at both
`N`): conditioning a hub-child edge on the other two children never wrongly
prunes it. Indirect-edge pruning (child-child pairs, conditioned on the
hub and the third child) is a little below the same formula's
one-variable-conditioning numbers at these `N` (D-008/D-009: `~.85`-`.86`
at `750`; here `.854`, close), consistent with two-variable conditioning
costing a small amount of statistical power relative to one-variable
conditioning at the same `N` and `alpha` — expected, since the Fisher-z
degrees of freedom drop by one additional unit (`N - 3 - 2` vs.
`N - 3 - 1`), and the result lands almost exactly where a quick
pre-registered simulation (run before freezing the charter, using this
same formula and DGP) predicted: `TPR ~ .858`/`.882`, `FPR = 0` at
`750`/`1500`.

## Outcome

**PROCEED at both `N = 750` and `N = 1500`.** "Condition on every other
node in the candidate component" — the direct generalization of Stage 1's
validated one-variable partial correlation — works for this 4-node hub
shape, using the already-validated `alpha(N)` formula unmodified. This is
a genuinely useful, non-obvious result: a formula fit only for
one-variable conditioning did not need refitting for two-variable
conditioning to still clear a comfortable margin.

This validates the mechanism only for this one hub shape (one shared
cause, several independent children). Components with a different
structure — two motifs sharing a node rather than a single shared cause,
or larger components still — remain untested and would need their own
charter, per the charter's stated scope.

See `raw_metrics.csv`, `decision.json`, and `resolved_config.yaml` under
`results/generated/stage1k_hub/` for complete evidence.
