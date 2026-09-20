# Task 09 — Runner and Actions infrastructure

Roadmap: §12, M2/M4. Files: `src/mintnet/experiments/cin_cost.py`, `cin_cost_reporting.py`, `cin_baseline.py`, `cin_baseline_reporting.py`, shared helper `src/mintnet/experiments/cin_common.py` **[added]**, `scripts/aggregate_cin_sidecars.py` **[added]**, `tests/integration/test_cin_runners.py`, `configs/cin_*.yaml`.

## 1. Purpose

Make both evidence runners (cost pilot, statistical panel) shardable through the repository's existing generic workflow, with deterministic seeds, incremental rows, sidecar tables, provenance, thread control, and integration tests. Before coding, **re-read** the historical `archive/mi_native_search/src/mintnet/experiments/stage5a.py` and `stage5a_reporting.py`, active `.github/workflows/sharded_benchmark.yml` and `scripts/aggregate_shards.py`, plus archived cost precedents `archive/mi_native_search/.github/workflows/stage10a_cost.yml` and `archive/mi_native_search/scripts/stage10a_cost_shard.py`; signatures may have changed since this plan.

## 2. Contract to satisfy (verified at HEAD `069c10e`)

Each runner module must expose:

- `load_config(path) -> Config` (a frozen dataclass; store `source_path`),
- `expected_row_count(config) -> int`,
- `expected_combinations(config) -> set[tuple]`,
- `COMBINATION_COLUMNS: tuple[str, ...]`,
- CLI: `--config`, `--output`, shard-selector flags, `--no-report`, optional `--workers`,
- companion `<module>_reporting.py` exposing `write_report(raw, config, output_dir)`.

Aggregator facts to design around: it requires `len(raw) == expected_row_count(config)`; the set of `COMBINATION_COLUMNS` tuples must equal `expected_combinations`; duplicates are checked on `COMBINATION_COLUMNS + ["replicate"]` when a `replicate` column exists; only `raw_metrics.csv` per shard is concatenated; only `resolved_config.yaml` and a synthesized `metadata.json` are propagated. It does **not** verify or collect other files. Therefore CIN sidecars need their own handling (§6).

## 3. Shard axes

Keep the matrix small (roadmap: do not reproduce a 225-shard benchmark). Use two dimensions passed through the existing workflow's `dim1_flag/dim2_flag`:

- **Cost runner** (`cin_cost`): `--cells` (eight cell ids from task 10) as dim1; optional `--repeat` (`1,2`) as dim2 to run the boundary-repeat as separate jobs. Total ≤ 16 jobs.
- **Panel runner** (`cin_baseline`): `--cases` (A–I plus `regression`) as dim1; `--replicate-batches` (`dev0, val0, val1`, i.e. development 10 replicates as one batch, validation 20 replicates in two batches of 10) as dim2. About 10 × 3 = 30 jobs before comparators. Comparators run **inside** the same shard on the identical draw (paired same-draw, as in `stage5a`).

`COMBINATION_COLUMNS` for the panel: `("case", "phase", "method")` with `phase ∈ {development, validation}`; `replicate` is a separate column enabling the aggregator's duplicate check. Methods: `cin`, `cin_linear`, `ebicglasso` (continuous cases A–E only; categorical/mixed cases have `cin` and `cin_linear`? **linear-only is comparator only for continuous A–E**, so `cin_linear` only there). `expected_combinations` and `expected_row_count` must implement these exact case→method availability rules.

## 4. Seeds

```text
seed(case_idx, phase_idx, replicate) = SeedSequence([master_seed, _CIN_TAG, case_idx, phase_idx, replicate])
   -> children: [structure, sample, cin_fit, comparator_fit, stability]
```

