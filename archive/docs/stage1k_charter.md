# Stage 1k Charter: Multi-Variable Conditioning for Non-Triad Components (R3c)

Status: **FROZEN before results**
Date: 2026-08-29

## Background and objective

Stage 2b's composed pipeline (`docs/decision_log.md` D-014) validated DPI
pruning only within candidate components that are exactly a 3-node,
3-edge triad — the one shape where "which variable to condition on" is
unambiguous. It explicitly passed every other component shape through
unmodified, flagging overlapping motifs and hub structures as a distinct,
unresolved question. This charter addresses that question directly, using
the smallest DGP that forces it.

**The new mechanism decision, stated plainly:** when a candidate edge
`(i, j)` sits in a component with more than one other node, which of
those other nodes should the conditional-independence test condition on?
This charter tests one principled candidate answer — **condition on every
other node in the component**, the direct generalization of Stage 1's
one-variable partial correlation to a multi-variable partial correlation
(still exact and closed-form for jointly Gaussian data via linear
regression residuals) — rather than trying several competing designs at
once. If this fails, competing designs (e.g., conditioning only on shared
neighbors, or a stepwise/iterative approach) become a distinct follow-up
question, not something to explore simultaneously here.

**DGP choice, deliberately minimal:** a single hub variable with three
children (`X0 -> X1`, `X0 -> X2`, `X0 -> X3`, no direct edges among the
children), tested in isolation — not embedded in Stage 2's `p=15`
screening network. This is the smallest structure where a candidate
component has more than 3 nodes at all (4 nodes here), and it isolates
the multi-variable conditioning question from screening or scale,
mirroring how Stage 1's original charters tested DPI in isolation before
Stage 2 ever introduced screening.

## Data-generating process

`sample_hub(n, strength, rng)`: `X0 ~ N(0,1)`; each of `X1, X2, X3 =
strength * X0 + sqrt(1 - strength^2) * noise_i`, independent noise per
child (the direct three-child generalization of the already-validated
measured-fork DGP, which is the two-child case). Strength `a = .5`
(matching every prior Stage 1/2 charter). `N = [750, 1500]` — Stage 1 and
Stage 2's shared validated regime; this charter does not reopen the `N`
floor question.

**Ground truth**: true direct edges `(X0,X1)`, `(X0,X2)`, `(X0,X3)` (3);
indirect edges `(X1,X2)`, `(X1,X3)`, `(X2,X3)` (3) — each child pair is
correlated only through the shared hub and should be pruned once
conditioned on it.

Master seed `20260829`, 2000 replicates (development 0-999, validation
1000-1999).

## Mechanism

New code: a general multi-variable partial correlation and Fisher-z test,
extending `mintnet.dpi.conditional`'s one-variable case. For target pair
`(i, j)` and conditioning set `S` (here, the other two children), compute
the partial correlation via linear-regression residuals (regress `X_i`
and `X_j` each on `S`, correlate the residuals), then:

```
z = atanh(r_ij.S) * sqrt(N - 3 - |S|)
p = 2 * (1 - Phi(|z|))
```

generalizing Stage 1's `sqrt(N - 4)` (the `|S| = 1` case) to `|S| = 2`
here. Retain edge `(i, j)` if `p <= alpha`.

**Alpha**: no new grid search. Test the single value `alpha = f(N)` from
the already-validated D-012 formula (`alpha(N) = 0.5222 - 0.0566 *
ln(N)`) as the first candidate — the same value already validated for
`|S| = 1` conditioning. Whether it also works for `|S| = 2` is itself
part of what this charter tests, not assumed.

## Selection and gate

No selection step, mirroring Stage 1j's held-out-prediction style: the
formula's predicted `alpha_hat` is tested directly. Per `N`, on
validation replicates (1000-1999):

1. Indirect-edge pruning TPR (child-child pairs correctly pruned) `>= .80`.
2. True-edge retention FPR (hub-child edges wrongly pruned) `<= .10`.
3. Both margins `>= .02` (D-011's "comfortable, not thin" standard).

**PROCEED** for a given `N` only if all three hold with no recorded
error. **REASSESS** otherwise.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate evidence (retain/prune status for all 6
pairs), aggregate metrics, the per-N decision table, report, and figures.

## Consequences

If PROCEED at both `N`: "condition on every other node in the component"
is validated for this one 4-node hub shape, and becomes a candidate
general rule to extend Stage 2b's composed pipeline beyond exact triads —
but only for this shape. Components with a different structure (e.g., two
motifs sharing a node rather than one hub with several children, or
larger components still) remain untested and would need their own
charter before being trusted.

If REASSESS: the D-012 formula does not directly generalize to
multi-variable conditioning, which is itself a real, useful finding — it
would mean the conditioning-set size needs its own alpha(N) relationship,
not a reused one, before this mechanism can be composed into the pipeline
at all.
