# CIN build plan: index, conventions, and dependency order

Date: 2026-09-19. Source of truth for *what* to build: [methodology outline](../methodology/methodology_outline_2026-09-19.md), [technical roadmap](../methodology/technical_implementation_roadmap_2026-09-19.md), [feasibility review](../methodology/feasibility_review_2026-09-19.md). These plan files expand the roadmap into task-level build instructions. Where a plan file adds a concrete choice the roadmap left open, it is tagged **[added]** so a reviewer can tell roadmap-mandated behavior from plan-level decisions. Where a plan file interprets an ambiguous roadmap sentence, it is tagged **[interpretation]**.

Product name in code: `mintnet.cin` (conditional predictive-information network). Nothing here changes the archived search/screening/bootstrap/DPI code.

## 1. Task files and dependency order

| # | File | Roadmap milestone | Depends on |
|---|---|---|---|
| 01 | [Config, schema, and data contract](01_config_schema_data_contract.md) | M1 | none |
| 02 | [Feature blocks and response matrix](02_feature_blocks_and_responses.md) | M1 | 01 |
| 03 | [Shared ridge engine and exact block omission](03_shared_ridge_engine.md) | M1 | 02 |
| 04 | [Scores and penalty tuning](04_scores_and_tuning.md) | M1 | 02, 03 |
| 05 | [Cross-fitting and fit orchestration](05_crossfit_fit_orchestration.md) | M2 | 01–04 |
| 06 | [Results, views, exports, methods text](06_results_views_exports.md) | M3 | 05 |
| 07 | [Optional repeated-refit stability](07_stability.md) | M3 | 05, 06 |
| 08 | [Simulation generators and exact truth](08_simulation_truth.md) | M2/M4 | 01 (schema shape) |
| 09 | [Runner and Actions infrastructure](09_runner_actions_infrastructure.md) | M2/M4 | 05, 08 |
| 10 | [Cost pilot (p=100 gate)](10_cost_pilot.md) | M2 | 05, 08, 09 |
| 11 | [Bounded statistical panel](11_statistical_panel.md) | M4 | 06, 07, 08, 09, 10 |
| 12 | [Documentation, decision log, close-out](12_documentation_and_closeout.md) | M5 | all |

```text
01 -> 02 -> 03 -> 04 -> 05 --+--> 06 -> 07 --+
                             |               |
 08 (parallel after 01) -----+--> 09 -> 10 --+--> 11 -> 12
```

Files 01–05 form the numerical core and must be finished, and their unit suites green, before 10 is dispatched. File 08's generators can be built in parallel with 02–05 because they only need the schema shape from 01.

## 2. Global invariants (checked in review of every task)

Copied from roadmap §1 so each task file can reference them by number.

- **I1** No conditioning-subset enumeration, marginal/Pearson screening, neighbor cap, or reuse of historical confidence curves.
- **I2** Every unordered pair gets a row with a `status`. Incomplete is never zero and never NaN-to-zero.
- **I3** All transforms, scalings, knots, prevalences, and penalty selection are fit on training rows only, with one set of splits shared by all targets.
- **I4** The target's own predictor block is removed before scoring *any* model, including tuning models.
- **I5** "Omit a predictor" means the exact restricted ridge at the same λ with the same feature centering/scaling. Never mask, permute, renormalize, retune, or one-step approximate.
- **I6** Signed raw gains are stored; display magnitude is `max(w, 0)`.
- **I7** Views never refit. There is no sign field that can zero an edge.
- **I8** Ordinary `fit_network` never resamples. Stability is an explicit separate call with count and budget.
- **I9** Historical modules and frozen evidence are untouched. New code lives in `mintnet.cin`, `mintnet.simulation.cin_networks`, and `mintnet.experiments.cin_*`.
- **I10** Local runs are for correctness only. Comparative/timing evidence comes from the sharded Actions workflow under a frozen charter.

## 3. Repository facts verified while writing this plan

Read directly from the repository at HEAD `069c10e` (branch `main`; `.gitignore` modified and uncommitted):

