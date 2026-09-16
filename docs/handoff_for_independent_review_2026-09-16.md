# Handoff Document for Independent Review (mi-native track)

Date: 2026-09-16
Audience: an independent AI agent (or human researcher) with **no
prior context** on this project, being asked to review, continue, or
critically re-assess this work.
Repository: `github.com/imh-ds/mintnet`, `main` branch.

**Read `docs/postmortem_2026-09-16_search_scaling_and_dense_network_
failure.md` in full before anything else.** This document assumes you
have. It exists to get you oriented on the project as a whole; the
postmortem is the specific, authoritative technical finding that
determines what you should and should not trust right now.

## 1. What this project is

`mintnet` (package name `mint`) is a Python library for discovering
conditional-independence network structure from data — given a matrix
of variables, decide which pairs are directly related versus related
only indirectly (through a mediating variable). It implements this via
a two-stage pipeline: **screening** (cheap pairwise marginal-
correlation filtering to produce a candidate-pair pool) followed by a
**growing-subset conditional-independence search** (test each
candidate pair against progressively larger conditioning sets, pruning
it if any tested subset shows the pair is conditionally independent
given that subset).

The project has historically supported multiple conditional-
independence *engines* for the second stage: an original Fisher-z /
partial-correlation engine (Gaussian-only), and a newer
**structured-density estimator** ("mi-native") using conditional
mutual information via cross-fitted density estimation and permutation
testing, intended to eventually handle non-Gaussian and nonlinear
relationships the Fisher-z engine cannot.

**Standing project constraint, non-negotiable**: the Fisher-z engine is
explicitly *not* part of the product going forward. It exists in the
codebase as a historical/comparison baseline and must never be
presented as a fallback that makes an mi-native gap "not urgent." All
work described below concerns the mi-native (structured-density)
engine specifically.

## 2. Where the project actually stands right now

**Short version**: the mi-native engine's underlying statistical test
is sound. The search algorithm built around it does not work on any
real, densely-connected network — confirmed directly, not suspected —
and everything built on top of that search (nine stages of charters,
an entire bootstrap-rescue subsystem, every composed-pipeline
calibration) is archived as a real-use claim until the search itself
is replaced.

The authoritative, detailed account of why is
`docs/postmortem_2026-09-16_search_scaling_and_dense_network_failure.md`,
with a precise stage-by-stage disposition table (Section 4 of that
document) and an exact file/function list (Section 7). Do not take
this handoff document's summary as a substitute for reading it — this
section is orientation, not the finding itself.

**What is still trustworthy, unconditionally, as of this handoff:**

- The core conditional-independence test itself
  (`mintnet.mi.structured_density.local_permutation_test`) — correct
  given a specific conditioning set; the defect is entirely in how
  candidate conditioning sets are chosen, never in this test's own
  logic.
- Pairwise screening (`mintnet.screening.pairwise_correlation`) — no
  conditioning-pool concept, unaffected.
- The `organic_network` DGP fixture
  (`mintnet.simulation.motifs.sample_organic_network`) — a reusable,
  correctly-designed single-connected-component stress test, the tool
  that surfaced the defect and exactly what any future work must be
  proven against.
- The project's own falsification discipline (see Section 3 below) —
  the process is what caught this precisely; it is not what failed.

**What is archived (not deleted — preserved as historical record, but
not to be cited as a currently-valid real-use claim or built upon
without re-derivation):** the entire search architecture from Stage 6a
onward, every composed-pipeline PROCEED/REASSESS decision through
Stage 9, and the complete bootstrap-rescue subsystem (Stage 9a-9d, both
the original full-repeat mechanism and its "localized" replacement).
See the postmortem's Section 4 table for the complete, stage-by-stage
reasoning — do not assume any component's disposition without checking
that table, since some of this (e.g. the specific DGP topology in
Stage 10a) is salvageable even though the stage it belongs to also
produced archived results.

## 3. Project discipline — read this before writing anything

This project runs on a specific, consistently-applied methodology.
Deviating from it without understanding why will produce work that
gets rejected or has to be redone.

- **Mechanism-by-mechanism falsification.** Each unit of work is
  scoped to test one specific, falsifiable claim, with the expected
  gate criteria written down *before* running anything.
- **Charters** (`docs/stageXX[letter]_charter.md`) are frozen before
  results are gathered — `Status: FROZEN before results` at the top
  of each file. **A frozen charter is never edited after evidence
  exists against it.** If something in a charter turns out to be
  wrong (as happened twice this session — Stage 10a's original
  topology, and implicitly the entire search architecture underlying
  Stage 9d), the correction is a **new, appended decision-log entry**,
  never a silent edit to the frozen file. The frozen file remains the
  historical record of what was originally planned.
- **`docs/decision_log.md`** is the sequential narrative: one `##
  D-0XX:` entry per finding, in strict chronological order, never
  renumbered or edited after the fact. Each entry states what
  happened, what was found, the decision (PROCEED / REASSESS / a
  correction), and consequences. **This is the single most important
  file for understanding how the project actually got to its current
  state** — read it before assuming anything about why a given piece
  of code exists.
