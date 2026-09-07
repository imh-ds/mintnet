# Peer Review Brief #2 — Mintnet Stage 1/Stage 2 Extension, 2026-08-30

## Purpose of this document

This is the second review checkpoint for this project (the first is
`docs/peer_review_brief_2026-08-29.md`, dated one day earlier — read that
one first for the project's governing outline, Stage 0/Stage 1 history
through D-008, and the repository/worktree layout, which are unchanged
and not repeated here). Since that review, the response to its six
requested corrections was applied (`docs/peer_review_followup_2026-08-29.md`,
addressed in commit `5928544`), and ten further decisions (D-009 through
D-018) extended the work substantially: precisely locating the DPI
sample-size floor, fitting and validating a default-alpha formula,
building and validating candidate-edge screening, composing screening
with DPI pruning into one pipeline, and generalizing DPI's conditioning
mechanism to two genuinely different multi-node topologies. This brief
covers only that new work.

## What was done in response to the first review

`docs/peer_review_followup_2026-08-29.md` requested six corrections, all
applied in commit `5928544`, verified by a full diff read before
accepting the fix as complete:

1. Outline documentation of the pivot — done via a new, separately
   versioned file (`outline/information_network_technical_build_plan_v2_2026-08-29.md`
   in the main checkout, not this worktree; the original file was left
   untouched per the user's explicit instruction not to overwrite it).
2. Precise validated-scope statement — added to that same v2 file.
3. Stage 2+ pipeline references revised — same file, inline annotations.
4. R2h "independent points" wording corrected — `docs/decision_log.md`
   D-009 and `docs/stage1h_report.md` both revised to state plainly that
   `N=750`-`2000` reuse identical seeded data from earlier charters.
5. N<=300 "decisive" claim scoped to the tested alpha grid — done in
   `docs/stage1h_report.md`.
6. `1 - p_value` relabeled as an exploratory score, not a calibrated
   probability, across `docs/decision_log.md` and every `stage1*_report.md`
   — charters themselves were deliberately left unedited, since editing a
   frozen charter after results exist would violate the project's own
   rule; the charters' original language was accurate foresight when
   written, not a claim about results.

## What has been done since (D-009 through D-018)

| # | Charter | Question | Outcome |
|---|---|---|---|
| D-009 | `docs/stage1h_charter.md` | Per-N alpha table: does each sample size need its own setting? | Per-N table, not one status. `N<=300`: decisive gap. `N=500`: one-grid-step near-miss. `N>=750`: clean, monotonic trend |
| D-010 | `docs/stage1i_charter.md` | Where exactly does the N=500-750 crossover sit? | Located precisely: `N<=600` no viable pair; `N=650` near-miss; `N=700` thin-margin PROCEED; `N=750` comfortable PROCEED |
| D-011 | (policy, no new charter) | Which floor should be the *recommended* default: 700 or 750? | `N=750` recommended (margin ~3-4x noise vs. `N=700`'s ~1.3x); `N=700` retained as a disclosed, non-default option |
| D-012 | `docs/stage1j_charter.md` | Can a formula replace the per-N lookup table? | `alpha(N) = 0.5222 - 0.0566*ln(N)`, fit on 6 known points, validated by predicting a single value (no search) at 4 held-out interpolated `N` — all passed with real margin |
| D-013 | `docs/stage2_charter.md` | Does per-pair correlation screening separate real from null pairs in a `p=15` network? | PROCEED at `N=750,1500`; uncorrected `alpha=.001` sufficient, no BH correction needed for this DGP |
| D-014 | `docs/stage2b_charter.md` | Does screening composed with DPI pruning work as one pipeline? | PROCEED at both `N`; final false-edge rate exactly tracks screening's own (DPI cannot rescue isolated false positives, confirmed not just assumed) |
| D-015 | `docs/stage1k_charter.md` | Does DPI conditioning generalize beyond one-variable conditioning (a 4-node hub)? | PROCEED at both `N`, using the *unmodified* D-012 formula |
| — | (refactor, no new charter) | Safe to replace the triad-only pipeline special case with one general rule? | Proven the general mechanism is numerically identical to the original for one conditioning variable; verified the refactor reproduces D-014's exact original output before trusting it |
| D-016 | `docs/stage2c_charter.md` | Does the generalized pipeline handle a network with *both* triad and hub shapes at once? | PROCEED at both `N`; every D-014 finding replicated |
| D-017 | `docs/stage1l_charter.md` | Does the conditioning mechanism generalize to a *different* topology (two triangles sharing one node)? | PROCEED at both `N`, same unmodified formula — but explicitly scoped to the mechanism alone, not screening's ability to detect it |
| D-018 | `docs/stage2d_charter.md` | Does the overlap shape work when wired into the full pipeline? | **Split, and predicted almost exactly in writing before results existed**: REASSESS at `N=750` (screening only detects the weak cross-branch signal `~66%` per edge, so a clean candidate clique forms only `~29%` of the time), PROCEED at `N=1500` (`~98%`/`~92%`) |

Full narrative and evidence for each is in `docs/decision_log.md`.

## What specifically needs external review

1. **The `VALIDATED_CLIQUE_SIZES` extension to size 5, and its near-miss
   inertness check.** Before trusting the code generalization in
   `mintnet.pipeline.compose`, D-016's exact original configuration was
   re-run and found to differ from its originally-recorded output in
   *one* replicate out of 4,000 (a rare spurious 5-node clique, where the
   new code correctly improved a TPR from `.2` to `.6`). This was
   reported honestly rather than the originally-planned inertness claim
   being left unchecked or silently corrected. A reviewer should judge
   whether this one-replicate discrepancy was handled appropriately —
   investigated, understood, and disclosed — or whether it warrants
   deeper investigation before being accepted as benign.

2. **The per-motif (not pooled) gating design in D-018.** Given the
   project's own D-004 history (a pooled average once hid a per-family
   failure), Stage 2d's gate checks chain/fork/overlap TPR *separately*.
   A reviewer should check whether this design choice is applied
   consistently elsewhere it should be, and whether any earlier charter's
   pooled metrics (e.g., D-013's screening recall, pooled across three
   embedded motifs) deserve the same scrutiny retroactively.

3. **Pre-registered simulation checks before several charters (D-016,
   D-018) predicted specific numeric outcomes** (e.g., D-018's `~26%`
   clean-clique rate, `~.59` TPR) **that then closely matched the frozen
   results.** This is presented in the reports as evidence the underlying
   mechanism is understood, not merely observed. A reviewer should
   consider whether this reasoning is sound, or whether repeatedly
   "predicting your own results accurately" could instead indicate the
   pre-charter checks and the frozen runs are not sufficiently
   independent (e.g., because they share code paths, seeds, or DGP
   parameters) to count as separate confirmation.

4. **Scope creep versus the original outline.** The original governing
   plan (`outline/information_network_technical_build_plan.md`) did not
   anticipate testing multiple candidate-component *topologies*
   (hub, shared-node overlap) or wiring multiple generalizations into one
   pipeline before Stage 3. This extension was user-directed at each
   step, not autonomously decided, but a reviewer assessing overall
   project discipline should judge whether this depth of Stage 1/Stage 2
   exploration was proportionate, or whether it should have been
   time-boxed sooner in favor of proceeding to Stage 3 (bootstrap
   reproducibility, not yet started).

5. **The general-shape gap remains genuinely open, not resolved.** Every
   validated multi-node result (D-015, D-017) is for a *clean, fully-
   connected clique* of a specific size and topology. Non-clique
   candidate components (partial connectivity), cliques of size 6+, and
   components formed by more than two motifs sharing structure are all
   explicitly untested. A reviewer should confirm this is stated clearly
   enough in `docs/validated_operating_ranges.md` that a future user of
   this code would not mistakenly assume broader coverage than exists.

6. **New, unreviewed implementation.** `mintnet.dpi.multi_conditional`,
   `mintnet.screening.pairwise_correlation`, and `mintnet.pipeline.compose`
   are all new since the last review, have unit test coverage, but (like
   the modules flagged in the first review) have not had a second
   independent implementer look at them.

## Where to find everything new (index)

**New charters and reports** (this worktree's `docs/`): `stage1h`
through `stage1l` (charter + report pairs), `stage2`, `stage2b`, `stage2c`,
`stage2d` (charter + report pairs).

**Decision log**: `docs/decision_log.md`, entries D-009 through D-018.

**Tracking reference**: `docs/validated_operating_ranges.md` — now covers
seven components, including the two new prominent caveat sections (the
`N=750` vs. `N=700` default-floor justification, and the `N=1500`
shape-specific caveat for shared-node overlap).

**New source modules**, this worktree's `src/mintnet/`:
- `dpi/multi_conditional.py` — general multi-variable partial-correlation
  test (arbitrary conditioning set size)
- `screening/pairwise_correlation.py` — unconditional Fisher-z screening,
  uncorrected and Benjamini-Hochberg
- `pipeline/compose.py` — connected-components grouping and the
  screen-then-prune composition, including `VALIDATED_CLIQUE_SIZES`
- `simulation/motifs.py` — new `sample_hub` and
  `sample_overlapping_triangles` generators (existing `sample_chain`,
  `sample_measured_fork`, `sample_precision_triangle` unchanged)
- `simulation/screening_network.py` — the `p=15` known-ground-truth
  network used by Stage 2's charters
- `experiments/stage1h.py` through `stage1l.py`, `stage2.py` through
  `stage2d.py`, and their paired `_reporting.py` / `_fit.py` modules

**Tests**: `tests/unit/test_multi_conditional.py`,
`test_pairwise_correlation.py`, `test_pipeline_compose.py`,
`test_overlapping_triangles.py`, `test_screening_network.py`,
`test_stage1j_fit.py`, plus one `test_stage1*`/`test_stage2*`
`_runner.py` + `_reporting.py` pair per new charter. Full suite: 187
tests, all passing (`.venv/Scripts/python.exe -m pytest -q` from this
worktree).

**Configs**: one `stage1h_hub.yaml` through `stage1l_overlap.yaml`,
`stage2_screening.yaml` through `stage2d_composition.yaml` (each with a
paired `_smoke.yaml`), all in this worktree's `configs/`.

**Raw generated evidence** (git-ignored, local filesystem only, same
caveat as the first review — not visible via `git clone`):
`results/generated/stage1h_dpi/` through `stage1l_overlap/`,
`stage2_screening/` through `stage2d_composition/`, each containing
`raw_metrics.csv`, `decision.json`, `metadata.json`, and figures.

**Git audit trail**: `git log --oneline c4b14b6..HEAD` on branch
`codex/stage1-dpi-motifs` shows every commit since the first review, in
the same freeze-then-implement-then-record order as before.
