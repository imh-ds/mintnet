# Mintnet Handoff — Stage 4 (Sequential/Greedy Conditioning Engine) — 2026-08-31

## Purpose and governing outline

The project develops a computationally tractable, information-theoretic
network method for behavioral tabular data. Its governing document is
`outline/information_network_technical_build_plan_v3_2026-08-30.md`,
which requires mechanism-by-mechanism falsification: no statistical
layer is built until the preceding one has a frozen charter, generated
evidence, and a written decision-gate outcome (`docs/decision_log.md`).

**Stage 4 built and validated a second, independent engine** — a
sequential/greedy conditioning procedure (rank associations, confirm
strong edges first, test remaining candidates by conditioning on
already-confirmed neighbors) — alongside the original, still-valid
conservative engine (composed screen-then-prune, validated in Stages
1-3). The motivation: the conservative engine needs `N=1500`-`1750` for
one realistic weak-signal shape (shared-node overlap), which is
prohibitive for many real behavioral studies even though its *general*
floor (`N=750`) is realistic for most of them. Stage 4 is now concluded
— every named precondition (`outline`'s own R6a milestone) has been
addressed, per-shape, with disclosed caveats. **This document is the
single index for finding anything from that arc.**

## Prior stages (validated, unchanged by Stage 4)

Stages 0-3 (MI estimation, DPI motif validation, candidate-edge
screening, bootstrap stability) are validated for the **conservative**
engine and documented in `docs/validated_operating_ranges.md`. Stage 4
does not alter any of that — it adds a second engine with its own,
separately validated operating range.

## Stage 4 charter arc, in order

Each row: charter (frozen before results) → decision log entry → one-
line finding. Read `docs/decision_log.md` for full detail; charters
themselves are never edited after evidence exists.

| Charter | Decision | Finding |
|---|---|---|
| `stage4a_charter.md` | D-030 | Sequential engine reproduces Stage 1b's own limitation on the classic triangle — not a new problem. |
| `stage4b_charter.md` | D-031 | Sequential engine dramatically closes the overlap shape's `N=750` gap in isolation. |
| `stage4d_charter.md` | D-032 | Overlap's apparent "no floor below 750" was a metric artifact (non-detection conflated with correctness); hub's own result was genuine. |
| `stage4e_charter.md` | D-033 | The corrected candidacy/conditional-accuracy metric reveals a second, initially unexplained pattern. |
| `stage4f_charter.md` | D-034 | Explained: a fixed alpha is miscalibrated across `N` (Fisher-z scaling), not a mystery. |
| `stage4g_charter.md` | D-035 | A recalibrated, `N`-dependent `alpha(N)` formula PROCEEDs at every tested `N` — the conditioning mechanism itself is sound. |
| `stage4c_charter.md` | D-036 | Cascading-error stress test on Stage 1's asymmetric triangle: no measurable noise-driven effect. |
| `stage4h_charter.md` | D-037 | **Headline result**: composed, noisy `p=15` pipeline PROCEEDs at `N=625`/`700`, beating the conservative engine's own `N=1500` result — and finds a real bug (negative alpha) at exactly `N=750`. |
| `stage4i_charter.md` | D-038 | Repair attempt (drop `N=750` from the fit) relocates the boundary gap rather than closing it. |
| `stage4j_charter.md` | D-039 | Densely-spaced refit narrows the gap `~4x` (validated range becomes `[400, 735]`) but does not fully close it. |
| `stage4k_charter.md` | D-040 | Broader sweep: the *existing*, unmodified general `alpha(N)` formula PROCEEDs across chain/fork/hub(2-children) at every shape/strength cell tested — overlap's miscalibration does not generalize. |
| `stage4l_charter.md` | D-041 | Same generalization holds composed and noisy, with no new fitting needed. |
| `stage4m_charter.md` | D-042 | Cascading-error stress test on chain/fork/hub (deliberately weak, uniform strength): a small but statistically robust effect *is* found — Stage 4c's clean null does not generalize past its own asymmetric design. |
| `stage4n_charter.md` | D-043 | Same stress test on overlap: clean null on noise (like the triangle), but a new, noise-independent structural pathway (opposite-triangle nodes, `2%`-`6%`) is found instead. |
| `stage4o_charter.md` / `stage4o_recommendation.md` | D-044 | **R6a milestone synthesis**: RECOMMEND WITH DISCLOSED CAVEATS for all four shapes, each within its own tested range. See below. |
| `stage4p_charter.md` | D-045 | Public canonical-`N`-grid benchmark surfaces two disclosure-worthy findings (see below) without changing any prior verdict. |
| `stage4q_charter.md` | D-046 | Repairs both D-045 findings: `N=1750` is a genuinely confident conservative-engine floor for overlap; the sequential engine's benchmark sweep is confirmed mostly genuine (small, quantified non-detection gap). |

## The two documents to cite first

- **`docs/stage4o_recommendation.md`** — the authoritative per-shape
  recommendation. Contains the rubric-driven verdict table, the
  `N`-by-method and effect-size-by-method viability matrices, every
  disclosed caveat with its measured magnitude, and an explicit
  boundary section (what is and is not covered). **This is the first
  place to look when writing up "is the greedy engine usable, and
  for what."**
- **`docs/validated_operating_ranges.md`** — the project-wide quick
  reference (both engines, all stages), kept current after every
  charter. Has its own overlap/chain/fork/hub sections for Stage 4
  specifically, plus the corrected `N=1750` conservative-engine note
  (D-046) and the two benchmark caveats (D-045).

## Headline results (for the paper's abstract/results section)

- **The sequential engine's key advantage**: on the shared-node-overlap
  shape, `N=625`-`700` matches or beats the conservative engine's own
  `N=1500`-`1750` requirement (D-037; conservative floor corrected to
  `N=1750` by D-046, superseding the thinner `N=1500` result).
- **This required its own dedicated `alpha(N)` calibration** for
  overlap specifically (`[400, 735]` validated, D-035/D-039) — the
  *general*, pre-existing formula did not transfer to this one shape,
  though it transferred cleanly to every other shape tested (D-040/
  D-041).
- **Cascading error, the engine's structurally distinguishing risk, is
  now measured, not assumed**, across three structurally different
  DGPs: negligible on an asymmetric triangle (D-036), small-but-real on
  uniformly-weak chain/fork/hub (D-042), and a small structural
  (noise-independent) pathway specific to overlap's own shared-node
  topology (D-043). No shape gets a bare "safe" verdict — every
  recommendation carries a specific, quantified caveat.
- **Full test suite**: 386 tests passing as of the last commit on this
  branch (`8969f2a`).

## Important repository state

Active worktree: `.worktrees/codex-stage1-dpi-motifs/`
Branch: `codex/stage1-dpi-motifs`
HEAD: `8969f2a docs: record D-046 -- N=1750 gives a confident overlap floor; metric gap confirmed small`
This branch is **159 commits ahead of `main`** (spans Stage 0 through
Stage 4 in full).

**Merging is not a clean fast-forward.** `docs/handoff_stage1.md`
already documented this: two commits were made directly on `main`
while this branch was under early development
(`a7c69b4 feat: add deterministic Stage 1 runner`,
`655f692 fix: resolve Stage 1 provenance from config root`), and
equivalent-but-not-identical versions were cherry-picked onto this
branch instead (`690037c`, `9476a7a`). A dry-run merge check
(`git merge-tree --write-tree main HEAD`) confirms this still produces
an **add/add conflict in `src/mintnet/experiments/stage1.py`** — the
only conflict found. This branch's own version is the one carrying 154
subsequent commits of validated work on top of it; `main`'s version
predates all of it.

## Exact next actions

1. **Resolve the merge**: take this branch's version of
   `src/mintnet/experiments/stage1.py` (and any other conflicting path
   the actual merge surfaces beyond the dry-run check), complete the
   merge, run the full test suite (`python -m pytest -q`, expect `386
   passed`), and push to `main`.
2. **Then**, scope the next milestone. The outline's own remaining
   items are **R6** ("does the method occupy a meaningful niche
   compared with incumbents" — broad benchmarking against other
   methods, entirely unstarted) and **R7** ("is higher-order
   information worth the complexity" — synergy/PID work, entirely
   unstarted). Neither has a charter yet. This is a separate scoping
   conversation, not a quick follow-up charter.