`case_idx`, `phase_idx`, and `replicate` come from the **full** grid (not the shard's filtered subset), so sharded output equals unsharded output (bit-identical except `elapsed_seconds`). `_CIN_TAG` is a fixed integer constant documented in the charter. Development replicates use indices `[0, 10)` and validation `[1000, 1020)` **[added]** so development seeds cannot collide with validation seeds and can never be reused for acceptance (roadmap M4). The exact ranges live in config as `development_replicates: [0, 10]`, `validation_replicates: [1000, 1020]` (stage5a convention: check its config keys and mirror them).

## 5. Raw rows and provenance

- Append and **flush after each completed method/dataset**, including failure rows (`status`, `error_type`), so a killed job keeps completed work. Do not batch rows to the end.
- Each raw row: identifiers (`case, phase, replicate, method`), seeds, `n, p`, `elapsed_seconds`, statuses and completion counts, metric columns (task 11), and for the cost runner the phase timings, factor counts, peak RSS, `q, t`, fallbacks.
- Repeated method rows on the same dataset are not independent datasets; reporting divides by unique `(case, phase, replicate)`.
- Per shard write: `raw_metrics.csv`, `resolved_config.yaml` (full-grid, identical across shards), `metadata.json` (`charter_sha256`, `config_sha256`, git commit, python/platform, numpy/scipy/sklearn/pandas versions, BLAS library and thread settings from `threadpoolctl.threadpool_info()`, runner CPU model, `runtime_seconds`, `peak_rss_mb`). Mirror the archived `archive/mi_native_search/src/mintnet/experiments/stage7b_frontier.py` evidence fields where they exist so `aggregate_shards.py`'s synthesized metadata still works.
- **Thread control**: set `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=1` **before importing numpy** (workflow `env:` block) *and* wrap fits in `threadpoolctl.threadpool_limits(1)` as a guard; record the actual limits. Note the precedent workflows use 2 threads; CIN evidence uses 1.

## 6. Sidecars (pair tables, repeat tables, fold diagnostics)

Because the generic aggregator ignores non-`raw_metrics.csv` files:

- Each shard writes `sidecars/<case>_<phase>_<replicate>_<method>.csv.gz` for pair tables (and `..._stability.csv.gz` where applicable), plus `sidecar_manifest.csv` with columns `file, case, phase, replicate, method, kind, n_rows, sha256`.
- `scripts/aggregate_cin_sidecars.py --shards-dir D --output O`: **after** the generic aggregator runs, collect manifests, verify every raw row that promises a sidecar has exactly one file with the declared row count and hash (pair tables must have `p(p−1)/2` rows; stability tables `B·p(p−1)/2`), reject duplicates and orphans, and concatenate into `pairs_all.csv.gz` / `stability_all.csv.gz` with a combined manifest. Fail loudly on any mismatch.
- Add this as an additional workflow step **only if** the generic workflow cannot be left unchanged; the roadmap prefers preserving `sharded_benchmark.yml`. Preferred option: keep `sharded_benchmark.yml` untouched, upload each shard's full directory as an artifact (it already uploads shard artifacts — confirm), and run `aggregate_cin_sidecars.py` as a separate local/Actions step on the downloaded shard directory. Any change to shared infrastructure needs focused tests (roadmap §12).
- Reporting reads pair sidecars (for AP, precision/recall at δ, oracle error) from the aggregated directory; `write_report(raw, config, output_dir)` must therefore accept sidecars located under `output_dir/sidecars` when present and **fail with a clear message if required sidecars are missing** rather than silently reporting from summaries alone. Metric columns computed inside shards (AP, precision, recall) remain in `raw_metrics.csv` so the gate script does not require sidecars for its numbers; sidecars enable audit.

## 7. Runner-hour ledger

`docs/cin_compute_ledger.csv` **[added]**: one row per dispatch: `phase, workflow_run_id, jobs, wall_hours_max, runner_hours_sum, dispatched_by, date, purpose`. `runner_hours_sum` = sum of job durations from the Actions run (or shard `runtime_seconds`). The cap (12 aggregate runner-hours; task 11 §8) is checked against this ledger before each dispatch; a dispatch that would breach it is not made.

## 8. Actions dispatch (deliverable is the *verified* command, not a guess)

After the runners exist and a smoke config passes, document in `docs/cin_user_guide.md` the exact `gh workflow run sharded_benchmark.yml -f runner_module=mintnet.experiments.cin_baseline -f config=configs/cin_baseline.yaml -f dim1_flag=--cases -f dim1_values=A,B,... -f dim2_flag=--replicate-batches -f dim2_values=dev0,val0,val1` form (input names taken from the workflow at that time), together with how the results were verified. A speculative command is not a deliverable. Never dispatch time-consuming compute locally (repository memory: expensive runs go through sharded Actions).

## 9. Integration tests (`tests/integration/test_cin_runners.py`)

Use the smoke configs (tiny p, tiny replicates, N small) so each test finishes in seconds:

1. **Expected combinations**: `expected_combinations`/`expected_row_count` match the raw rows of a full smoke run; `COMBINATION_COLUMNS` present.
2. **Sharded == unsharded**: run the smoke grid whole, and as every single-cell shard; concatenated raw metrics equal the unsharded ones after dropping timing columns (`elapsed_seconds`, `peak_rss_mb`, phase timings).
3. **Deterministic seeds**: seed table is a pure function of the full-grid indices and independent of the selected subset; development and validation ranges disjoint.
4. **Aggregator compatibility**: run `scripts/aggregate_shards.py` (import function `aggregate`) over shard outputs: passes when complete, exits when a shard is missing or duplicated.
5. **Duplicate detection** on `(case, phase, method, replicate)`.
6. **Incremental rows**: kill the runner (simulated exception after k datasets) and verify raw rows for completed datasets exist on disk and include failure rows for failed ones.
7. **Sidecars**: manifests complete; row counts and hashes verified; a deleted or altered sidecar makes `aggregate_cin_sidecars.py` fail; pair sidecars for a smoke dataset have `p(p−1)/2` rows and reload equal to `NetworkFit.pairs`.
8. **Failure rows**: comparator failure is recorded as a failure row, **not** as a correct empty graph; counts behind every mean appear in the report input.
9. **Report smoke**: `write_report` produces the report from smoke raw data (and errors clearly when required sidecars are absent).
10. **Thread limits recorded** in `metadata.json`.

Commands:

```bash
python -m pytest tests/integration/test_cin_runners.py
python -m mintnet.experiments.cin_cost --config configs/cin_cost_smoke.yaml --output results/generated/cin_cost_smoke
python -m mintnet.experiments.cin_baseline --config configs/cin_baseline_smoke.yaml --output results/generated/cin_baseline_smoke
```

The two smoke commands are correctness checks only; their timings are not evidence.

## 10. Acceptance

Integration suite green; a full smoke sharded run aggregates through the unmodified generic aggregator plus the sidecar wrapper; `resolved_config.yaml` identical across shards; ledger file created with the header.

## 11. Pitfalls

- `os.cpu_count()`-based default worker counts in `stage5a` can serialize tasks on 2-vCPU runners; for CIN, each shard should be one cell and run serially with `--workers 1` (BLAS = 1 thread); shard every varying dimension instead.
- Seeds from the shard's subset index (rather than the full grid) silently breaks sharded/unsharded equivalence — test 2 is the guard.
- Windows local runs: `resource.getrusage` unavailable; peak RSS is recorded only on Linux runners.