- **`docs/validated_operating_ranges.md`** is a *maintained reference
  table*, not a chronological log — it tracks, per methodological
  component, the sample-size threshold below which that component's
  automatic decision should not be trusted autonomously. It has not
  yet been updated to reflect the D-091 archival (a stated follow-up
  in D-091 itself, not yet done as of this handoff).
- **`outline/`** holds product-scope and API-design documents (not
  charters) — these are allowed disclosed, in-place corrections
  (clearly marked, dated, with the old and new stated), unlike frozen
  charters. `outline/package_scope_v1.md` and `outline/api_design_v1.md`
  both need such a correction reflecting this postmortem's finding;
  this has not yet been done.
- **Evidence generation for anything non-trivial must be dispatched
  via GitHub Actions, never run locally** — this includes a "quick"
  one-off timing comparison, not just full evidence-generation runs.
  This was violated twice this session (once for a rescue-mechanism
  cost comparison, once implicitly) and is now a hard standing rule.
  The reusable, generic dispatch vehicle is
  `.github/workflows/sharded_benchmark.yml`, which shards a
  `(dim1, dim2[, dim3])` grid across matrix jobs, each invoking
  `python -m <runner_module> --config <path> --output <dir> <dim1_flag>
  <value> <dim2_flag> <value> [<dim3_flag> <value>] --no-report`, then
  aggregates via `scripts/aggregate_shards.py`. A runner module must
  conform to the contract documented at the top of that workflow file
  and in `scripts/aggregate_shards.py`. **A single GitHub Actions job
  has a default 6-hour timeout** — this is what actually exposed the
  scaling defect (jobs were cancelled mid-computation, not merely
  slow), and it is why the "no unbounded-cost mechanism" gate in the
  postmortem exists.
- **Every commit and PR ends with the attribution line**
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` (commits)
  and the Claude Code footer (PR descriptions). Git user is `imh-ds`.
  Prefer new commits over amending; never force-push without explicit
  instruction.
- **Never use Cohen's effect-size thresholds** anywhere in this
  project — use the project's own modern-d convention
  (`.05`/`.1`/`.2`/`.3`) if effect-size language is needed at all.
- **Small-N results need researcher judgment, not more validation
  engineering** — this project's stated stance is that at small
  sample sizes, a component's automatic output is informative context
  for a human decision, not a decision-making authority in itself.
  Don't try to over-engineer statistical certainty out of a
  genuinely underpowered regime.

## 4. Repository map (mi-native-relevant subset)

```
src/mintnet/
  mi/structured_density.py          -- the core CI test (local_permutation_test). SOUND.
  screening/pairwise_correlation.py -- pairwise screening. SOUND.
  pipeline/
    growing_subset_dpi_structured_density.py  -- the BROKEN search (see postmortem Section 2/7).
    compose.py                       -- connected_components(); used (mis-used, at scale) by the search above.
    stability_rescue.py              -- rescue entry points, ARCHIVED (built on the broken search).
  bootstrap/stability.py             -- rescue mechanisms (full-repeat + localized), ARCHIVED.
  simulation/motifs.py               -- all synthetic DGP fixtures, including sample_organic_network (SALVAGEABLE).
  experiments/
    stage5a.py                       -- shared _DGP_REGISTRY used across many stages' evidence runners.
    stage9c_bootstrap_rescue.py / _reporting.py   -- ARCHIVED evidence runner + calibration logic.
    stage9d_localized_rescue.py      -- ARCHIVED evidence runner (localized rescue calibration).
    stage10a.py                      -- organic_network DGP wiring (SALVAGEABLE fixture, ARCHIVED any result run through the broken search).
    stage8c_composed_calibration.py  -- ARCHIVED calibration work.
  confidence/margin.py               -- edge_margin(), confidence-score mapping. ARCHIVED (calibrated against archived search output).
  api.py                             -- discover(), the public v1 API. Built on now-archived assumptions; needs revisiting.
docs/
  stageXX_charter.md                 -- frozen charters, one per stage. Historical record; do not edit after evidence exists.
  decision_log.md                    -- THE sequential narrative. Read this to understand why anything exists.
  validated_operating_ranges.md      -- maintained reference table (not chronological); needs a post-D-091 update pass.
  postmortem_2026-09-16_search_scaling_and_dense_network_failure.md  -- READ THIS FIRST.
  handoff_for_independent_review_2026-09-16.md  -- this document.
outline/
  package_scope_v1.md, api_design_v1.md  -- product-scope/design docs, need a disclosed correction (not yet done).
scripts/
  stage10a_cost_shard.py / aggregate_stage10a_cost_shards.py  -- the scripts that produced the timings cited in the postmortem.
  stage9d_full_repeat_cost_shard.py, aggregate_stage9d_full_repeat_shards.py  -- ARCHIVED, related failure mode.
  aggregate_shards.py               -- generic shard-aggregation contract used by sharded_benchmark.yml.
