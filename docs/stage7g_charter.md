# Stage 7g Charter: Resolving Whether Stage 7f's `N=500->600` Confidence Dip Is Noise or a Real Non-Monotonic Relationship (mi-native)

Status: **FROZEN before results**
Date: 2026-09-10

## Background and objective

D-083 (Stage 7f) found the exposed confidence score (`growing_subset_
dpi_structured_density`'s own `decisive_p_value`/`confidence` fields)
clearly informative -- correct decisions score roughly double the
confidence of incorrect ones, at every tested `N` -- but its own
predeclared monotonicity check technically REASSESSed: the frontier-
relevant weak edge's own mean confidence rose `46%` overall from
`N=400` to `1500`, but dipped `1.33%` at one specific step (`N=500 ->
600`) against an otherwise unambiguous climb.

**Two real possibilities, both worth distinguishing, neither assumed**:
(1) the dip is ordinary sampling noise on a `400`-replicate cell, and a
properly-powered or properly-specified statistical test would confirm
the overall trend is real and this step is not a meaningful exception;
or (2) something genuinely non-monotonic is happening in this narrow
`N` range that a strict pointwise check correctly flagged and a looser
test would wrongly paper over. **D-083's own predeclared gate was a
strict, pointwise "every consecutive step must not decrease" rule --
arguably the wrong statistical tool for this question**, since any
noisy sequence of only `7` points can fail a pointwise check by chance
even under a genuinely strong underlying trend. This charter does not
retroactively reinterpret D-083's own result (which stands, exactly as
reported: REASSESS per that predeclared rule) -- it asks the sharper,
different question a properly-chosen test can answer, as its own new,
separately-gated charter.

## Mechanism

**Step 1 (required, zero new compute) -- reuse Stage 7f's own already-
collected raw evidence entirely.** From `results/generated/
stage7f_frontier/raw_metrics.csv` (or an equivalent local re-run of
`run_stage7f` against `configs/stage7f_frontier.yaml`, which reproduces
the same evidence bit-for-bit from the same `master_seed`), extract
every replicate's own `confidence` value (via `edge_margin` at the same
canonical `alpha=0.10` D-083 used) for the frontier condition
(`triangle_0`, the smallest tested `target_rho`, pair `(1, 2)`) at
every tested `N`. Apply two checks, neither of which D-083 ran:

1. **Pairwise significance, `N=500` vs `N=600` specifically**: a
   two-sample Mann-Whitney U test (distribution-free -- `confidence`
   is not assumed normal) comparing the two cells' own `400`-replicate
   confidence distributions directly. A non-significant result
   (`p > 0.05`) supports "the dip is consistent with sampling noise";
   a significant result would mean the dip is a real, if small, effect
   worth investigating further, not noise.
2. **Overall trend across the full `N` range**: a Spearman rank
   correlation (or Mann-Kendall trend test, whichever this project's
   own available tooling supports most directly) between `N` and
   `confidence`, pooling all `7` tested `N` values' own replicate-level
   data. A significant positive trend, even with one local dip, would
   confirm the `46%` overall climb D-083 already reported is a real,
   statistically supported relationship, not an artifact of eyeballing
   the seven cell means.

