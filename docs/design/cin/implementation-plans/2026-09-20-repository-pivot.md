# MINT/CIN Repository Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `mintnet` around MINT (Model-based Information Network Toolkit) and its forthcoming CIN engine while preserving the retired search-era implementation as a coherent historical snapshot.

**Architecture:** Keep the repository, package name, generic evidence infrastructure, comparator, simulation fixtures, and append-only decision log active. Move the incompatible search/DPI/bootstrap implementation and its tests, configurations, workflows, scripts, and documents under `archive/mi_native_search/`. Promote the controlling CIN methodology and task plan from ignored local outlines into tracked `docs/design/cin/` documentation.

**Tech Stack:** Git, Markdown, Python package layout, pytest metadata.

**Spec:** `docs/design/cin/methodology/methodology_outline_2026-09-19.md` and `docs/design/cin/build-plan/00_README_build_plan_index.md` after Task 2 promotes them.

## Global Constraints

- Preserve the existing uncommitted `.gitignore` edit in the primary checkout; work only on `codex/cin-repository-pivot`.
- Preserve historical content byte-for-byte when moving it; explanatory archive indexes may be added separately.
- Keep `docs/decision_log.md` active and append-only.
- Keep `src/mintnet/comparators/ebicglasso.py`, `src/mintnet/simulation/{gaussian,motifs}.py`, the generic shard workflow/aggregators, and their focused tests active.
- Do not claim the CIN engine is implemented or validated; this change prepares the repository for that work.
- Use the public identity “MINT — Model-based Information Network Toolkit” and describe CIN as the forthcoming “Conditional Predictive-Information Network” engine.
- Commit after each independently reviewable milestone.

## Review Focus

- Archive completeness: no retired `stage*`, screening, DPI, MI-search, confidence-curve, or bootstrap implementation remains active accidentally.
- Retained dependency integrity: active tests and modules do not import paths moved into the archive.
- Historical preservation: every moved tracked file remains tracked at exactly one archive path.
- Documentation integrity: controlling CIN documents are tracked and their internal links resolve after relocation.
- Product honesty: README/package metadata distinguish the planned CIN engine from implemented functionality.

---

### Task 1: Archive the retired MI-native search implementation

**Files:**
- Create: `archive/mi_native_search/README.md`
- Move: `.github/workflows/{stage10a_cost.yml,stage9d_full_repeat_cost.yml}`
- Move: `configs/stage*.yaml`
- Move: legacy `docs/`, `scripts/`, `src/mintnet/`, and `tests/` paths identified by the repository audit
- Modify: `archive/README.md`

**Interfaces:**
- Consumes: the audit manifest of 309 active tracked files.
- Produces: an active set of 17 pre-CIN infrastructure files plus this plan, with 292 retired files preserved under one snapshot.

- [ ] **Step 1:** Record the exact pre-move tracked-file manifest and counts.
- [ ] **Step 2:** Move the retired files with history-preserving Git moves.
- [ ] **Step 3:** Add the snapshot README and update the archive index.
- [ ] **Step 4:** Verify that every pre-move tracked path is either retained or represented once under `archive/mi_native_search/`.
- [ ] **Step 5:** Verify no retained Python source imports a newly archived `mintnet` module. Archive the nominally generic integration tests if dependency inspection shows that they import retired runners.
- [ ] **Step 6:** Commit as `chore: archive retired MI-native search pipeline`.

### Task 2: Promote the controlling CIN design documents

**Files:**
- Create: `docs/design/cin/README.md`
- Create: `docs/design/cin/methodology/*.md`
- Create: `docs/design/cin/build-plan/*.md`
- Modify: relocated Markdown links that referred to the ignored `outline/` layout

**Interfaces:**
- Consumes: the local authoritative files in `outline/network/revised/` and `outline/plan/` from the primary checkout.
- Produces: 16 tracked source-of-truth documents with resolvable internal links.

- [ ] **Step 1:** Copy the three revised methodology documents and thirteen build-plan documents without changing substantive methodology.
- [ ] **Step 2:** Add a concise design index identifying controlling versus historical material.
- [ ] **Step 3:** Update only relocation-sensitive links and references.
- [ ] **Step 4:** Verify all relative Markdown links within `docs/design/cin/` resolve locally or are valid external URLs.
- [ ] **Step 5:** Commit as `docs: track CIN methodology and build plan`.

### Task 3: Establish the MINT/CIN active repository identity

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `docs/decision_log.md`

**Interfaces:**
- Consumes: the approved MINT backronym and CIN method name.
- Produces: an honest top-level identity and a permanent record of the pivot without claiming implementation or validation.

- [ ] **Step 1:** Replace the placeholder README with the MINT/CIN identity, current status, active-tree map, and historical archive pointer.
- [ ] **Step 2:** Update the package description while retaining version `0.1.0` until the CIN implementation establishes a release boundary.
- [ ] **Step 3:** Append decision D-092 documenting the naming and repository-boundary decision.
- [ ] **Step 4:** Verify the active tracked manifest, archive counts, forbidden active paths, Markdown links, and Git status.
- [ ] **Step 5:** Run retained tests if a Python 3.11 interpreter is available; otherwise record the exact environment blocker and do not claim test success.
- [ ] **Step 6:** Commit as `docs: establish MINT and CIN project identity`.
