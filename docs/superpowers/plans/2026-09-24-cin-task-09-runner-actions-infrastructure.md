# CIN Task 09 Runner and Actions Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic, shardable cost-pilot and statistical-panel runners that emit incrementally flushed raw evidence, auditable pair/stability sidecars, complete provenance, and reports compatible with the repository's existing generic Actions workflow.

**Architecture:** A small `cin_common` module owns full-grid seed derivation, thread limits, provenance, incremental CSV writing, resource measurements, and shared fit/metric serialization. `cin_cost` and `cin_baseline` each own a frozen YAML dataclass, shard selectors, method execution, and runner-specific raw columns; companion reporting modules consume complete aggregated output. A separate sidecar aggregator validates and combines files because `scripts/aggregate_shards.py` intentionally handles only `raw_metrics.csv`.

**Tech Stack:** Python 3.11, frozen dataclasses, NumPy `SeedSequence`, pandas, PyYAML, scikit-learn's existing EBICglasso comparator, `threadpoolctl`, gzip CSV sidecars, and the existing `sharded_benchmark.yml` / `aggregate_shards.py` contracts.

**Spec:** `docs/design/cin/build-plan/09_runner_actions_infrastructure.md`, with cost cells from `docs/design/cin/build-plan/10_cost_pilot.md` and panel method/metric availability from `docs/design/cin/build-plan/11_statistical_panel.md`.

## Global Constraints

- Preserve the generic `.github/workflows/sharded_benchmark.yml` and `scripts/aggregate_shards.py` interfaces unless a focused test proves a shared change is required; the active workflow already uploads each shard's complete output directory.
- Use the repository requirement `requires-python = ">=3.11,<3.12"` and add `threadpoolctl` as an explicit runtime dependency because the runners must record and enforce BLAS limits.
- Set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and `NUMEXPR_NUM_THREADS` to `1` in the workflow and before NumPy import in runner modules; also wrap every fit in `threadpool_limits(1)`.
- Derive every seed from the full unfiltered grid with `SeedSequence([master_seed, 9009, case_idx, phase_idx, replicate])`; never derive a seed from a shard-local position.
- Development replicate ids are `[0, 10)` and validation replicate ids are `[1000, 1020)`; these ranges are configuration data and are never reused across phases.
- Flush one raw row immediately after each completed method/dataset, including a failure row; never retain the entire raw run only in memory.
- A failed comparator is recorded as `status="error"` with `error_type` and `error`; it is never represented as a successful empty graph.
- Metadata may contain provenance and diagnostics but never participant-level observations; pair and stability tables are written as separate sidecars.
- Cost inputs are stress inputs without truth and never receive recovery metrics; panel cases use Task 08's observed-variable truth contract.
- Do not dispatch expensive GitHub Actions jobs or claim timing evidence locally; local smoke runs validate correctness only.
- Do not modify archived files under `archive/mi_native_search/`; read them as historical references only.

## Review Focus

- **Shard-local seed drift:** a one-cell runner must produce the same non-timing rows as the matching rows of a full run; pin this in the panel and cost sharding tests.
- **Partial-run loss:** a raised exception after completed work must leave flushed rows and an explicit failure row on disk; pin this with an injected dataset failure.
- **Sidecar integrity:** missing, altered, duplicated, or orphaned sidecars must fail aggregation before reporting; pin each condition in the sidecar integration tests.
- **Comparator failure semantics:** a failed EBICglasso fit must remain a failure with unavailable metrics and no sidecar, never a valid zero-edge result; pin this by monkeypatching the comparator.
- **Provenance/thread reproducibility:** full-grid resolved config, code/config/charter hashes, thread settings, and resource fields must survive shard aggregation; pin metadata equality and thread-limit fields in smoke tests.

---

### Task 1: Define shared runner contracts, seed bundles, provenance, and smoke configurations

**Files:**

- Create: `src/mintnet/experiments/cin_common.py`
- Modify: `pyproject.toml`
- Create: `configs/cin_cost.yaml`
- Create: `configs/cin_cost_smoke.yaml`
- Create: `configs/cin_baseline.yaml`
- Create: `configs/cin_baseline_smoke.yaml`
- Create: `tests/integration/test_cin_runners.py`

**Interfaces:**