.github/workflows/
  sharded_benchmark.yml             -- the generic, reusable sharded-dispatch workflow. Use this for any new evidence generation.
  stage9d_full_repeat_cost.yml, stage10a_cost.yml  -- one-off cost-measurement workflows (both produced the cancelled runs discussed in the postmortem).
configs/
  stageXX_*.yaml                    -- config files for the various evidence-generation runners.
results/generated/                  -- gitignored. Local evidence archives (raw shard data) live here, not in git. Check before assuming evidence is lost.
```

## 5. What a viable next step actually requires

This is Section 6 of the postmortem, restated here for visibility.
**Not a new charter yet — a precondition for one.** Any replacement
search architecture must, before any further evidence generation:

1. Build its conditioning pool from a pair's own *local* structure
   (its actual screened neighbors — in the manner of PC-algorithm-style
   constraint-based discovery) rather than the whole connected
   component, so cost scales with local degree, not network size.
2. Be re-validated from the ground up against the existing small
   isolated motifs first, to confirm the new pool design does not
   silently change or break any correctness property the old design
   had in the regime where the two designs agree (small components).
3. Clear both binding gates (postmortem Section 3) against
   `organic_network` specifically, with real measured cost and
   correctness numbers, before any claim is made that the scaling
   problem is solved:
   - **Gate 1**: cost must be demonstrably bounded by local structure,
     not global network size. No amount of infrastructure
     (parallelism, sharding, compute budget) substitutes for this.
   - **Gate 2**: correctness and boundedness must be proven on at
     least one single, densely-interconnected connected component —
     `organic_network` already exists for exactly this purpose —
     not merely on disjoint small motifs, regardless of how many
     motifs or replicates are tested.

Until all three are satisfied, do not describe the package as working,
validated, or ready for any real-world use, regardless of what
isolated-motif evidence exists.

## 6. Practical gotchas learned the hard way this session

- **Windows multiprocessing**: any script using
  `ProcessPoolExecutor`/`multiprocessing` must guard its executable
  code under `if __name__ == "__main__":` — omitting this produces a
  `RuntimeError` about re-importing the main module, specific to
  Windows' `spawn` start method (this repo's local dev environment is
  Windows; GitHub Actions runners are Linux and don't hit this, but
  local reproduction scripts will).
- **Local Python environment**: use the repo's own `.venv`
  (`./.venv/Scripts/python.exe` on Windows), not the system Python —
  the system Python does not have `mintnet` installed and will fail
  with `ModuleNotFoundError`.
- **`gh run cancel <run-id>`** is the correct way to stop a GitHub
  Actions dispatch once its answer is already known — don't let a run
  continue "for completeness" once the qualitative finding is already
  decisive; that only burns further compute confirming a known answer.
- **A sharded run's individual shard timing is itself evidence** — use
  `gh run view <run-id> --json jobs -q '...'` to pull exact
  `startedAt`/`completedAt` timestamps per job rather than waiting for
  a full aggregate; this is how the postmortem's cited shard timings
  were obtained while the run was still partially in progress.
- **CRLF/LF git warnings on Windows** (`warning: ... LF will be
  replaced by CRLF ...`) are harmless line-ending normalization
  notices, not errors — don't treat them as a problem to fix.

## 7. What NOT to do without explicit human confirmation

- Do not edit any frozen `docs/stageXX_charter.md` file after evidence
  exists against it — append a decision-log correction instead.
- Do not delete any archived code, config, or documentation — "archive"
  in this project's own vocabulary means "do not trust or build on
  as-is," never "remove from the repository."
- Do not dispatch any new GitHub Actions run without being reasonably
  confident of its expected cost and shape first (see Section 3's
  sharding requirement) — and do not let a run continue once its
  answer is already decisively known.
- Do not push commits to `main` without the standing attribution line,
  and do not force-push or amend published commits.
- Do not present the Fisher-z engine as a fallback or as evidence an
  mi-native gap is "not urgent" — it is not part of the product.

## 8. Suggested first task for a reviewing agent

1. Read the postmortem in full, then this document, then
   `docs/decision_log.md` entries D-085 through D-091 in order (they
   are the direct narrative leading to the current state).
2. Independently verify the core claim: read
   `growing_subset_dpi_structured_density.py`'s pool construction and
   confirm for yourself that it scales with connected-component size
   rather than local degree. Do not take the postmortem's word for it
   without reading the actual code.
3. If proposing a fix, prototype the neighbor-based pool design
   in an additive, separate function (do not modify the existing,
   still-referenced `growing_subset_dpi_structured_density`), and test
   it first against the small isolated motifs already in
   `mintnet.simulation.motifs` before touching `organic_network`.
4. Write a new charter (`docs/stage11a_charter.md` or the next
   available letter/number) before generating any evidence for the
   proposed fix, following the frozen-before-results discipline
   described in Section 3.
