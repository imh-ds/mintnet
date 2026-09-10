# Stage 7h Charter: First Composed-Tier Validation of the Structured-Density Growing-Subset Engine — Does the Isolation-Tier Accessibility Finding Transfer? (mi-native)

Status: **FROZEN before results**
Date: 2026-09-10

## Background and objective

Stage 7e/7f/7g validated `growing_subset_dpi_structured_density`
(`degree=1`) entirely on isolated 3-node motifs (chain, fork,
`weak_edge_triangle`) — clean scaffolding where every candidate edge
has exactly one possible conditioning subset. D-083's own headline
finding (`N` as low as `400` already resolves any weak-edge effect
`>=0.12`; only the single most extreme tested value needs `N>=750`-
`1000`) and D-084's own confirmed, statistically-supported confidence-
score trend were BOTH measured only in that clean, pool-size-1 setting.

**This engine has never been run on a real, composed, noisy multi-
variable network.** Every prior composed-tier finding this project's
`mi-native` track has produced (D-053's own dimension-scoping
diagnostic; the whole D-069-D-081 composed-tier-miscalibration-and-
rescue arc) used the OLDER Fisher-z/partial-correlation `growing_
subset_dpi`, not the genuinely MI-based structured-density estimator
Stage 7 built specifically to move past that engine's own structural
blindness to nonlinear dependence (D-062). Whether the isolation-tier
accessibility win survives a composed network's own added complexity
-- more candidate edges, a real screening step, deeper conditioning
searches, cross-edge noise -- is a completely open, untested question,
not an assumption this charter is entitled to make either way.

