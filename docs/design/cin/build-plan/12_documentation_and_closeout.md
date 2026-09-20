# Task 12 — Documentation, decision log, and close-out

Roadmap: §9 M5, §13. Files: `docs/cin_user_guide.md`, `docs/cin_cost_charter.md` and `docs/cin_baseline_charter.md` (finalized in tasks 10–11), decision-log entry in `docs/decision_log.md`, optional short pointer in `README.md`, worked examples under `examples/` or `docs/` (match repository practice; inspect first).

## 1. Purpose

Leave the repository in a state where another researcher can reproduce a fit and a displayed view, where every claim maps to recorded evidence (or is explicitly withheld), and where historical evidence is untouched.

## 2. Preconditions

Tasks 01–07 complete and unit-tested; task 10 decision recorded; task 11 report produced (or the reduced/unsupported scope decision recorded).

## 3. Final regression run

```bash
python -m pytest tests/unit/cin tests/integration/test_cin_runners.py
```

Also run the existing active suite areas that could have been affected (imports, `simulation`, shared scripts): `python -m pytest tests/unit tests/integration -x -q` is a starting point; run the full active suite if it is fast enough. Generic shard aggregation and workflow behavior is covered by `tests/integration/test_cin_runners.py`; historical tests remain under `archive/mi_native_search/tests/` and are not collected. Confirm no archived API was modified (invariant I9).

## 4. User guide (`docs/cin_user_guide.md`) outline

1. **What this is / is not**: undirected weighted map of conditional predictive information under an explicitly stated model; not causal, not a significance test, not a sparse selection; units are nats per observation; independent-participant cross-sectional scope.
2. **Install and environment**: repository Python 3.11; dependencies already in `pyproject.toml`; no R, no networkx.
3. **Quick start** (continuous): code that runs, with a small built-in example and expected output structure.
4. **Declaring the schema**: continuous vs categorical (levels, ordered as metadata only); missing-data policy; constants rejected; what diagnostics mean.
5. **The fit**: default settings table (roadmap §3) labelled "initial engineering settings"; runtime expectations *quoted from the cost pilot's measured results only* (no invented numbers); budgets; statuses.
6. **Reading results**: pair table columns, node diagnostics, how negative weights arise, orientation gap, `gaussian_equivalent_magnitude` (unsigned analogy only), why no sign.
7. **Views**: Landscape / Effect-filtered / Agreement-filtered / Stable subset / Presentation limit with literal meanings; δ is a researcher relevance threshold, **not** a significance threshold; example values illustrative; changing views never refits; changing variables/types/basis/tuning needs a new fit.
8. **Stability**: how to call it, B/fraction/budget/resume, meaning (reproducibility under subsampling), resolution, unavailable-stability semantics.
9. **Dense and low-N use**: p near 100 → matrix and sortable table; presentation limit is not evidence; no universal N/p rule; show retained N, p, rare-category counts, model performance.
10. **Mixed/categorical items**: status of the categorical branch **as determined by the evidence** (supported, or "experimental — validation gate failed"); ordinal order not used.
11. **Limitations** (verbatim from methodology §5–§9): variance-only dependence, XOR, extreme skew/floor-ceiling, counts, missingness bias, repeated measures/multilevel, DAG orientation not implied, Gaussian EBICglasso remains a strong comparator in its regime.
12. **Reproducing the published evidence**: exact verified `gh workflow run` command(s) from task 09 §8, config paths, charter hashes, run IDs, the aggregation and sidecar steps, and the gate script.
13. **Methods paragraph**: how `methods_text()` output should be cited; what not to claim.

Every code block in the guide must be executed once (doctest-style or a scripted check in the integration tests) so it is not aspirational.

## 5. Two worked examples

- **Continuous**: ~10 construct scores (bundled synthetic frame with a planted U-shaped pair), fit → landscape → effect-filtered → agreement-filtered → optional stability (B=10) → export → methods text. Include the linear-only comparison showing the U-shaped pair missed by `max_curvature_rank=0` (numerically small illustrative result; do not overclaim).
- **Mixed/categorical items**: explicit schema with five-level items, an ordered flag, one binary and continuous scores; **label experimental until the M4 categorical gates pass**, and if they failed, keep the warning permanently.

## 6. Decision log entry

Append to `docs/decision_log.md` under the **next available identifier** (currently after D-091; re-check the file). Use the file's existing entry style. Content: the decision to build the CIN baseline; the plan/outline provenance; the evidence produced (cost pilot verdict, development and validation gate table with counts, ledger runner-hours, repeat-stability outcome); the one profiling pass and one global correction if used; scope verdicts **individually** — continuous preview, categorical branch, p=100 runtime, low-N claim; explicit disclosure of gaps (high-p categorical recovery unevidenced, comparator caveats, 20-replicate resolution); what remains deferred. Do not rewrite frozen entries. Do not add AI coauthor requirements to the log; commit trailers follow the session's attribution reminder only in git.

## 7. Charters and provenance bundle

Ensure `docs/cin_cost_charter.md` and `docs/cin_baseline_charter.md` contain final frozen content and hashes, and that a `results/`-side provenance note (or an appendix in the charters) lists: config hash, charter hash, code revision, environment/BLAS, dispatch run IDs, dev vs validation seed ranges, ledger totals. Follow the repository's convention for where generated results live (`results/generated/...` is used by smoke commands; check whether evidence directories are tracked).

## 8. Status statement (required last section of the user guide and the decision-log entry)

State, individually and with references: (a) continuous preview passed/failed/not evaluated; (b) categorical item branch passed/failed/experimental; (c) p=100 runtime supported/unsupported (with measured numbers); (d) low-N (Case C, I) claim supported/unsupported; (e) stability tested on A/B/F with results; (f) items explicitly not built (deferred nice-to-haves, roadmap §13).

## 9. Completion criteria (roadmap §13)

Complete when: numerical and integration contracts pass; measured cost/utility scope recorded honestly; exports and optional stability work; input-type claims supported or explicitly withheld; the guide lets another researcher reproduce a fit and its displayed view. **Not** required: sign-aware outputs, normal-score sensitivity, GCV/dual, marginal networks, ordinal-order models, interactions, imputation, clustered/time-series, centrality, causal extensions. Optional extensions require a separate prioritized request.

## 10. Final commit sequence

1. Docs and examples commit (`docs:`).
2. Decision log commit (`docs:` — kept separate so evidence provenance is easy to audit).
3. Only stage files created by this project (charter, guide, log); leave unrelated working-tree changes (such as the pre-existing `.gitignore` modification) alone unless asked.

## 11. Pitfalls

- Do not quote timings, precision, or recall from the smoke reports or from Claude's feasibility script as evidence for this final procedure (feasibility review §4F).
- Do not describe stability as a probability of an edge, or δ as significance.
- Do not describe the categorical model as logistic regression or as a validated ordinal model.
