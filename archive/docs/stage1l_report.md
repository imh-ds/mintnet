# Stage 1L Shared-Node-Overlap Report (R3e)

Status: **PROCEED at both tested N**

## Run

`configs/stage1l_overlap.yaml`: two `balanced`-style triangles sharing
one node (5 variables total), `N = [750, 1500]`, `alpha = f(N)` from the
unmodified D-012 formula, each edge conditioned on the other 3 nodes in
the component. 2000 replicates, zero errors, runtime 16.1s.

## Decision table

`results/generated/stage1l_overlap/decision.json`:

| N | alpha | status | indirect TPR | true-edge FPR | margin |
|---|---|---|---|---|---|
| 750 | .1476 | **PROCEED** | .858 | .000 | .057 |
| 1500 | .1084 | **PROCEED** | .894 | .000 | .094 |

## The mechanism generalizes to a genuinely different topology, not just bigger stars

Both `N` clear the `.02` required margin comfortably. True-edge retention
is perfect (`FPR = 0`) at both `N` — conditioning a within-triangle edge
on all 3 other nodes (the other triangle-mate plus both members of the
*other* triangle) never wrongly prunes it, even though two of those
conditioning variables belong to a structurally unrelated triangle.
Indirect-edge pruning (the weak, `~.135`-correlation cross-branch pairs)
is comfortably above `.80` at both `N`, close to a pre-charter
1000-replicate simulation's prediction (`TPR ~ .847`/`.884`).

This is a materially different topology from Stage 1k's hub (D-015): a
hub has one shared cause radiating outward with no further structure past
the children, while this DGP has two independent local structures
(triangles) meeting only at a single point. That the same "condition on
everyone else in the component" rule works for both, using the same
unmodified `alpha(N)` formula, is evidence the mechanism is a genuinely
general conditional-independence test, not one that happened to fit the
star shape specifically.

## What this charter deliberately does not test

Per `docs/stage1l_charter.md`, this result says nothing about whether
Stage 2-style screening would reliably detect the weak (`~.135`)
cross-branch correlation and hand DPI a clean 5-node candidate clique to
work with in the first place — the pre-charter power calculation showed
that detection is unreliable at `N=750` (`~66%` power at
`alpha=.001`) and much better at `N=1500` (`~98%`). This charter isolates
the conditioning mechanism from that separate, real concern, which
remains open for a follow-up wiring charter (mirroring how Stage 1k
preceded Stage 2c).

See `raw_metrics.csv`, `decision.json`, and `resolved_config.yaml` under
`results/generated/stage1l_overlap/` for complete evidence.