**Two connected questions**: (1) does Stage 7f's own accessibility
table (moderate effect sizes resolvable at low `N`) hold up on
`chain_fork_hub`/`overlap` (`p=15`, the two composed DGPs this
project's `mi-native` and Gaussian tracks alike have used throughout),
or does composed-tier noise push the effective floor back toward the
old `N>=1500` picture; (2) does the confidence score's own validated
properties (informative, trending correctly with `N` -- D-083/D-084)
transfer to composed-tier decisions, including specifically the
`conditioning_size_used >= 2` regime D-076 already found unreliable
for the OLDER engine -- a directly relevant prior finding this charter
must check against, not assume resolved by a different mechanism.

## Mechanism

Compose `growing_subset_dpi_structured_density` (`degree=1`,
unmodified) with MINT's own existing screening step, mirroring Stage
6a's/Stage 9b's own composition pattern exactly (`compute_pairwise_
screening_evidence` -> `screen_uncorrected` -> `growing_subset_dpi_
structured_density` on the screened candidate graph).

**Sweep**: `chain_fork_hub` and `overlap` (`stage5a._DGP_REGISTRY`,
this project's own standing composed fixtures), `N in {400, 500, 600,
700, 750, 1000, 1500}` (Stage 7f's own grid, unchanged, for direct
comparability), `strength in {0.3, 0.5, 0.7}` (this project's own
historical strength grid, giving the effect-size-conditional read
Stage 7f's own `target_rho` sweep gave at isolation tier).

**Alpha selection**: the SAME already-validated fitted-alpha procedure
Stage 9b used (`mintnet.experiments.stage1j_fit.fit_candidate_forms`/
`select_form`), not a manual grid. This is a deliberate departure from
Stage 7f's own free "compute once, threshold many alphas" design: at
composed scale, `decisive_p_value` is NOT alpha-independent (a
multi-variable candidate edge can have more than one possible
conditioning subset, so a different `alpha` can change which subset
the search visits and where it stops) -- re-thresholding stored
p-values across many alpha values would silently misrepresent what an
actual different-alpha run would have done. Using one fitted alpha per
`N`, exactly as every other composed-tier charter in this project
already does, avoids that trap and keeps cost proportional to the
sweep grid alone, not multiplied by an alpha grid on top of it.

**Per replicate, record**: every candidate edge's own `decisive_p_
value`, `confidence`, `conditioning_size_used`, and ground truth
(`is_true_edge`) -- directly extending D-076's own stratified-accuracy
design (by `is_true_edge` and `conditioning_size_used`) across this
new `N`/`strength` grid, rather than D-076's own single-`N` snapshot of
already-existing (Fisher-z-engine) evidence.

## Data-generating processes

`chain_fork_hub`, `overlap` (`stage5a._DGP_REGISTRY`), `p=15`,
`strength in {0.3, 0.5, 0.7}`, `N in {400, 500, 600, 700, 750, 1000,
1500}` -- identical DGP registry and `p` every mi-native composed-tier
charter (Stage 6a onward) has used, extended to a strength sweep and a
downward-extended `N` grid neither Stage 6a nor D-069-D-081 tested.

## Compute-cost disclosure

**Not assumed to transfer from the isolation tier's own cheap `9s`-
`13s`/replicate cost (Stage 7f) or from the OLDER Fisher-z engine's own
composed-tier cost** -- a `p=15` network's own growing-subset search
visits many more candidate subsets per replicate than a 3-node motif's
single fixed test, and `growing_subset_dpi_structured_density` has
never been run at this scale before. Per this project's own standing
discipline (restated after Stage 9a's own multi-hour-timeout mistake
and Stage 7e's own identical disclosure): **measure real per-replicate
wall-clock cost, under GitHub Actions' own thread limits, on at least
one composed-tier cell at the smallest and largest tested `N`, before
finalizing the replicate count or shard plan.** Provisional planning
figure only, not a commitment: `R=200` per cell (smaller than Stage
7f's own `400`, anticipating a materially higher per-replicate cost) --
resolved after direct measurement, exactly as Stage 7e's own charter
required and Stage 9a's own failure to do so up front caused two
cancelled multi-hour dispatches.

**This charter's evidence MUST be generated via the sharded GitHub
Actions workflow, not local multiprocessing, from the first run.**

## Selection and gate

**Part A (accessibility) PROCEED** if, at every tested `strength`, true
-edge retain accuracy stays `>= 0.95` (mirrors D-076's own near-100%
retain finding for the older engine) at an `N` no higher than what
Stage 7f's own isolation-tier table would suggest for a comparably
weak effect, without requiring `N>=1500` the way the Gaussian engine's
own hardest composed shape did (D-029). **REASSESS** if composed-tier
noise pushes the effective floor materially higher than the isolation-
tier comparison would predict -- judged by comparison to Stage 7f's
own table, not an absolute pass/fail number, since exact isolation-
to-composed comparability is not itself established.

**Part B (confidence transfer) PROCEED** if, using Stage 7g's own
validated statistical methodology (Mann-Whitney for a pairwise check,
Spearman/trend test for an overall relationship -- NOT a brittle
strict pointwise rule, a direct, disclosed lesson from D-083/D-084),
confidence is informative (correct decisions score higher than
incorrect ones) and trends with `N` in the specific `conditioning_
size_used >= 2` regime, at every tested `(dgp, strength)` combination.
**REASSESS** otherwise -- and if so, explicitly check whether the
failure pattern resembles D-076's own already-documented asymmetry
(reliable retain, unreliable prune at depth `>= 2`) or something new.

Both parts are independently gated -- one may PROCEED while the other
REASSESSes, exactly as Stage 7f's own two-part structure allowed.

## Explicit non-goals

- **No re-tuning of `degree`, `k_perm`, or any other estimator
  parameter.** `degree=1` is inherited unchanged from D-063.
- **No bootstrap-rescue mechanism.** Stage 9's own `growing_subset_
  dpi_with_stability_rescue` was built and validated for the OLDER
  Fisher-z engine's own composed-tier asymmetry -- whether an
  analogous fix is needed here, if Part B REASSESSes, is separate,
  not-yet-chartered future work, not assumed solved by a mechanism
  built for a different estimator.
- **No claim beyond `chain_fork_hub`/`overlap` at `p=15`.** Identical
  scope discipline to every prior composed-tier charter.
- **No production deployment authorization**, even on a full PROCEED
  on both parts.
- **No recalibration of the confidence score into a literal
  probability.** Ordinal-only, unchanged from Stage 7f's own explicit
  non-goal -- a dedicated recalibration charter (mirroring Stage
  8b/8c's own arc, but on composed-tier evidence directly rather than
  isolated-motif evidence that is already known not to transfer) is
  separate future work, worth chartering after this one, not before.

## Required evidence

This charter's SHA-256, commit and runtime metadata, the up-front
compute-cost measurement and its resulting replicate-count/shard-plan
decision, raw per-candidate-edge evidence (`decisive_p_value`,
`confidence`, `conditioning_size_used`, `is_true_edge`) for every
swept `(dgp, strength, N)` cell, Part A's own stratified-accuracy
table (mirroring D-076's own format, extended across `N`/`strength`),
Part B's own Mann-Whitney/trend-test results per `(dgp, strength)`,
both gate decisions, and a report.

## Consequences

**If both PROCEED**: `mi-native`'s own accessibility story extends
cleanly from isolated motifs to real composed networks -- a materially
stronger case that this engine is usable for smaller-`N` behavioral
research than the isolation-tier result alone could support, and a
green light to pursue the confidence-score recalibration charter next
(this time on composed-tier evidence, avoiding the known isolated-
motif-to-composed-network transfer trap).

**If Part A REASSESSes but Part B PROCEEDs**: composed-tier noise
genuinely erodes the low-`N` accessibility win even though the
confidence score itself remains a trustworthy signal -- motivates
recommending the confidence score specifically as the tool for a
researcher to assess THEIR OWN composed analysis's reliability at
whatever `N` they have, rather than a blanket lower-`N` recommendation.

**If Part B REASSESSes**: check whether the failure pattern matches
D-076's own already-documented retain/prune asymmetry for the older
engine. If so, Stage 9's own bootstrap-rescue design (proven to work
against exactly that signature) becomes a natural, well-motivated
candidate to adapt to this estimator, rather than a speculative new
mechanism.
