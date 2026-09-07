# Mintnet Handoff — 2026-08-28

## Purpose and governing outline

The project is developing a computationally tractable, loop-compatible,
information-theoretic network method for behavioral tabular data. Its governing
document is `outline/information_network_technical_build_plan.md`. The outline
requires mechanism-by-mechanism falsification: no later statistical layer may
be built until the preceding stage has a frozen charter, generated evidence,
and a written decision gate outcome.

The planned sequence is: Stage 0 MI estimator validation; Stage 1 tolerant-DPI
motif validation; Stage 2 candidate-edge screening; Stage 3 bootstrap
reproducibility; Stage 4 continuous MVP; then mixed-type, interpretation,
benchmarking, nonlinear, and synergy work. Only Stages 0 and 1 have been
started.

## Completed and committed on `main`

Stage 0.1 Gaussian MI validation is implemented and completed.

- `a277fe3 feat: add Stage 0 Gaussian MI validation`: Python package, KSG-1,
  Gaussian simulator, deterministic runner, reporting, configs, and tests.
- `3c51c41 docs: record Stage 0 Gaussian decision` and `e1febff`: R1 report
  and decision log.
- Frozen experiment: 72,000 estimates, zero errors, **PROCEED**, selected
  `k=20`; validation maximum absolute bias 0.0134 nats, maximum RMSE 0.0452,
  Spearman 1.00, null 95th percentile 0.0213.
- Generated evidence is ignored at `results/generated/stage0_gaussian/`.

## Current Stage 1 branch

Active worktree: `.worktrees/codex-stage1-dpi-motifs/`  
Branch: `codex/stage1-dpi-motifs`  
HEAD: `1cbd11e fix: require complete Stage 1 gate evidence`

The branch contains the committed Stage 1 design and plan:

- `docs/superpowers/specs/2026-08-28-stage1-dpi-motifs-design.md`
- `docs/superpowers/plans/2026-08-28-stage1-dpi-motifs.md`

The Stage 1 charter freezes continuous Gaussian chain, measured-fork, and
precision-triangle DGPs; 500 replicates; seed `20260829`; nine tau values;
development replicates 0–249; validation 250–499; and the gate: chain/fork
TPR >= .80 and triangle true-edge FPR <= .10 at N >= 500 for two adjacent tau
values. Any error or incomplete evidence is REASSESS.

Implemented on this branch:

- Motif fixtures (`c9cdfda`), strict DPI (`084189e`, `894af39`), pairwise MI
  and topology metrics (`8ad68fc`).
- Deterministic runner/config/charter (`690037c`) and CWD-independent
  provenance fix (`9476a7a`).
- Reporting, figures, gate selection, and runner integration (`455f748`),
  with fail-closed completeness checks (`1cbd11e`).

Reviews: Tasks 1–4 passed after fixes. Task 5 passed scoped re-review after
the missing-evidence fix. The latest full suite reported 45 passing tests.

## Important repository state

Two Task 4 commits were accidentally made directly on `main` while the branch
was being developed: `a7c69b4` and `655f692`. Equivalent commits were
cherry-picked onto the Stage 1 branch as `690037c` and `9476a7a`. Do not merge
the branch with a blind fast-forward; review the branch-to-main diff and
resolve duplicate patch ancestry deliberately.

The local Stage 1 worktree needs a working Python environment. Recreate it
with Python 3.11 (or the supported local runtime), then install `-e '.[test]'`.
If editable installation is unreliable, tests have been run successfully with
`PYTHONPATH=src`.

## Exact next actions

1. Run `python -m pytest -q` in the Stage 1 worktree and confirm the current
   branch is clean.
2. Run the smoke CLI: `python -m mintnet.experiments.stage1 --config
   configs/stage1_dpi_smoke.yaml --output results/generated/stage1_dpi_smoke`.
   Smoke REASSESS is expected because it lacks the N>=500 gate regime.
3. Run the frozen full CLI to `results/generated/stage1_dpi/`. Expected raw
   rows: `3 motifs * 6 N * 3 strengths * 500 replicates * 9 tau = 243,000`.
   Use below-normal priority and a memory guard, as in Stage 0.
4. Inspect `decision.json`. Do not edit `docs/stage1_charter.md`. Update
   `docs/stage1_report.md` and `docs/decision_log.md` with R2 evidence and
   PROCEED/REASSESS, then commit.
5. Only if R2 is PROCEED, plan Stage 2 candidate-edge screening. If REASSESS,
   document the failure and do not build screening, bootstrap, or mixed-type
   layers.