- `CINSeedBundle`: frozen dataclass with `structure`, `sample`, `cin_fit`, `comparator_fit`, and `stability` integer fields.
- `derive_seed_bundle(master_seed: int, case_index: int, phase_index: int, replicate: int) -> CINSeedBundle`.
- `IncrementalCsvWriter(path: Path, columns: tuple[str, ...])` with `append(row: Mapping[str, Any])`, `flush()`, and `close()`; `append` writes the header once and flushes after every row.
- `thread_limits() -> contextlib.AbstractContextManager` wrapping `threadpoolctl.threadpool_limits(limits=1)`.
- `write_provenance(output_dir: Path, *, config_payload: Mapping[str, Any], source_path: Path, charter_path: Path | None, runtime_seconds: float, peak_rss_mb: float | None) -> None`.
- `write_resolved_config(output_dir: Path, config_payload: Mapping[str, Any]) -> str`, returning the SHA-256 of the exact written YAML bytes.
- `canonical_pair_sidecar_name(case: str, phase: str, replicate: int, method: str, kind: str = "pairs") -> str`.

The full seed implementation is fixed before any runner code:

```python
def derive_seed_bundle(master_seed, case_index, phase_index, replicate):
    root = np.random.SeedSequence(
        [int(master_seed), 9009, int(case_index), int(phase_index), int(replicate)]
    )
    children = root.spawn(5)
    values = [int(child.generate_state(1, dtype=np.uint32)[0]) for child in children]
    return CINSeedBundle(*values)
```

Create the exact full cost matrix in `configs/cin_cost.yaml` with
`master_seed: 20260924`: `c_p8_n100`,
`c_p30_n100`, `c_p100_n100`, `c_p100_n300`, `c_p100_n1000`,
`k5_p30_n150`, `k10_p100_n200`, and `mix_p100_n200`, with the dimensions and
input kinds specified in Task 10. Set `repeats: [1, 2]` and record the master
seed. The smoke config retains the same eight ids but substitutes dimensions
no larger than `p=12`, `n=60`, and uses `repeats: [1]`.

Create `configs/cin_baseline.yaml` with `master_seed: 20260924`, cases `A` through `I` plus the
historical `regression` fixture,
`development_replicates: [0, 10]`, `validation_replicates: [1000, 1020]`,
the Task 11 default master seed, `stability_cases: [A, B, F]`,
`stability_repeats: 10`, and `stability_fraction: 0.8`. Create the smoke
config with cases `A` and `F`, two development ids `[0, 2]`, two validation
ids `[1000, 1002]`, `stability_cases: []`, and `n_overrides: {A: 40, F: 40}`
so every smoke dataset has at most eight variables and at most sixty rows.

- [ ] **Step 1: Write failing shared-contract tests.**

Add tests for exact five-child seed derivation, seed independence from selected
shards, disjoint development/validation ranges, incremental header/flush
behavior, canonical sidecar names, YAML hash stability, and metadata fields
including thread settings and a `None` Linux-only RSS value on platforms that
cannot measure it. Include config-loader tests that assert the eight cost ids,
the two phase ranges, and the smoke overrides.

- [ ] **Step 2: Run the shared tests to verify the red state.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py -k "seed or common or config"
```

Expected: collection or import failures because the common module and config
loaders do not yet exist.

- [ ] **Step 3: Implement the shared utilities and explicit dependency.**

Set the four thread environment variables at the top of each executable runner
before importing NumPy; use `threadpoolctl.threadpool_limits(1)` around fits;
record `threadpool_info()`, Python/platform, package versions, BLAS details,
CPU model, runtime, peak RSS, current git revision, config hash, and charter
hash in metadata. Use `resource.getrusage` only on Linux and return `None` on
Windows. Make resolved YAML serialize the full config, never the shard filter.

- [ ] **Step 4: Re-run the shared tests and commit.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py -k "seed or common or config"
ruff check src/mintnet/experiments/cin_common.py tests/integration/test_cin_runners.py
```

Commit:

```text
git add pyproject.toml src/mintnet/experiments/cin_common.py configs tests/integration/test_cin_runners.py
git commit -m "feat: add CIN runner contracts and deterministic seed infrastructure"
```

---

### Task 2: Implement the cost-pilot runner and report

**Files:**

- Create: `src/mintnet/experiments/cin_cost.py`
- Create: `src/mintnet/experiments/cin_cost_reporting.py`
- Modify: `tests/integration/test_cin_runners.py`

**Interfaces:**

