# Peer Review Brief — Mintnet Stage 0 / Stage 1, 2026-08-29

## Purpose of this document

This project is developing a computationally tractable, information-theoretic
network method for behavioral tabular data, governed by a build plan that
requires mechanism-by-mechanism falsification: no later statistical layer is
built until the preceding one has a frozen charter, generated evidence, and a
written decision-gate outcome. This brief is an intermittent checkpoint,
written for an independent reviewer (human or AI) with no prior context on
this project, to sanity-check the work completed so far before continuing.

It covers: what has been done, what specifically deserves external scrutiny,
and exactly where the evidence lives so a reviewer can verify claims rather
than take them on faith.

## Repository locations (read this first)

Two separate locations are involved:

1. **Main checkout**: `C:\Users\imhoh\GitHub\mintnet` (branch `main`). Contains
   Stage 0's completed, merged work.
2. **Active worktree**: `C:\Users\imhoh\GitHub\mintnet\.worktrees\codex-stage1-dpi-motifs`
   (branch `codex/stage1-dpi-motifs`, not yet merged to `main`). Contains all
   Stage 1 work (charters `1` through `1h`). All Stage-1-relative paths below
   are relative to this worktree unless stated otherwise.

**Important**: `results/generated/` is git-ignored in both locations. Every
`.csv`, `.json`, and `.png` under it exists only on this local filesystem —
an independent reviewer looking only at a `git clone` or a GitHub view of
this repository will **not** see any raw evidence, only the charters, code,
and narrative reports that reference it. If the reviewer needs the actual
numbers (not just the summarized tables in the reports), those files need to
be shared directly (copied, zipped, or the reviewer needs local filesystem
access to these two paths).

A known, still-unresolved git-hygiene issue: two commits (`a7c69b4`,
`655f692`) were made directly on `main` while this branch was in progress;
equivalent commits were cherry-picked onto this branch as `690037c` and
`9476a7a`. **Do not merge this branch to `main` with a blind fast-forward**
— the ancestry needs deliberate reconciliation first. A reviewer evaluating
merge-readiness should look at this specifically.

## What has been done

### Stage 0 (main branch, merged, complete)

Validated the bivariate KSG-1 mutual-information estimator on continuous
Gaussian data, `N = [100...1000]`, `k = [3,5,10,20]`. Selected `k=20`.
**Outcome: PROCEED.**

