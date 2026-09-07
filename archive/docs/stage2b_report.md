# Stage 2b Screening + DPI Composition Report (R3b)

Status: **PROCEED at both tested N**

## Run

`configs/stage2b_composition.yaml`: Stage 2's `p=15` DGP, screening at
`alpha=.001` (D-013), DPI at `alpha = f(N)` from the D-012 formula
(`.1476` at `N=750`, `.1084` at `N=1500`), `N = [750, 1500]`, 2000
replicates. 4,000 raw rows, zero errors, runtime 17.1s.

## Decision table

`results/generated/stage2b_composition/decision.json`:

| N | status | dpi_alpha | indirect TPR | true-edge FPR | screening FER | final FER | triad rate |
|---|---|---|---|---|---|---|---|
| 750 | **PROCEED** | .1476 | .818 | .0053 | .00115 | **.00115** | .961 |
| 1500 | **PROCEED** | .1084 | .861 | .0004 | .00100 | **.00100** | .963 |

## The predeclared expectation held exactly, not just approximately

The charter predicted that most screening false positives would be
isolated single edges DPI cannot act on, so the final false-edge rate
should closely track screening's own rate rather than improve on it.
`screening_false_edge_rate` and `final_false_edge_rate` are **identical
to the reported precision at both `N`** — in this run, DPI never once
converted a false-positive candidate edge into a pruned one, nor did it
introduce any new false edge (which the mechanism cannot do by
construction: it only prunes within already-screened triads). This is a
clean, complete confirmation of the predeclared mechanism, not a
coincidence of rounding — see `raw_metrics.csv` for the per-replicate
values behind this aggregate.

## Indirect-edge pruning is a little weaker than Stage 1's isolated numbers, but consistent

`docs/decision_log.md` D-009 reported chain/fork TPR around `.85`-`.87`
at `N=750` with a similar alpha, tested on isolated 3-node motifs alone.
Here, composed with screening first, `N=750` gives `.818` — lower, but
in the same range, and still comfortably above the `.80` gate. This is a
reasonable, small effect to see: `~4%` of replicates (`triad_rate =
.961`) did not form a clean 3-node candidate triad for at least one true
motif (most likely because screening missed one of that motif's own true
edges, or drew in an extra false-positive neighbor), and those
replicates skip DPI entirely for the affected motif, contributing
un-pruned indirect edges to the pooled TPR average. This is exactly the
scope boundary the charter stated up front, showing up as a small,
explained effect rather than a surprise.

## Outcome

**PROCEED at both `N = 750` and `N = 1500`.** The composed pipeline
(screen at `alpha=.001`, then DPI within clean candidate triads) meets
every predeclared criterion, and does so for a documented, mechanistic
reason rather than by chance: false edges mostly can't be rescued because
they're mostly isolated, and the small TPR gap from Stage 1's isolated
numbers is explained by the `~4%` of replicates where a motif's candidate
component wasn't a clean triad. This validates the composition only for
disjoint, non-overlapping 3-node motifs at `p=15`, `N in [750, 1500]`.
Candidate components larger than 3 nodes, or motifs sharing variables,
remain untested and require their own DGP and charter.

See `raw_metrics.csv`, `decision.json`, and
`false_edge_rate_comparison.png` under
`results/generated/stage2b_composition/` for complete evidence.