**Step 2 (contingent, small new compute -- only if Step 1's own
pairwise test is ambiguous, e.g. underpowered given `400` replicates
per cell rather than genuinely null)**: collect additional replicates
at `N in {500, 600}` for the `triangle_0` condition only (not the full
`11`-condition x `7`-`N` grid Stage 7f swept), using `master_seed=
92000` (Stage 7f's own, unchanged) with a disjoint replicate range
(`400`-`799`, continuing past Stage 7f's own `0`-`399`) to sharpen the
estimate without re-drawing already-used replicates. Not run unless
Step 1 leaves genuine ambiguity -- disclosed as contingent, not
assumed necessary.

## Data-generating processes

Identical to Stage 7f's own `triangle_0` condition (`sample_weak_edge_
triangle` at the smallest tested `target_rho`) -- no new DGP code,
Step 1 requires none, Step 2 (if triggered) reuses `stage7f_frontier.
py` unmodified with a restricted `--conditions triangle_0 --sample-
sizes 500,600` and a new `--replicate-range` argument (mirroring Stage
9a's own precedent) added only if Step 2 actually triggers.

## Compute-cost disclosure

**Step 1**: effectively free -- a statistical test over already-stored
`confidence` values, no new significance tests, no new DGP draws,
runs in well under a minute locally.

**Step 2 (contingent)**: if triggered, `400` additional replicates x
`2` `N` values x `~10s`-`13s` per replicate (Stage 7f's own measured
cost) = roughly `1.5`-`2` hours total, comfortably runnable as a single
local batch or a 2-shard GitHub Actions dispatch -- far cheaper than
Stage 7f's own `77`-shard run, since this only touches two cells.

## Selection and gate

**PROCEED** (the `N=500->600` dip is attributed to sampling noise, and
Stage 7f's own confidence-score monotonicity claim is considered
supported by a properly-specified test even though it missed D-083's
own stricter pointwise rule) if BOTH: (1) the pairwise Mann-Whitney
test finds no significant difference between `N=500` and `N=600`
(`p > 0.05`), AND (2) the overall trend test finds a significant
positive relationship between `N` and confidence across the full range
(`p < 0.05`). If Step 1 satisfies both without ambiguity, Step 2 is not
run.

**REASSESS** if either check fails to support the "noise" explanation
-- e.g. a significant pairwise difference (a real, if small, dip) or no
significant overall trend (would also contradict D-083's own
"unambiguous `46%` climb" characterization, itself worth flagging). If
Step 1 is genuinely ambiguous (e.g. pairwise test underpowered, wide
confidence interval spanning both a null and a small real effect),
run Step 2 before reaching a final verdict.

## Explicit non-goals

- **Does not reopen D-083's own recorded REASSESS.** That entry stands
  exactly as reported, per its own predeclared (if arguably too
  strict) pointwise rule -- this charter asks a different, better-
  specified question, not a re-litigation of the first one.
- **No claim about any `N` outside `{500, 600}`** even on a full
  PROCEED -- this charter is scoped narrowly to the one disputed step,
  not a general re-validation of the whole frontier table (D-083's own
  Part A table is unaffected either way, and was never gated on this
  question).
- **No change to `growing_subset_dpi_structured_density`'s own fields
  or behavior.** Purely a statistical re-analysis (Step 1) plus,
  possibly, additional evidence collection under the existing,
  unmodified mechanism (Step 2).
- **No claim that confidence is a calibrated literal probability**,
  unchanged from Stage 7f's own explicit non-goal -- this charter only
  asks whether the *ordinal* trend with `N` is real, not whether the
  score's own numeric value has a literal probabilistic meaning.

## Required evidence

This charter's SHA-256, commit and runtime metadata, Step 1's own
pairwise and trend-test results (test statistic, p-value, and the
underlying confidence distributions compared), Step 2's own raw
evidence and updated test results if triggered, the gate decision, and
a report.

## Consequences

**If PROCEED**: the confidence score's own monotonicity-with-`N`
property is considered supported by a properly-specified test, and
`docs/validated_operating_ranges.md`'s own "not yet confirmed to
increase monotonically" caveat (D-083) can be relaxed to "supported by
a trend test; D-083's own stricter pointwise check remains on record as
a disclosed, non-contradicting technicality." The confidence score
still requires its own separate recalibration charter (mirroring Stage
8b/8c's own arc) before being presented as more than an ordinal signal.

**If REASSESS**: the `N=500->600` region genuinely behaves differently
than the surrounding `N` values in a way ordinary sampling noise does
not explain -- worth its own follow-up diagnostic (what is different
about this specific range) before recommending the confidence score
for any `N`-dependent researcher guidance, though it would not affect
the confidence score's own already-confirmed informativeness (D-083's
check 1) or Part A's own frontier table.