- Charter: `docs/stage0_charter.md` (in the main checkout)
- Decision: `docs/decision_log.md`, entry **D-001** (in the main checkout)
- Report: `docs/stage0_report.md` (in the main checkout)
- Evidence: `C:\Users\imhoh\GitHub\mintnet\results\generated\stage0_gaussian\`
  (72,000 estimates, zero errors)
- Code: `src/mintnet/mi/ksg.py`, `src/mintnet/mi/matrix.py` (main checkout)

### Stage 1 (this worktree, nine charters, R2 through R2h)

The objective throughout: test whether a "DPI" (data-processing-inequality)
pruning rule can correctly remove a spurious indirect connection (A—B—C,
where A and C are only related through B) while correctly keeping a genuine
direct connection, using only three-variable synthetic test cases (chain,
measured fork, and triangle motifs) where the right answer is known by
construction.

| # | Charter | What changed | Outcome | Why |
|---|---|---|---|---|
| R2 | `docs/stage1_charter.md` | Original mechanism: prune the weakest of three pairwise-correlation edges if it's much weaker than the other two | **REASSESS** | Could not distinguish "real but weaker" from "fake" — wrongly pruned real edges at every tolerance setting tested |
| R2b | `docs/stage1b_charter.md` | New mechanism: test each edge's own conditional independence (partial correlation, exact equivalent of conditional MI for Gaussian data) instead of comparing edges to each other | **REASSESS**, but confirmed the fix works for 2 of 3 test fixtures; 3rd fixture's failure improved with sample size (a good sign) | Root cause diagnosed correctly; remaining issue looked like insufficient N, not a broken mechanism |
| R2c | `docs/stage1c_charter.md` | Raised sample-size floor 500→750, added N=1500/2000 to test the "not enough data" hypothesis | **REASSESS** | Confirmed the power hypothesis directly (error rate fell to near zero by N=2000), but the automatic selection rule's *pooled average* across N masked a still-failing case at moderate N — a bug in the evaluation, not the mechanism |
| R2d | `docs/stage1d_charter.md` | Fixed selection to require every individual (N, strength) cell to pass, not just the average (reused R2c's data, no new simulation) | **REASSESS** | Found only one isolated alpha value that passed everywhere, with no working neighbor — but the near-misses were smaller than expected statistical noise |
| R2e | `docs/stage1e_charter.md` | Quadrupled replicates (500→2000) to check whether those near-misses were noise | **REASSESS** | One near-miss firmed into a real (non-noise) failure; another shrank toward passing — pointed at needing finer resolution in the settings being tested, not more data |
| R2f | `docs/stage1f_charter.md` | Narrowed the settings grid to fine 0.01 steps in the promising region | **REASSESS**, by the smallest margin yet (0.004, under half a standard error) | The auto-picker grabbed the first setting that barely passed instead of a much more robust neighboring one it never got to test — a second, different bug in the selection rule |
| R2g | `docs/stage1g_charter.md` | Fixed selection to prefer the most robust passing pair, not the first one found (reused R2f's data, no new simulation) | **PROCEED** | First clean pass: setting ≈0.14–0.15 works with real margin (~3–4x the noise level) at every sample size from 750 to 2000 |
| R2h | `docs/stage1h_charter.md` | Extended to test whether *different* sample sizes need *different* settings (100–3000), rather than requiring one global setting | Per-sample-size table, not a single status (by design) | N≥750: clean, monotonic relationship (larger N → stricter setting, bigger margin) across 5 points. N≤300: decisive, unbridgeable gap — no setting works, at any strictness. N=500: a near-miss by one grid step, unresolved |

Full narrative for every entry above, including the reasoning for each
REASSESS/PROCEED call, is in `docs/decision_log.md`, entries **D-002**
through **D-009**.

### Supporting artifact

`docs/validated_operating_ranges.md` — a maintained (not chronological)
reference table of which components are validated for fully automatic,
data-driven decisions at which minimum sample size, versus where a
researcher's own theoretical justification should carry the decision
instead. Reflects an explicit project stance: small-N decisions are
expected to need more researcher judgment, not more validation engineering.

## What specifically needs external review

This section is deliberately candid about where I think independent scrutiny
would be most valuable — not just "please check everything," but the
specific judgment calls and risk points a reviewer should focus on.

1. **The Gaussian-equivalence claim (R2b's core justification).** The whole
   pivot from magnitude-ratio comparison to partial-correlation testing rests
   on the claim that, for jointly Gaussian data, testing partial correlation
   against zero is mathematically identical to testing conditional mutual
   information against zero (`I(X;Y|Z) = -0.5*ln(1 - r_partial^2)`). This is
   asserted and used repeatedly (`docs/stage1b_charter.md`, background
   section) but should be independently verified, including whether the
   Fisher z-transform's degrees-of-freedom adjustment (`sqrt(N-4)` for one
   conditioning variable) is applied correctly in
   `src/mintnet/dpi/conditional.py`.

2. **The margin-robust selection rule (R2g) and per-N selection rule (R2h).**
   These are novel evaluation-methodology choices I designed mid-investigation
   in response to two different bugs found in the original "first eligible
   pair" rule. They are reasonable but not the only possible fix — a reviewer
   should consider whether maximizing worst-case margin is the right
   objective (versus, say, maximizing average margin, or some other
   robustness criterion), and whether the per-N independence assumption in
   R2h (no smoothing or sharing of information across neighboring N) is
   appropriate or overly conservative.

3. **The "decisive vs. boundary" classification for small N (R2h).** N≤300
   is called a "decisive, unbridgeable gap" based on a 23-point alpha sweep
   up to 0.50. A reviewer should check whether this conclusion is solid or
   whether an even more extreme alpha, or a different test statistic
   entirely, could plausibly rescue it — I did not exhaustively rule this
   out, only the tested range.

4. **Evidence reuse across charters (R2d reusing R2c's data; R2g reusing
   R2f's; R2h using its own fresh simulation).** The stated rationale is that
   only the *analysis/selection rule* changed between these pairs, not the
   underlying simulated data or any value being cherry-picked, so reuse is
   legitimate rather than a form of data snooping. A reviewer should verify
   this reasoning holds — in particular, confirm (e.g., via
   `tests/integration/test_stage1d_runner.py`,
   `test_stage1g_runner.py` provenance/hash checks) that the reused files are
   byte-identical to their source and that no manual selection of favorable
   subsets occurred.

5. **Code correctness of newly written modules.** Everything under
   `src/mintnet/dpi/conditional.py`,
   `src/mintnet/experiments/stage1b.py` through `stage1h.py`, and their
   `*_reporting.py` counterparts was written in this session and has unit
   test coverage but has not had a second independent implementer or
   reviewer look at it (unlike the original Stage 1 magnitude-ratio DPI code,
   which the handoff notes went through five rounds of review before this
   session started — see `docs/handoff_stage1.md`).

6. **Representativeness of the triangle fixtures.** All triangle evidence
   comes from three fixed precision matrices (`balanced`, `moderate`,
   `strong`; see `src/mintnet/simulation/motifs.py`,
   `_TRIANGLE_PRECISIONS`). These were chosen once at the start of Stage 1
   and never revisited. A reviewer should consider whether three fixed
   points adequately represent the space of real-world "one edge much weaker
   than the other two" triangles, or whether the eventual `alpha(N)` rule
   (not yet built) risks overfitting to these three specific configurations.

7. **Readiness to proceed.** Given R2g's single-global-alpha PROCEED and
   R2h's richer per-N table, is Stage 1 sufficiently validated to begin
   chartering Stage 2 (candidate-edge screening), or does the N<750 boundary
   (and the still-open question of a formal `alpha(N)` rule) warrant closing
   that gap first? This is a scope/sequencing judgment call, not a
   correctness question, and worth a second opinion.

## Where to find everything (quick index)

**Governing plan:**
`outline/information_network_technical_build_plan.md` (main checkout)

**Charters (frozen-before-results specifications), this worktree's `docs/`:**
`stage1_charter.md`, `stage1b_charter.md`, `stage1c_charter.md`,
`stage1d_charter.md`, `stage1e_charter.md`, `stage1f_charter.md`,
`stage1g_charter.md`, `stage1h_charter.md`

**Reports (per-run narrative and numbers), same directory:**
`stage1_report.md` through `stage1h_report.md`

**Decision log (chronological, all entries D-001 through D-009):**
`docs/decision_log.md`

**Tracking reference:** `docs/validated_operating_ranges.md`

**Prior handoff (context on repository state before this session):**
`docs/handoff_stage1.md`

**Source code, this worktree's `src/mintnet/`:**
- `dpi/prune.py` — original magnitude-ratio DPI (superseded, kept for
  historical/comparison purposes)
- `dpi/conditional.py` — current conditional-independence mechanism
- `simulation/motifs.py`, `simulation/gaussian.py` — data-generating process
- `metrics/topology.py` — motif scoring (TPR/FPR)
- `mi/ksg.py`, `mi/matrix.py` — Stage 0's estimator, still imported by the
  original (now superseded) `experiments/stage1.py`
- `experiments/stage1.py` / `stage1_reporting.py` — R2
- `experiments/stage1b.py` / `stage1b_reporting.py` — R2b
- `experiments/stage1c.py` / `stage1c_reporting.py` — R2c
- `experiments/stage1d.py` / `stage1d_reporting.py` — R2d (reporting-only,
  reuses R2c's raw evidence)
- `experiments/stage1e.py` / `stage1e_reporting.py` — R2e
- `experiments/stage1f.py` / `stage1f_reporting.py` — R2f
- `experiments/stage1g.py` / `stage1g_reporting.py` — R2g (reporting-only,
  reuses R2f's raw evidence)
- `experiments/stage1h.py` / `stage1h_reporting.py` — R2h

**Tests, this worktree's `tests/`:**
`unit/test_conditional.py`, `unit/test_dpi.py`, and one
`integration/test_stage1*_runner.py` + `test_stage1*_reporting.py` pair per
charter. Run with `.venv/Scripts/python.exe -m pytest -q` from this
worktree (Python 3.11.9 venv already provisioned at `.venv/`).

**Configs** (frozen run parameters), this worktree's `configs/`:
one `stage1*_dpi.yaml` (frozen full run) and `stage1*_dpi_smoke.yaml`
(quick sanity check) per charter.

**Raw generated evidence** (git-ignored, local filesystem only):
- Stage 0: `C:\Users\imhoh\GitHub\mintnet\results\generated\stage0_gaussian\`
- Stage 1 (each directory has `raw_metrics.csv`, `aggregate_metrics.csv`,
  `decision.json`, `calibration_summary.csv`, `metadata.json`, and figure
  PNGs): `results/generated/stage1_dpi/`, `stage1b_dpi/`, `stage1c_dpi/`,
  `stage1d_dpi/`, `stage1e_dpi/`, `stage1f_dpi/`, `stage1g_dpi/`,
  `stage1h_dpi/` (all under this worktree's `results/generated/`)

**Git audit trail:** `git log --oneline` on branch `codex/stage1-dpi-motifs`
in this worktree shows every commit in the sequence above, each tagged with
a `docs:` (charter freeze or decision record) or `feat:` (implementation)
prefix in the order they were made — freeze-before-implement-before-record,
consistently, which a reviewer can spot-check against the actual commit
timestamps and diffs.