- `CostCell`: frozen dataclass with `cell_id`, `kind`, `p`, and `n`.
- `CostConfig`: frozen dataclass with `cells`, `repeats`, `master_seed`, and `source_path`.
- `load_config(path: Path) -> CostConfig`.
- `expected_row_count(config: CostConfig) -> int` returning `len(config.cells) * len(config.repeats)`.
- `expected_combinations(config: CostConfig) -> set[tuple[str, int]]` returning every `(cell_id, repeat)` pair in the full config.
- `COMBINATION_COLUMNS = ("cell", "repeat")`.
- `run_cost(config: CostConfig, output_dir: Path, *, cells: tuple[str, ...] | None = None, repeats: tuple[int, ...] | None = None, workers: int = 1, write_report: bool = True) -> pd.DataFrame`.
- CLI: `python -m mintnet.experiments.cin_cost --config ... --output ... [--cells id1,id2] [--repeat 1] [--workers 1] [--no-report]`.
- `cin_cost_reporting.write_report(raw: pd.DataFrame, config: CostConfig, output_dir: Path) -> None`.

The raw schema is fixed and includes:

```python
COST_RAW_COLUMNS = (
    "cell", "repeat", "kind", "p", "n", "status", "error_type", "error",
    "structure_seed", "sample_seed", "cin_fit_seed", "elapsed_seconds",
    "prepare_seconds", "features_seconds", "gram_factor_seconds", "h_seconds",
    "omission_seconds", "score_seconds", "aggregate_seconds", "outputs_seconds",
    "n_large_factorizations", "q", "t", "n_fallbacks", "fallback_fraction",
    "n_pairs_complete", "n_pairs_total", "peak_rss_mb", "pair_sidecar_file",
)
```

- [ ] **Step 1: Write failing cost-runner tests.**

Test loader validation, full-grid expected combinations, one-cell selection,
`--repeat` selection, one raw row per cell/repeat, default `CINConfig`, cost
input schemas, extraction of fit cost counters, and pair-sidecar row counts.
Assert that a smoke run writes `raw_metrics.csv`, `resolved_config.yaml`,
`metadata.json`, `sidecars/`, and `sidecar_manifest.csv`.

