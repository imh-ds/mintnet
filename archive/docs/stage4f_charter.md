# Stage 4f Charter: Diagnosing the Candidacy-Accuracy Anomaly (R6e)

Status: **FROZEN before results**
Date: 2026-08-30

## Background and objective

D-033 (Stage 4e) found that, even after correcting for the non-detection
artifact D-032 identified, the overlap shape's conditional pruning
accuracy (correctness among cross-branch pairs that actually became
screening candidates) still declines modestly as `N` rises — backwards
from every other finding in this project, and left as an explicitly
unexplained anomaly rather than speculatively rationalized.

D-033 offered one unverified hypothesis: a cross-branch pair only
becomes a candidate at low `N` if its *marginal* sample correlation
happens to be an unusually large fluke relative to its small true value
(`~.135`); that fluke has no particular reason to also inflate the
separately-computed *partial* (conditioning-test) correlation, so
low-`N` candidates might get correctly pruned at a normal rate despite
being "noticed" for the wrong reason, while high-`N` candidacy admits a
larger, more complete, and possibly genuinely harder pool.

**This charter is a quick, narrowly-scoped, purely diagnostic check of
that specific hypothesis — not a new validation gate.** There is no
PROCEED/REASSESS decision here, no new mechanism, and no code change to
the sequential engine. It exists only to look directly at the marginal
and partial correlation values behind the anomaly, at two predeclared
sub-questions, and report what they show plainly.

## Predeclared sub-questions

**Q1 — Does marginal detection strength predict conditional outcome
among candidates?** For each candidate cross-branch pair, record its
marginal correlation `r_marginal` and its partial correlation
`r_partial` (conditioning on the shared node). Compute the correlation
between `|r_marginal|` and `|r_partial|` across all candidate pairs, per
`N`. **If the hypothesis holds**, this correlation should be weak and
similar in magnitude at low and high `N` (marginal detection being a
fluke unrelated to the conditional result). **If instead `r_marginal`
and `r_partial` are strongly correlated**, that would point to shared
sample-noise driving both estimates together, a different explanation
than D-033's hypothesis, and should be reported as such, not folded
into it.

**Q2 — Is the low-`N` candidate pool "easier," or does it just clear
noisily?** Compute the mean `|r_partial|` among candidates, per `N` (a
direct measure of how far the conditional test result sits from the
correct answer of zero). **If the hypothesis holds as stated**, this
should be roughly similar at low and high `N` (low-`N` candidates are
not intrinsically easier, they just happened to get noticed, and the
conditional test still works normally on them). **If mean `|r_partial|`
is systematically smaller at low `N`**, the low-`N` candidate pool is
in fact easier, not merely differently selected — a distinct, more
specific finding worth stating precisely, not conflated with the
original hypothesis.

Report both answers plainly; a "yes" or "no" to the hypothesis is not
owed by these two sub-questions individually — they may point in
different directions, and both readings should be stated if so.

## Data-generating process

Identical overlap DGP and seed derivation to Stage 4b/4d/4e (no noise
columns, `master_seed=20260830`, overlap's own shape index), so this
charter examines the identical draws already analyzed. **`N = [300,
500, 750]`** — a minimal three-point check (the two extremes from
D-033's anomaly plus a midpoint), not the full five/six-point grid,
consistent with this charter's quick, targeted scope. **`alpha in
{.10, .20}`** only — the two values D-032/D-033 actually selected,
since this charter diagnoses an already-observed pattern at those
specific settings rather than re-deriving a selection from scratch.
2,000 replicates per `N` (no development/validation split needed —
this is descriptive, not a gate).

## Mechanism

No engine change. For each replicate, independently of
`sequential_screen_and_prune_detailed` (to avoid modifying frozen
engine code for a diagnostic charter): compute marginal screening
evidence (`mintnet.screening.compute_pairwise_screening_evidence`) and,
for each of the 4 cross-branch pairs that clears the marginal
`alpha` threshold, the partial correlation conditioning on node 2 (the
shared node — the neighbor the engine actually tests for these pairs in
this no-noise DGP; if a different or additional neighbor was tested for
some replicate under the live engine, this charter's node-2-only
computation is a documented simplification, not a claim it exactly
reproduces every engine decision) via
`mintnet.dpi.multi_conditional.compute_partial_correlation_evidence`.

## Required evidence

Resolved configuration, this charter's SHA-256, commit and runtime
metadata, raw per-replicate per-cross-branch-pair evidence (`r_marginal`,
`r_partial`, candidate flag, correctly-pruned flag), the Q1 correlation
table and Q2 mean-`|r_partial|` table per `N`/`alpha`, a scatter plot of
`r_marginal` vs. `r_partial` colored by `N`, and a report stating the
answers to both sub-questions plainly, without extrapolating beyond
what they show.

## Consequences

This charter cannot, by itself, resolve D-033's anomaly — it narrows
down *which* of several plausible explanations the data actually
supports, or shows that neither predeclared sub-question points toward
D-033's hypothesis at all, in which case that hypothesis should be
retired rather than carried forward unexamined. Either way, **overlap's
`N` recommendation remains withheld** until this line of investigation
concludes with an explanation that survives scrutiny, per D-033's own
consequences. If both sub-questions come back inconclusive or
contradictory, that itself is a valid, reportable outcome — it would
mean the anomaly needs a differently-designed follow-up (e.g., examining
the joint distribution of all 4 cross-branch pairs' test statistics
together, since they are not independent within a replicate), not
further speculation layered onto this charter's evidence.