- Python is pinned `>=3.11,<3.12`. Runtime deps in `pyproject.toml`: matplotlib, numpy, pandas, PyYAML, scipy, scikit-learn. Test extra: pytest, pytest-xdist. `threadpoolctl` is a scikit-learn dependency, so it is available for thread control without a new dependency.
- `src/mintnet/simulation/` holds `gaussian.py` and `motifs.py` (contains `sample_organic_network(n, rng)`). `src/mintnet/comparators/ebicglasso.py` exposes `fit_ebicglasso` and `EBICglassoResult`.
- The generic shard contract, from `scripts/aggregate_shards.py` and the historical `archive/mi_native_search/src/mintnet/experiments/stage5a.py`: the runner module exposes `load_config(path)`, `expected_row_count(config)`, `expected_combinations(config)`, `COMBINATION_COLUMNS`; a sibling `<module>_reporting` exposes `write_report(raw, config, output_dir)`. The aggregator concatenates `*/raw_metrics.csv`, requires `len(raw) == expected_row_count`, requires the *set* of `COMBINATION_COLUMNS` tuples to equal `expected_combinations`, and rejects duplicates on `COMBINATION_COLUMNS + ["replicate"]` when a `replicate` column exists. It copies only `resolved_config.yaml` and a synthesized `metadata.json`. **It does not collect any other per-shard file.** This is why file 09 specifies sidecar handling.
- `stage5a._condition_seed` uses `np.random.SeedSequence([master_seed, _STAGE_TAG, dgp_index, sample_index, replicate])` with indices from the *full* grid. File 09 reuses this pattern.
- `.github/workflows/sharded_benchmark.yml` inputs: `runner_module`, `config`, `dim1_flag/values`, `dim2_flag/values`, optional `dim3_flag/values`. Archived cost workflows (`archive/mi_native_search/.github/workflows/stage10a_cost.yml`, `stage9d_full_repeat_cost.yml`) are dedicated precedents that set `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS`; the CIN plan requires **1** thread, not the 2 used there.
- Latest decision log entry is D-091 (search-architecture failure post-mortem). Take the next free identifier at write time.

Recheck all of the above before coding; the roadmap itself says to.

## 4. Conventions for every task

**Code style.** Match surrounding repository style: `from __future__ import annotations`, frozen dataclasses for configs/results, `numpy.random.Generator` passed explicitly, no global RNG, module docstrings that state the contract, minimal comments. NumPy float64 everywhere; C-contiguous arrays for solve inputs.

**Determinism.** No `hash()`, no set iteration order in numerics, no reliance on dict ordering other than insertion order that is itself derived from schema order. Every random stream is `np.random.SeedSequence` derived from documented keys.

**Tolerances.** Direct-vs-shared comparisons for well-conditioned fixtures: `rtol=1e-8, atol=1e-10`. Anything looser needs a written justification in the test.

**Testing layout.** `tests/unit/cin/` (new package; add an empty `__init__.py` only if the existing unit tree uses them — check first) and `tests/integration/test_cin_runners.py`. Unit tests must run in seconds; nothing in `tests/` may generate N≥5000 data or run more than a few seconds of solver work.

**Commit hygiene.** One logical commit per task file section that passes its own tests. Commit messages follow the repository's `feat:/test:/docs:` style seen in `git log`. End with the attribution line supplied by the session's commit reminder.

**Status vocabulary (shared by files 05–07):** `complete`, `unsupported`, `numerical_failure`, `budget_exceeded`, `not_started`. Repeat-level extras in file 07: `budget_not_started` (request-level), `unsupported_repeat_request`.

## 5. Interpretations and gaps adopted across the plan

1. **[interpretation]** Roadmap §11.3 gate 2 says "each case has mean all-edge precision ≥ 0.70 …". Read as applying to cases A and B (the only ones named in the same gate). C, D, E, I are covered by other gates or descriptive.
2. **[interpretation]** "Full-model categorical held-out excess loss versus the intercept no worse than 0.10 nats per node" is read as `mean_node(intercept_score − full_score) ≤ 0.10` using per-observation mean log scores, averaged over nodes then replicates.
3. **[added]** The δ-selection rule for gate 2 is not given in the roadmap; file 11 §6 proposes one, to be frozen in the charter.
4. **[added]** Linear-only comparator is implemented as `CINConfig(max_curvature_rank=0)` rather than a separate code path; the roadmap requires "the same scoring/tuning engine using linear-only predictor blocks".
5. **[added]** Peak process memory is measured with `resource.getrusage(RUSAGE_SELF).ru_maxrss` on the Linux runner; not measured locally on Windows.
6. **[added]** The extra artifacts (pair tables, repeat tables, fold diagnostics) are stored per shard as `pairs/*.csv.gz` with a `sidecar_manifest.csv`, collected by a CIN-specific aggregation wrapper (file 09) rather than by modifying `aggregate_shards.py`.
7. Ambiguity kept open in the roadmap and **not** resolved here: the exact numeric definitions of "strong-edge" for case E (no oracle CMI is required for E; strong-edge recall gates apply only to A and B).

## 6. Definition of done (whole plan)

Mirrors roadmap §13: numerical and integration contracts pass; measured cost and utility scope recorded honestly, including any failed gate; exports and optional stability work; each input-type claim (continuous, categorical, mixed, p=100 runtime, low-N) is individually recorded as passed or withheld; the user guide lets another researcher reproduce a fit and a displayed view; decision-log entry appended. Unbuilt nice-to-haves do not make the baseline incomplete.
