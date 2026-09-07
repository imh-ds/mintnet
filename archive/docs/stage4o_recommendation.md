# Stage 4o Recommendation: Sequential/Greedy Conditioning Engine — Resolving the R6a Milestone

Status: Synthesis deliverable per `docs/stage4o_charter.md`. Generates
no new evidence — every claim below traces to `docs/decision_log.md`
D-030 through D-043 and `docs/validated_operating_ranges.md`. Where the
record does not answer a question, this document says so rather than
inferring an answer.

Date: 2026-08-31

> **Addendum — 2026-08-31, D-045:** A separate, supplementary public
> benchmark (`docs/stage4p_charter.md`) later ran both engines side by
> side on a shared canonical `N` grid using D-012's general formula
> (not overlap's own specialized one). It surfaced two disclosure-worthy
> findings — a thin, sampling-sensitive margin at overlap/conservative's
> own `N=1500` (diverging from D-018's recorded PROCEED by less than the
> size of D-018's own margin), and a reminder that the sequential
> engine's clean sweep there uses a coarser metric D-032 already showed
> can be inflated by non-detection. **Neither finding changes any
> verdict in this document** — see D-045 and
> `docs/validated_operating_ranges.md` for detail — but any reader
> comparing this document's own Section 2 table against Stage 4p's
> benchmark table should read the two as answering related but distinct
> questions, not as competing claims.

---

## 1. Per-shape verdict (the charter's own rubric, applied literally)

| Shape | Question A — materially lower N? | Question B — cascading error measured? | Verdict |
|---|---|---|---|
| **Overlap** | Yes. Composed, noisy `p=15`: `N=625`/`700` PROCEED, beating the conservative engine's own `N=1500` result (TPR `.986`/`.998` vs. `.817`). D-037. | Yes. Noise-driven: clean null (D-043, Q1). Structural (opposite-triangle, noise-independent): small, `2%`-`6%` of wrongly-pruned edges. D-043, Q4. | **RECOMMEND WITH DISCLOSED CAVEATS** |
| **Chain** | Yes, within its own tested range. Isolated and composed/noisy PROCEED at `N in [750, 1000, 1500]`, `strength in [0.30, 0.50]` — no conservative-engine floor comparison exists for this exact composed DGP, so the claim is the engine's own validated range, not a beat-the-baseline claim. D-040, D-041. | Yes. Small, statistically robust noise-driven effect at `strength=0.15` (deliberately below the validated range): positive in `17`/`18` cells, mean delta `.0017`, max `.0045`. D-042. | **RECOMMEND WITH DISCLOSED CAVEATS** |
| **Fork** | Same as chain — same charters, same grid, separately measured. D-040, D-041. | Same as chain — separately measured, same magnitude. D-042. | **RECOMMEND WITH DISCLOSED CAVEATS** |
| **Hub (2 children)** | Same as chain — same charters, same grid, separately measured. D-040, D-041. | Same as chain — separately measured, same magnitude. D-042. | **RECOMMEND WITH DISCLOSED CAVEATS** |

No shape reaches a bare RECOMMEND (the rubric forbids it — every tested
shape has at least one disclosed, non-zero caveat on record) and no
shape reaches DO NOT RECOMMEND (no measured effect was large enough to
trigger that branch). Any shape, `N`, strength, or `p` not named in the
table above is **INSUFFICIENT EVIDENCE** by the rubric's own default —
see Section 3.

---

## 2. Viability matrix by sample size

**Read this table as "what has actually been measured at this N," not
as a recommendation to operate at every cell marked PROCEED** — several
cells were stress-test conditions, not floor searches, and are labeled
accordingly.

| N | Conservative — general shapes | Conservative — overlap | Greedy — chain/fork/hub | Greedy — overlap, isolated calibration | Greedy — overlap, composed/noisy (realistic) |
|---|---|---|---|---|---|
| **100–300** | Not tested at this range (below D-012's `N=700` floor) | Not tested | **Stress-test only** — baseline wrong-prune rate `17%`-`68%` even noise-free (D-042); not a floor claim in either direction | Not tested | Not tested |
| **400** | Not tested | Not tested | Not tested | **PROCEED** (D-038/D-039, held-out point) | Not tested |
| **550–675** | Not tested | Not tested | Not tested | **PROCEED** at every tested point (D-038/D-039) | Not tested |
| **625** | Not tested | Not tested | Not tested | PROCEED (subsumed above) | **PROCEED** — this project's headline result (D-037: TPR `.986`, beats conservative's own `N=1500`) |
| **700** | Validated as the formula's own lower boundary (D-012, `[700, 3000]`) | Not tested | Not tested | PROCEED (subsumed above) | **PROCEED** (D-037: TPR `.998`) |
| **705–735** | Not tested | Not tested | Not tested | **PROCEED** at every tested point (D-039's dense-region result) | Not tested — composed pipeline was never re-run at these specific `N` |
| **740–750** | Not tested | **REASSESS** (D-018: TPR `.569`) | Not tested | **Unresolved** — formula predicts an invalid (negative) alpha in this exact window (D-037/D-038/D-039); Stage 4e's lookup value (`alpha=.005`) is the only usable fallback | **Unresolved** — the one `N=750` composed attempt errored on the same formula defect (D-037) |
| **750** | **PROCEED**, recommended default floor (D-011) | REASSESS (subsumed above) | **PROCEED**, isolated and composed, `strength in [0.30, 0.50]` (D-040, D-041) | Unresolved (subsumed above) | Unresolved (subsumed above) |
| **1000** | Not directly tested (750/1500 are the conservative engine's own tested points) | Not tested | **PROCEED**, isolated and composed (D-040, D-041) | Not tested | Not tested |
| **1500** | **PROCEED** | **PROCEED** (D-018: TPR `.817`) | **PROCEED**, isolated and composed (D-040, D-041) | Not tested | Not tested |
| **1750** | Not tested at this specific `N` for general shapes | **PROCEED**, `p=30` only (D-027) | Not tested | Not tested | Not tested |

**The single most important cell to read carefully is `740`-`750`.**
This is the one `N` window where the greedy engine has an actual,
disclosed, unresolved gap rather than a caveat-with-a-number — not a
negative finding, but genuinely open. Everywhere else in this table,
"not tested" means exactly that: absent evidence, not a failed test.

---

## 3. Viability matrix by effect size

Overlap's own direct edges (`-0.25`) and indirect cross-branch
correlation (`~.135`) are fixed by its DGP — there is no tunable
"strength" for overlap the way chain/fork/hub have. This table therefore
reports overlap as two fixed rows and chain/fork/hub across their own
tested strength grid.

| Effect size (approx. correlation) | Conservative | Greedy — chain/fork/hub | Greedy — overlap |
|---|---|---|---|
| **`~0.08`** (Stage 1's weakest asymmetric triangle edge) | Baseline wrong-prune rate `~59%`-`84%` at small `N` (D-036 stress-test context); no cascading effect from noise (D-036) | Not tested at this exact strength | Not applicable (fixed DGP) |
| **`0.135`** (overlap's own indirect/cross-branch correlation, fixed) | REASSESS at `N=750`, PROCEED at `N=1500` (D-018) | Not applicable | Governs overlap's own `N` floor directly — see Section 2 |
| **`0.15`** (chain/fork/hub, deliberately below the validated range) | Not tested at this exact strength | **Stress-test only**: small, real, noise-driven cascading effect found here specifically (D-042) — this is below the validated range, not a floor claim | Not applicable |
| **`0.25`** (overlap's own direct edges, fixed) | Not applicable as a tunable value | Not applicable | Governs the `2%`-`6%` structural (noise-independent) cascading rate found in D-043 |
| **`0.30`** | Not tested at this exact strength | **PROCEED**, isolated and composed, at `N in [750, 1000, 1500]` — the *lower* bound of the validated strength range (D-040, D-041) | Not applicable |
| **`0.40`–`0.50`** | Not tested at this exact strength | **PROCEED**, isolated (`0.30`-`0.70` full grid) and composed (`0.30`, `0.50`) (D-040, D-041) | Not applicable |
| **`0.70`** | Not tested at this exact strength | **PROCEED**, isolated only — composed/noisy was not tested at this strength, only at `0.30`/`0.50` (D-040; D-041 tested only two of the four isolated strengths) | Not applicable |

**The gap to note here**: chain/fork/hub's composed/noisy validation
(D-041) covers only `strength in {0.30, 0.50}`, a subset of the four
strengths validated in isolation (D-040). `0.40` and `0.70` are
isolated-only for these three shapes — the same isolated-vs-composed
distinction that matters for overlap in Section 2 applies here too, on
a different axis.

---

## 4. Caveats that must accompany any recommendation (not boilerplate)

**Overlap:**
- Noise-driven cascading error: measured, clean null (D-043).
- Structural cascading error (opposite-triangle pathway, present with
  or without noise): `2%`-`6%` of wrongly-pruned direct edges, at every
  tested `N`/`alpha` (D-043, Q4).
- The composed, realistic pipeline is validated at exactly `N=625` and
  `N=700` — **not** the full `[400, 735]` range, which is an isolated-
  calibration result only (Section 2).
- `N=740`-`750` has no working formula; only a lookup fallback exists.

**Chain / fork / hub (each separately measured, same magnitude for all
three):**
- Noise-driven cascading error: small but real, `17`/`18` stress-test
  cells positive, never negative (sign-test `p<.001`), mean delta
  `.0017`, max `.0045` (D-042).
- This effect was measured at `strength=0.15`, **below** the validated
  `[0.30, 0.70]` range — the magnitude at validated strengths is not
  directly measured, only inferred to be no worse (Stage 4m's own
  design chose the weakest, most-exposed condition on purpose).
- Composed/noisy validation covers only `strength in {0.30, 0.50}`, not
  the full isolated range.

---

## 5. Boundary of recommendation — explicitly covered vs. explicitly not

**Covered by a verdict in Section 1:**
- Overlap: composed/noisy at `N in {625, 700}`; isolated calibration
  at `N in [400, 735]`; cascading error at `N in [100, 200, 300]`
  (stress-test only, not a floor).
- Chain, fork, hub(2-children): isolated and composed at `N in [750,
  1000, 1500]`, `strength in [0.30, 0.50]` (composed) / `[0.30, 0.70]`
  (isolated); cascading error at `strength=0.15`, `N in [100, 200,
  300]` (stress-test only).

**Explicitly not covered — do not extend any verdict above to these
without new evidence:**
- Any shape other than these four (disjoint triads, larger hubs, any
  DGP not in this list).
- Hub with more than 2 children (Stage 4b/4d's own hub result used a
  different child count and was never re-tested under this engine's
  later, corrected metric or `alpha(N)` treatment).
- Any `p` other than `15` for the composed/noisy tests.
- Overlap at `N in {400, 550, 675, 705, 715, 725, 735}` in a **composed,
  noisy** setting — only isolated calibration exists there.
- Overlap at `N in {740, ..., 750}` under any formula.
- Chain/fork/hub below `N=750`, at any strength.
- Chain/fork/hub composed at `strength in {0.40, 0.70}`.
- Any strength/effect-size below `0.30` (chain/fork/hub) as a
  *validated floor claim* — `0.15` was tested only as a deliberately
  harsh stress condition, not a floor search.
- Any contamination pathway other than independent pure-noise columns
  (e.g., noise correlated with a real node) and any noise-column count
  other than `5`.
- Bootstrap edge-stability filtering (Stage 3's own rescue mechanism)
  has never been tested with this engine at all — it exists only for
  the conservative engine's own composed pipeline.

---

## 6. Top-line answer to the R6a milestone

**The R6a milestone is cleared, per-shape, for all four shapes tested
— with disclosed caveats in every case, not a blanket clean pass.**
Both halves of the milestone's own question (materially lower `N`;
cascading-error rate characterized and not worse than the conservative
engine's own failure mode) have direct, cited evidence for overlap,
chain, fork, and hub(2-children), within the specific `N`/strength
ranges in Sections 2-3. The milestone is **not** cleared for any shape,
`N`, or strength outside those ranges — that is INSUFFICIENT EVIDENCE
by the rubric's own default, not a judgment that those conditions would
fail.

**On the engine as a whole**: the sequential/greedy engine is now a
defensible choice for the four tested shapes, inside their tested
ranges, provided the caveats in Section 4 are disclosed alongside any
`N`-savings claim. It should **not** yet be described as a general
replacement or general alternative to the conservative engine — that
would require the boundary-of-recommendation gaps in Section 5 to be
closed, particularly the composed/noisy testing gaps (overlap's
isolated-vs-composed range mismatch; chain/fork/hub's partial strength
coverage) and the bootstrap-stability gap, which has not been touched
at all for this engine.

---

## 7. Recommended next steps (gaps surfaced by this synthesis, not new work done here)

In rough priority order:

1. **Close overlap's isolated-vs-composed gap**: re-run Stage 4h's
   composed/noisy test at the `N` values only isolated-validated so
   far (`400, 550, 675, 705, 715, 725, 735`), so the headline claim
   covers the range it currently implies rather than two points.
2. **Extend chain/fork/hub's composed testing to `strength in {0.40,
   0.70}`**, closing the isolated-vs-composed strength gap in Section 3.
3. **Bootstrap edge-stability for the sequential engine**: Stage 3's
   rescue mechanism has never been tested with this engine at all; it
   may or may not transfer, and this is a real, currently-unaddressed
   gap in this project's own layered validation approach.
4. **A future charter to close overlap's `N=740`-`750` gap**, if a
   downstream use ever specifically needs that narrow range (D-039
   already found this is not worth pursuing otherwise).
5. Lower priority: floor-search chain/fork/hub below `N=750`, and test
   overlap's own cascading error inside its validated `[400, 735]`
   range rather than only at the deliberately harsh `[100, 300]` stress
   window.