- [ ] **Step 2: Run the cost tests to verify the red state.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py -k "cost"
```

Expected: failures because `cin_cost` and its report module are absent.

- [ ] **Step 3: Implement deterministic cell execution and incremental output.**

Resolve cell indices from the full config before filtering. For each selected
cell/repeat, derive its seed bundle using `case_index = full cell index`,
`phase_index = 0`, and `replicate = repeat`; generate the Task 08 cost input
with `sample`, fit with `CINConfig(seed=cin_fit)`, and execute under one BLAS
thread. Extract `metadata["cost"]`, completion counts, fallback fraction,
phase seconds, q/t, and peak RSS. Write the fit's complete pair table as
`sidecars/<cell>_<repeat>_cin_pairs.csv.gz`, append its manifest row with byte
hash and row count, then append and flush the raw row. On any exception, append
the same identity row with `status="error"`, the exception type/message, NaN
metrics, and no sidecar path.

- [ ] **Step 4: Implement the cost report and CLI.**

`write_report` must produce `cost_summary.csv` and `cost_report.md`, with one
row per cell/repeat, phase timings, factor counts, RSS, completion, fallback
fraction, and the exact gate labels from Task 10. It must state that smoke
timings are correctness-only and must not emit recovery metrics. `--no-report`
must skip report creation for a partial shard while still writing raw evidence,
resolved config, metadata, and sidecars.

- [ ] **Step 5: Run the cost smoke command and commit.**

Run:

```text
python -m mintnet.experiments.cin_cost --config configs/cin_cost_smoke.yaml --output results/generated/cin_cost_smoke
python -m pytest tests/integration/test_cin_runners.py -k "cost"
ruff check src/mintnet/experiments/cin_cost.py src/mintnet/experiments/cin_cost_reporting.py tests/integration/test_cin_runners.py
```

Commit:

```text
git add src/mintnet/experiments/cin_cost.py src/mintnet/experiments/cin_cost_reporting.py tests/integration/test_cin_runners.py
git commit -m "feat: add shardable CIN cost runner"
```

---

### Task 3: Implement the statistical-panel runner and exact method matrix

**Files:**

- Create: `src/mintnet/experiments/cin_baseline.py`
- Modify: `src/mintnet/experiments/cin_common.py`
- Modify: `tests/integration/test_cin_runners.py`

**Interfaces:**

- `PanelConfig`: frozen dataclass with `cases`, `master_seed`, `development_replicates`, `validation_replicates`, `n_overrides`, `stability_cases`, `stability_repeats`, `stability_fraction`, and `source_path`.
- `load_config(path: Path) -> PanelConfig`.
- `expected_row_count(config: PanelConfig) -> int`.
- `expected_combinations(config: PanelConfig) -> set[tuple[str, str, str]]`.
- `COMBINATION_COLUMNS = ("case", "phase", "method")`.
- `run_baseline(config: PanelConfig, output_dir: Path, *, cases: tuple[str, ...] | None = None, replicate_batches: tuple[str, ...] | None = None, workers: int = 1, write_report: bool = True) -> pd.DataFrame`.
- CLI: `python -m mintnet.experiments.cin_baseline --config ... --output ... [--cases A,F] [--replicate-batches dev0,val0,val1] [--workers 1] [--no-report]`.
- Methods: `cin` on A–I plus `regression`; `cin_linear` and `ebicglasso` on continuous A–E plus `regression`; F–I receive no unsupported integer-code comparator rows.

The panel raw schema includes the identifiers and seeds plus these exact Task
11 metric fields: `n`, `p`, `status`, `error_type`, `error`,
`elapsed_seconds`, `ap`, `prevalence`, `ap_minus_prevalence`,
`n_pairs_complete`, `n_pairs_total`, `n_failed_pairs`, `strong_edge_recall`,
`oracle_cmi_mae`, `oracle_cmi_bias`, `categorical_excess_loss`,
`positive_weight_q50`, `positive_weight_q90`, `positive_weight_q95`,
`positive_weight_q99`, `positive_weight_max`, `tie_fraction`, and for each
delta token in `0`, `005`, `01`, and `02`,
`delta_<token>_displayed_count`, `delta_<token>_displayed_fraction`,
`delta_<token>_precision`, `delta_<token>_recall`, and
`delta_<token>_empty`. Agreement-filtered variants use the same fields with
the `agreement_` prefix. The row ends with `pair_sidecar_file` and
`stability_sidecar_file`. All metric fields are NaN when a method fails;
failure counts remain explicit.

- [ ] **Step 1: Write failing panel contract and seed tests.**

Test the exact method availability matrix, row count over both phase ranges,
`COMBINATION_COLUMNS`, case-index/phase-index seed derivation, full-grid batch
selection (`dev0`, `val0`, `val1`), and rejection of unsupported cases or
overrides. Assert that `cin_linear` is `max_curvature_rank=0` and EBICglasso
is never called for categorical/mixed cases.

- [ ] **Step 2: Run the panel contract tests to verify the red state.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py -k "panel or expected_combinations or method_matrix"
```

Expected: failures because the baseline runner and panel config are absent.

- [ ] **Step 3: Implement full-grid phase and batch resolution.**

Map `dev0` to development ids `[0, 10)`, `val0` to validation ids `[1000,
1010)`, and `val1` to validation ids `[1010, 1020)`. For each selected case,
phase, and replicate, derive seeds with the original full case index and
phase index (`0` development, `1` validation). Generate one frame/schema per
dataset and pass that exact frame to every applicable method.

- [ ] **Step 4: Implement method execution and metric/sidecar rows.**

Use the full case registry `("A", "B", "C", "D", "E", "F", "G", "H", "I", "regression")` for case indices. Run `fit_network` with the default Task 11 config for `cin`, and with
`dataclasses.replace(config, max_curvature_rank=0)` for `cin_linear`. Run
`fit_ebicglasso` only for A–E on the same continuous frame, audit its
convergence/exception result, and emit a failure row on any failure. Serialize
every successful `NetworkFit.pairs` table to a gzip sidecar and compute the
raw ranking/display metrics against the Task 08 truth. For configured A/B/F
stability datasets, call `estimate_stability` with the point fit and original
frame, then write its records as a second gzip sidecar. Append each method row
immediately after its sidecars are complete; the dataset is not regenerated
between methods.

- [ ] **Step 5: Run panel smoke tests and commit.**

Run:

```text
python -m mintnet.experiments.cin_baseline --config configs/cin_baseline_smoke.yaml --output results/generated/cin_baseline_smoke
python -m pytest tests/integration/test_cin_runners.py -k "panel or expected_combinations or method_matrix"
ruff check src/mintnet/experiments/cin_baseline.py src/mintnet/experiments/cin_common.py tests/integration/test_cin_runners.py
```

Commit:

```text
git add src/mintnet/experiments/cin_baseline.py src/mintnet/experiments/cin_common.py configs/cin_baseline*.yaml tests/integration/test_cin_runners.py
git commit -m "feat: add shardable CIN statistical panel runner"
```

