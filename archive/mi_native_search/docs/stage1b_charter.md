# Stage 1b Charter: Conditional-Independence Motif Validation (R2b)

Status: **FROZEN before results**
Date: 2026-08-28

## Background and objective

`docs/stage1_charter.md` chartered tolerant DPI (pruning the weakest of three
pairwise MI edges when it falls below `(1 - tau) * min(other two MIs)`). The
frozen R2 run (`docs/decision_log.md`, D-002) returned REASSESS: chain/fork
indirect-edge pruning TPR was satisfied at every tested tau, but triangle
true-edge pruning FPR never cleared the `.10` gate, even at `tau = .50`. A
per-family breakdown showed the failure is concentrated in the `moderate` and
`strong` triangle fixtures, where one genuine edge is, by construction,
markedly weaker than the other two. Magnitude-ratio comparison cannot
distinguish "real but weaker" from "fake and indirect" — both look identical
to a rule that only compares pairwise MI sizes to each other.

This charter tests a different mechanism: **prune an edge based on its own
conditional dependence, not on how its magnitude compares to its neighbors.**
For a chain or fork, `X1` and `X3` should be conditionally independent given
`X2`; for a genuine triangle, they should not be, regardless of the raw
pairwise MI ranking. This directly targets the confound identified in R2 and
does not require modifying the frozen R2 charter, whose evidence and REASSESS
outcome stand as recorded.

**Scope note — this is a fast Gaussian-equivalence check, not a resolution of
the estimator question.** For jointly Gaussian variables, conditional mutual
information is a strictly monotonic function of partial correlation:
`I(X1;X3|X2) = -0.5 * ln(1 - r_13.2^2)`. Testing partial correlation against
zero and testing conditional MI against zero are therefore the same decision
rule on this DGP, not two different methods. This charter uses the
closed-form partial-correlation test because it is exact and requires no new
estimator, not because partial correlation is the project's chosen mechanism
going forward. The bivariate KSG pairwise MI used in the R1/R2 charters is,
for the same reason, already a monotonic function of Pearson `r` on Gaussian
data — Stage 0 and Stage 1 have operated in this regime from the start, and
R2b does not newly introduce it.

This charter's result therefore answers a narrower question than "does
conditional MI fix the R2 failure": it answers "does conditioning on the
mediator, tested exactly, fix the R2 failure, in the Gaussian case." If it
does not, the DPI-by-conditioning logic itself is broken independent of
estimator choice, and no nonparametric conditional-MI estimator needs
building to know that. If it does, that result is valid only for the
Gaussian regime already chartered here; it does not validate, and must not
be cited as validating, any conditional-MI estimator for the outline's
future nonlinear or mixed-type stages. A separate charter to build and
validate a nonparametric conditional-MI estimator (with its own Stage-0-style
bias/variance evidence) remains a prerequisite before that generalization is
trusted for a gate.

## Data-generating process

Identical to `docs/stage1_charter.md`, reused unmodified for direct
comparability to the R2 baseline: chain (`X1 -> X2 -> X3`), measured fork
(`X1 <- X2 -> X3`), and the `balanced`/`moderate`/`strong` triangle
precision-matrix fixtures. `N = [100, 200, 300, 500, 750, 1000]`, strengths
`a = b = [.3, .5, .7]`, 500 replicates, master seed `20260829`, development
replicates 0-249, validation replicates 250-499.

## Mechanism

For each motif's three variables, compute the sample **partial correlation**
of each pair conditioning on the third (`r_12.3`, `r_13.2`, `r_23.1`). Because
all data in this stage are Gaussian, partial correlation is computed in
closed form from linear-regression residuals; this deliberately avoids
introducing a new nonparametric conditional-MI estimator, which would need
its own Stage-0-style validation before use and is out of scope here. (A
conditional-MI estimator remains future work for the outline's nonlinear
stage, where the Gaussian shortcut no longer applies.)

Each partial correlation is converted to a test statistic via the Fisher
z-transform with one conditioning variable:

```
z_ij = atanh(r_ij.k) * sqrt(N - 4)
p_ij = 2 * (1 - Phi(|z_ij|))
```

**Decision rule:** retain edge `(i, j)` if `p_ij <= alpha`; prune it
otherwise. `alpha` plays the role `tau` played in the R2 charter, but the
comparison is against a fixed null distribution per edge, not against the
other two edges' magnitudes. Frozen `alpha` grid:
`[.50, .30, .20, .10, .05, .01, .005, .001, .0001]`.

**Confidence score (exploratory, non-gating):** for every edge decision,
also record `1 - p_ij` as a continuous retention-confidence score. This is
not used to select `alpha` or to determine PROCEED/REASSESS. It is reported
separately (see Exploratory evidence below) purely to assess whether a future
confidence-scored (soft) edge representation would be viable and worth its
own charter.

## Selection and gate

Structurally identical to the R2 charter, substituting `alpha` for `tau`.
Replicates 0-249 (development) select the lexicographically lowest adjacent
`alpha` pair that, pooled across all strengths, families, and `N >= 500`,
meets:

1. Chain and fork indirect-edge (`X1`, `X3`) pruning TPR each at least 0.80.
2. Triangle true-edge retention FPR (each of the three edges, all three
   families) at most 0.10.
3. No estimator, DGP, regression, or Cholesky error is recorded.

Replicates 250-499 (validation) cannot alter selection. The result is
**PROCEED** only if the selected pair meets every validation cell
individually at each `N in [500, 750, 1000]` and strength. Otherwise
**REASSESS**. This stage does not select a public default `alpha` and does
not authorize Stage 2 work.

## Exploratory evidence (non-gating)

Reported alongside the gate decision, explicitly excluded from
PROCEED/REASSESS:

- Calibration of the confidence score against ground truth: does the
  fraction of edges retained at confidence level `c` actually match `c`
  (reliability diagram), and what is the Brier score, per motif and pooled?
- Whether calibration improves, degrades, or is flat with `N`.

This evidence exists to inform whether a follow-up charter for a
confidence-scored (soft) network representation is worth writing — not to
justify one now.

## Required evidence

Each run persists its resolved configuration, this charter's SHA-256, commit
and runtime metadata, and raw per-replicate evidence (partial correlations,
z-statistics, p-values, prune/retain decisions per alpha, and the exploratory
confidence score). Aggregate metrics, gate decision, report, figures, and the
exploratory calibration summary are produced by a separate reporting step,
mirroring the R2 pipeline.

## Consequences

If REASSESS: document the failure plainly; do not build Stage 2 screening,
bootstrap, mixed-type, or confidence-scored-network layers on this evidence.
A conditional-independence mechanism failing for a reason other than the R2
confound (e.g., a new failure mode) would need its own diagnosis and charter,
not a parameter sweep on this one.

If PROCEED: Stage 2 candidate-edge screening may be planned using the
selected `alpha`. Separately, if the exploratory calibration evidence looks
promising, a dedicated charter for a confidence-scored edge representation
may be proposed — this is an executive decision, not an automatic
consequence of R2b passing, since it would affect every downstream stage in
the outline.
