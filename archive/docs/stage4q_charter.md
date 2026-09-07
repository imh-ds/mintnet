# Stage 4q Charter: Canonical Benchmark Repair — Higher-N Conservative Floor and Decomposed Sequential Metric for Overlap (R6q)

Status: **FROZEN before results**
Date: 2026-08-31

## Background and objective

D-045 (Stage 4p) disclosed two problems with the canonical benchmark's
own overlap-network results, neither of which changes any prior
verdict but both of which leave the benchmark itself less trustworthy
than it looks at face value:

1. The conservative engine REASSESSed at every tested `N`, including
   `N=1500`, where D-018 originally recorded a thin (`.017`-margin)
   PROCEED. The benchmark's own independent draw landed just under the
   `.80` line. Neither result is wrong, but neither is a confident read
   — `N=1500` is evidently close to this DGP's actual crossover point,
   not comfortably past it.
2. The sequential engine's clean PROCEED sweep on the same network uses
   the coarse, pooled indirect-edge TPR metric — the exact metric D-032
   already showed can be inflated by non-detection (a pair that never
   becomes a candidate defaults to "pruned," indistinguishable from a
   pair that was correctly reasoned about). A direct check found `58%`
   of `N=400` validation replicates already scoring a perfect `1.0`
   under this metric — the benchmark cannot currently say how much of
   that is genuine.

**Objective:** two independent, additive repairs to the canonical
benchmark, addressing each problem directly rather than re-litigating
the whole benchmark:

- **Part A** — extend the conservative engine's `N` grid on the
  overlap-based network upward, past `N=1500`, to locate a threshold
  with real margin rather than a coin-flip-adjacent one.
- **Part B** — re-score the sequential engine's overlap-network results,
  at the same `N` and the same underlying data Stage 4p already drew,
  using the proper candidacy/conditional-accuracy decomposition (Stage
  4e's own corrected metric) instead of composite TPR.

Neither part touches the hub-based network or the chain/fork/hub
metrics, which have no non-detection risk and no thin-margin finding.

## Part A: higher-N conservative floor for overlap

**`N = [1750, 2000]`** — new points, extending past Stage 4p's own
`N=1500`. `N=1750` mirrors D-027's own `p=30` overlap floor point
(found there between `1600` and `1750`) for rough cross-`p`
comparability; `N=2000` is included specifically to test whether
`1750` alone provides a comfortable margin or whether the true
comfortable floor sits even higher.

**Everything else reused unmodified from `docs/stage4p_charter.md`**:
the overlap-based `p=15` network (`mintnet.experiments.
stage2d._sample_network`), the conservative engine
(`mintnet.pipeline.compose_screen_then_prune`), screening `alpha=.001`,
DPI `alpha=f(N)` from D-012's same frozen general formula, the same
five-part gate, `2,000` replicates per `N` (development `0`-`999`,
validation `1000`-`1999`). A new stream tag, since these `N` were never
simulated before at `p=15` for the conservative engine.

**Required margin, not just PROCEED.** Because the entire motivation is
"find a threshold with real confidence," this part additionally reports
the margin above `.80` at each `N` explicitly, and states plainly
whether `1750` or `2000` clears with a margin comparable to D-011's own
`N=750` general-floor margin (`.032`, roughly `3`-`4` SE at `1000`
replicates) rather than D-018's thin `N=1500` margin (`.017`).

## Part B: decomposed metric for the sequential engine on overlap

**Identical `N` grid to Stage 4p's own** (`[400, 500, 600, 750, 1000,
1500]`), **identical seed derivation** (`_condition_seed(master_seed,
dgp_index=0, sample_index, replicate)`, matching Stage 4p's own overlap
DGP index exactly) — this reproduces Stage 4p's own sequential-engine-
on-overlap draws bit-for-bit, so this is a **re-scoring of the same
underlying data**, not a new independent sample. **Identical alpha**:
D-012's same general formula, unchanged — this part corrects the
*metric*, not the alpha-selection rule (changing both at once would
conflate two separate questions).

**New extraction, mirroring Stage 4h's own precedent exactly**: for
each of the `4` overlap cross-branch (indirect) pairs
(`mintnet.experiments.stage2d.OVERLAP_INDIRECT`), record whether it was
a candidate, whether it was tested against any shared confirmed
neighbor, and the final confirmed/pruned outcome — the per-pair detail
Stage 4p's own generic `_score` call never captured. Compute the pooled
`candidacy_rate` and `conditional_accuracy` (Stage 4e's own definitions,
reused unmodified) at each `N`.

**Report both metrics side by side** — Stage 4p's own composite TPR and
this part's decomposed `candidacy_rate`/`conditional_accuracy` — so the
gap between them is visible directly, not just asserted. This is
explicitly descriptive at `N in {1000, 1500}` (outside overlap's own
specialized formula's validated `[400, 735]` range) and a genuine
re-validation at `N in {400, 500, 600, 750}` (inside that range, using
D-012's *general* formula rather than the specialized one — this
remains a distinct question from Stage 4g/4i/4j's own finding, not a
replacement for it).

## Required evidence

For each part: resolved configuration, this charter's SHA-256, commit
and runtime metadata, raw per-replicate evidence, and a report. Part A's
report states the margin at each new `N` explicitly and names which `N`
(if any) clears with D-011-comparable confidence. Part B's report
presents the composite-TPR-vs-decomposed-metric comparison table
directly, at every `N`, with no `N` omitted regardless of outcome.

## Consequences

Neither part authorizes a change to `docs/stage4o_recommendation.md`'s
own per-shape verdicts on its own — Part A produces a candidate higher-
confidence floor for the conservative engine on overlap (a new,
disclosable fact, not previously established at `p=15`); Part B
produces the honest picture of how much of Stage 4p's sequential/
overlap sweep was genuine versus non-detection, which may narrow or
confirm that sweep's own apparent strength. Both results should be
folded into `docs/validated_operating_ranges.md` and cross-referenced
from `docs/stage4o_recommendation.md`'s own D-045 addendum once
generated, mirroring how D-045 itself was handled.