---

### Task 4: Add runner-specific reports and sidecar validation/aggregation

**Files:**

- Create: `scripts/aggregate_cin_sidecars.py`
- Create: `src/mintnet/experiments/cin_baseline_reporting.py`
- Modify: `src/mintnet/experiments/cin_cost_reporting.py`
- Modify: `tests/integration/test_cin_runners.py`

**Interfaces:**

- `aggregate_sidecars(shards_dir: Path, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]`.
- CLI: `python scripts/aggregate_cin_sidecars.py --shards-dir D --output O`.
- `cin_baseline_reporting.write_report(raw: pd.DataFrame, config: PanelConfig, output_dir: Path) -> None`.
- `cin_cost_reporting.write_report(raw: pd.DataFrame, config: CostConfig, output_dir: Path) -> None`.

- [ ] **Step 1: Write failing sidecar/report tests.**

Build a complete smoke shard directory and assert that sidecar aggregation
creates `pairs_all.csv.gz`, `stability_all.csv.gz` when stability exists, and
`sidecar_manifest.csv`. Test pair row count `p*(p-1)//2`, stability row count
`B*p*(p-1)//2`, duplicate manifest keys, missing files, altered hashes,
orphan files, raw rows promising a missing sidecar, and an absent sidecar in a
report input. Every invalid case must raise a message naming the offending
identity or file.

- [ ] **Step 2: Run the sidecar/report tests to verify the red state.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py -k "sidecar or report"
```

Expected: failures because the sidecar script and baseline report are absent.

- [ ] **Step 3: Implement manifest validation and combined tables.**

Read the aggregated `output/raw_metrics.csv` when present; otherwise read all
shard raw files. For each manifest entry, resolve the path relative to its
shard, verify SHA-256 and declared row count, and match exactly one raw identity
and declared kind. Reject duplicate identities and every file under a shard's
`sidecars/` directory that is not listed. Concatenate pair tables into
`output/sidecars/pairs_all.csv.gz` and stability tables into
`output/sidecars/stability_all.csv.gz`, preserving identity columns and writing
a combined manifest. Do not edit the generic aggregator or its workflow.

- [ ] **Step 4: Implement reports that require audit sidecars.**

The baseline report must load combined pair sidecars when any successful panel
row promises one, fail clearly if they are missing, and write a JSON/Markdown
summary with method/case/phase counts, complete-pair counts, AP and display
metrics, failures, and stability availability. The cost report writes the
Task 10 cost table and gate labels without truth or recovery language. Both
reports must preserve counts behind every mean.

- [ ] **Step 5: Run aggregator/report tests and commit.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py -k "sidecar or report"
python scripts/aggregate_cin_sidecars.py --shards-dir results/generated/cin_baseline_shards --output results/generated/cin_baseline_aggregated
ruff check scripts/aggregate_cin_sidecars.py src/mintnet/experiments/cin_*_reporting.py tests/integration/test_cin_runners.py
```

Commit:

```text
git add scripts/aggregate_cin_sidecars.py src/mintnet/experiments/cin_*_reporting.py tests/integration/test_cin_runners.py
git commit -m "feat: add CIN sidecar aggregation and evidence reports"
```

---

### Task 5: Prove shard equivalence, incremental failure behavior, and generic aggregation compatibility

**Files:**

- Modify: `tests/integration/test_cin_runners.py`
- Modify: `src/mintnet/experiments/cin_cost.py`
- Modify: `src/mintnet/experiments/cin_baseline.py`

- [ ] **Step 1: Test unsharded versus every single-cell cost shard.**

Run the eight-cell smoke grid once, run each cell/repeat as a separate shard,
aggregate all raw rows through `scripts.aggregate_shards.aggregate`, and
compare sorted frames after dropping only timing/resource columns. Assert
resolved YAML bytes are identical across all shards and expected combinations
are complete exactly once.

- [ ] **Step 2: Test unsharded versus panel case/batch shards.**

Run the complete A/F smoke grid, then every case × `dev0`, `val0`, and `val1`
selection separately. Aggregate with the unchanged generic aggregator and
sidecar wrapper; compare all non-timing raw columns and the combined pair table
against the unsharded run. Assert no development id occurs in validation and
that the same dataset seeds feed `cin` and `cin_linear`/EBICglasso rows.

- [ ] **Step 3: Test duplicate/missing coverage and failure rows.**

Delete one shard and assert generic aggregation exits for incomplete row count;
duplicate one shard and assert duplicate-key failure; inject a comparator
exception and assert an error row with no pair sidecar; inject a dataset
exception after at least one completed method and assert flushed prior rows,
the failure row, and a still-valid `raw_metrics.csv`.

- [ ] **Step 4: Test thread and provenance fields.**

Load every smoke `metadata.json` and assert the four environment variables are
recorded as `1`, `threadpool_info` is present, config hashes match the exact
resolved YAML, git revision is present, and Windows RSS is either numeric or
explicitly `null`. Verify aggregated metadata preserves invariant fields and
sums shard runtimes.

- [ ] **Step 5: Run the complete integration suite and commit.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py
ruff check src/mintnet/experiments scripts/aggregate_cin_sidecars.py tests/integration/test_cin_runners.py
git diff --check
```

Commit:

```text
git add src/mintnet/experiments/cin_cost.py src/mintnet/experiments/cin_baseline.py tests/integration/test_cin_runners.py
git commit -m "test: verify CIN runner sharding and failure durability"
```

---

### Task 6: Create the compute ledger and document the verified Actions command

**Files:**

- Create: `docs/cin_compute_ledger.csv`
- Create: `docs/cin_user_guide.md`
- Modify: `tests/integration/test_cin_runners.py`

- [ ] **Step 1: Write documentation/ledger tests.**

Assert the ledger has exactly this header and no dispatch rows before any
expensive run:

```text
phase,workflow_run_id,jobs,wall_hours_max,runner_hours_sum,dispatched_by,date,purpose
```

Assert the user guide contains the exact verified baseline dispatch command,
the cost dispatch command, the generic aggregation command, and the sidecar
aggregation command, with `--workers 1` and the full-grid shard axes.

- [ ] **Step 2: Verify the active workflow inputs without dispatching.**

Read `.github/workflows/sharded_benchmark.yml` and document this exact command
shape, using the runner module/config paths and values accepted by the smoke
tests:

```text
gh workflow run sharded_benchmark.yml \
  -f runner_module=mintnet.experiments.cin_baseline \
  -f config=configs/cin_baseline.yaml \
  -f dim1_flag=--cases -f dim1_values=A,B,C,D,E,F,G,H,I,regression \
  -f dim2_flag=--replicate-batches -f dim2_values=dev0,val0,val1
```

Also document the cost form with `dim1_flag=--cells`, the eight full cell ids,
and `dim2_flag=--repeat -f dim2_values=1,2`. State that the command has been
verified against the workflow inputs and that dispatch is deliberately not
performed by local correctness work.

- [ ] **Step 3: Add the ledger header and reproducibility guide.**

The guide must explain that smoke outputs are correctness-only, how to run the
two local smoke commands, where `raw_metrics.csv`, sidecars, resolved config,
metadata, and reports are found, and how to run both aggregators. It must
document seed ranges, `CINSeedBundle` fields, one-thread policy, failure-row
semantics, and the 12 runner-hour cap.

- [ ] **Step 4: Run documentation tests and commit.**

Run:

```text
python -m pytest tests/integration/test_cin_runners.py -k "ledger or workflow or guide"
git diff --check
```

Commit:

```text
git add docs/cin_compute_ledger.csv docs/cin_user_guide.md tests/integration/test_cin_runners.py
git commit -m "docs: document CIN runner dispatch and compute ledger"
```

---

## Completion Checklist

- [ ] `cin_cost` and `cin_baseline` expose the generic shard contract and frozen config loaders.
- [ ] Full-grid seed derivation is identical between unsharded and single-cell shard runs.
- [ ] Raw rows flush after every method/dataset, including explicit failure rows.
- [ ] Cost and panel sidecars have manifests, hashes, row counts, and deterministic names.
- [ ] Sidecar aggregation rejects missing, altered, duplicate, and orphan files.
- [ ] Reports require sidecars where audit metrics require them and preserve counts behind means.
- [ ] Metadata includes config/charter/code hashes, environment, BLAS/thread settings, runtime, and RSS semantics.
- [ ] Smoke configs run locally in seconds and produce no publication/evidence claim.
- [ ] The existing generic workflow and raw aggregator remain unchanged unless a focused compatibility test proves otherwise.
- [ ] The compute ledger header exists before dispatch and no local command dispatches expensive Actions work.
- [ ] `python -m pytest tests/integration/test_cin_runners.py`, Ruff, and `git diff --check` are green.
