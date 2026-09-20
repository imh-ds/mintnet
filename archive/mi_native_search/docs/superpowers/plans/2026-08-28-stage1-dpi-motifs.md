# Stage 1 DPI Motif Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate tolerant DPI on Gaussian chains, measured forks, and genuine triangles using the existing KSG estimator.

**Architecture:** Add focused motif DGP, DPI, and topology modules, then compose them in a deterministic Stage 1 runner. The runner owns raw evidence; the reporting module owns aggregate metrics and the frozen development/validation decision.

**Tech Stack:** Python 3.11, NumPy, SciPy, pandas, PyYAML, matplotlib, pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-stage1-dpi-motifs-design.md`

## Global Constraints

- Run the real `KSG -> DPI` pipeline; analytic covariance is fixture validation only.
- Use exactly the motif parameters, seed `20260829`, tau grid, partitions, and gate in the Stage 1 spec.
- Preserve strict DPI inequality: equality does not prune.
- Do not add Stage 2+ layers or a public network API.
- Generated evidence remains under ignored `results/generated/`.

---

### Task 1: Gaussian motif fixtures

**Files:**
- Create: `src/mintnet/simulation/motifs.py`
- Modify: `src/mintnet/simulation/__init__.py`
- Test: `tests/unit/test_motifs.py`

**Interfaces:**
- Produces `sample_chain(n: int, strength: float, rng: Generator) -> ndarray`.
- Produces `sample_measured_fork(n: int, strength: float, rng: Generator) -> ndarray`.
- Produces `sample_precision_triangle(name: str, n: int, rng: Generator) -> ndarray` and `triangle_precisions() -> dict[str, ndarray]`.

- [ ] **Step 1: Write failing DGP truth tests**

```python
def test_chain_endpoint_correlation_is_weaker_than_adjacent_links():
    data = sample_chain(100_000, 0.7, np.random.default_rng(1))
    corr = np.corrcoef(data.T)
    assert corr[0, 2] < corr[0, 1]
    assert corr[0, 2] < corr[1, 2]

def test_triangle_precisions_are_positive_definite():
    for precision in triangle_precisions().values():
        np.linalg.cholesky(precision)
        assert np.all(np.abs(precision[np.triu_indices(3, 1)]) > 0)
```

- [ ] **Step 2: Run the test and confirm it fails because `motifs` is absent**

Run: `.venv\\Scripts\\python.exe -m pytest tests/unit/test_motifs.py -q`

- [ ] **Step 3: Implement unit-variance chain/fork equations and named precision fixtures**

```python
def sample_chain(n, strength, rng):
    x1 = rng.normal(size=n)
    x2 = strength * x1 + np.sqrt(1 - strength**2) * rng.normal(size=n)
    x3 = strength * x2 + np.sqrt(1 - strength**2) * rng.normal(size=n)
    return np.column_stack((x1, x2, x3))
```

Validate `0 < strength < 1`, validate `n >= 1`, Cholesky-check each named precision matrix, sample covariance inverse, and standardize columns with `ddof=1`.

- [ ] **Step 4: Run the motif suite and commit**

Run: `.venv\\Scripts\\python.exe -m pytest tests/unit/test_motifs.py -q`

Commit: `git commit -am "feat: add Gaussian Stage 1 motifs"`

### Task 2: Strict tolerant-DPI pruning

**Files:**
- Create: `src/mintnet/dpi/__init__.py`, `src/mintnet/dpi/prune.py`
- Test: `tests/unit/test_dpi.py`

**Interfaces:**
- Produces `prune_tolerant_dpi(mi_matrix: ndarray, tau: float) -> ndarray`.
- The return value is a symmetric boolean adjacency matrix with a false diagonal.

- [ ] **Step 1: Write failing boundary and permutation tests**

```python
def test_dpi_prunes_only_when_weakest_edge_is_strictly_below_threshold():
    mi = np.array([[0, .9, .7], [.9, 0, .8], [.7, .8, 0.]])
    assert not prune_tolerant_dpi(mi, .20)[0, 2]
    equal = np.array([[0, .9, .72], [.9, 0, .8], [.72, .8, 0.]])
    assert prune_tolerant_dpi(equal, .20)[0, 2]
```

- [ ] **Step 2: Run the test and confirm import failure**

Run: `.venv\\Scripts\\python.exe -m pytest tests/unit/test_dpi.py -q`

- [ ] **Step 3: Implement complete-graph initialization and triangle pruning**

Validate a finite square symmetric matrix with a zero diagonal and `0 <= tau < 1`. For each three-node combination, identify the unique weakest edge; skip exact weakest-MI ties; apply `weak < (1 - tau) * min(stronger)`; return the resulting adjacency.

- [ ] **Step 4: Run the DPI suite and commit**

Run: `.venv\\Scripts\\python.exe -m pytest tests/unit/test_dpi.py -q`

Commit: `git commit -am "feat: add tolerant DPI pruning"`

### Task 3: Motif scoring and pairwise MI matrix

**Files:**
- Create: `src/mintnet/metrics/topology.py`, `src/mintnet/metrics/__init__.py`
- Create: `src/mintnet/mi/matrix.py`
- Test: `tests/unit/test_topology.py`, `tests/unit/test_mi_matrix.py`

**Interfaces:**
- Produces `estimate_pairwise_mi(data: ndarray, k: int) -> ndarray`.
- Produces `score_motif(adjacency: ndarray, motif: Literal['chain','fork','triangle']) -> dict[str, float]`.

- [ ] **Step 1: Write failing tests for MI symmetry/diagonal and topology outcomes**

```python
def test_triangle_score_counts_any_pruned_true_edge():
    adjacency = np.array([[False, True, False], [True, False, True], [False, True, False]])
    assert score_motif(adjacency, "triangle")["true_edge_prune_fpr"] == 1 / 3
```

- [ ] **Step 2: Run the two unit suites and confirm imports fail**

Run: `.venv\\Scripts\\python.exe -m pytest tests/unit/test_topology.py tests/unit/test_mi_matrix.py -q`

- [ ] **Step 3: Implement pairwise KSG calls and explicit motif scoring**

For three columns, call `estimate_ksg_mi` for each unordered pair, mirror values, and leave the diagonal at zero. Chain/fork scoring returns `indirect_prune_tpr`, `true_edge_prune_fpr`, and `perfect_recovery`; triangle scoring returns the same keys with indirect TPR as `nan`.

- [ ] **Step 4: Run all unit tests and commit**

Run: `.venv\\Scripts\\python.exe -m pytest tests/unit -q`

Commit: `git commit -am "feat: add Stage 1 MI and topology metrics"`

### Task 4: Frozen configuration and deterministic Stage 1 runner

**Files:**
- Create: `configs/stage1_dpi.yaml`, `configs/stage1_dpi_smoke.yaml`, `docs/stage1_charter.md`
- Create: `src/mintnet/experiments/stage1.py`
- Test: `tests/integration/test_stage1_runner.py`

**Interfaces:**
- Produces `Stage1Config`, `load_stage1_config(path: Path)`, and `run_stage1(config, output_dir) -> DataFrame`.
- CLI: `python -m mintnet.experiments.stage1 --config <yaml> --output <directory>`.

- [ ] **Step 1: Write an end-to-end failing smoke test**

```python
def test_stage1_smoke_runner_is_deterministic(tmp_path):
    config = load_stage1_config(Path("configs/stage1_dpi_smoke.yaml"))
    first = run_stage1(config, tmp_path / "first")
    second = run_stage1(config, tmp_path / "second")
    assert len(first) == 3 * 1 * 1 * 2 * len(config.taus)
    pd.testing.assert_frame_equal(first.drop(columns="elapsed_seconds"), second.drop(columns="elapsed_seconds"))
```

- [ ] **Step 2: Run it and confirm import failure**

Run: `.venv\\Scripts\\python.exe -m pytest tests/integration/test_stage1_runner.py -q`

- [ ] **Step 3: Implement config, deterministic seeds, raw rows, and metadata**

Use `SeedSequence([master_seed, motif_index, sample_index, strength_index, replicate])`. For every replicate and tau, save motif, family/strength, N, k, tau, seed, all topology metrics, runtime, status, and error text. Persist raw CSV, resolved YAML, Stage 1 charter SHA-256, git commit, and runtime metadata.

- [ ] **Step 4: Run smoke CLI and commit**

Run: `.venv\\Scripts\\python.exe -m mintnet.experiments.stage1 --config configs/stage1_dpi_smoke.yaml --output results/generated/stage1_dpi_smoke`

Commit: `git commit -am "feat: add deterministic Stage 1 runner"`

### Task 5: Gate reporting and R2 documentation

**Files:**
- Create: `src/mintnet/experiments/stage1_reporting.py`, `docs/stage1_report.md`
- Modify: `src/mintnet/experiments/stage1.py`
- Test: `tests/integration/test_stage1_reporting.py`

**Interfaces:**
- Produces `select_tau_pair(raw, config) -> tuple[float, float] | None`.
- Produces `evaluate_stage1_gate(raw, config) -> GateDecision` and `write_stage1_report(raw, config, output_dir) -> GateDecision`.

- [ ] **Step 1: Write failing gate-fixture tests**

```python
def test_gate_requires_the_development_pair_to_pass_each_validation_cell():
    decision = evaluate_stage1_gate(passing_raw_with_one_failed_fork_cell(), config)
    assert decision.status == "REASSESS"
    assert "fork indirect-edge TPR" in decision.failures
```

- [ ] **Step 2: Run reporting tests and confirm import failure**

Run: `.venv\\Scripts\\python.exe -m pytest tests/integration/test_stage1_reporting.py -q`

- [ ] **Step 3: Implement pooled selection, cell-level validation, and figures**

Select the lexicographically lowest adjacent development tau pair satisfying pooled TPR/FPR criteria. Validate that fixed pair separately by N and strength. Treat any error, missing cell, missing pair, or failed metric as `REASSESS`. Emit `aggregate_metrics.csv`, `decision.json`, `stage1_report.md`, `dpi_operating_curve.png`, `performance_vs_tau.png`, and `runtime_vs_n.png`.

- [ ] **Step 4: Run all tests, full frozen experiment, and commit the R2 result**

Run tests: `.venv\\Scripts\\python.exe -m pytest -q`

Run experiment: `.venv\\Scripts\\python.exe -m mintnet.experiments.stage1 --config configs/stage1_dpi.yaml --output results/generated/stage1_dpi`

Verify expected rows: `3 motifs * 6 N * 3 strengths * 500 replicates * 9 taus = 243,000`; inspect `decision.json`; update `docs/stage1_report.md` and `docs/decision_log.md` without editing the charter; commit `docs: record Stage 1 DPI decision`.

## Self-review

- The plan maps DGP truth, strict pruning, metrics, reproducible execution, and the R2 gate to separate tested tasks.
- The selected interfaces are consistent: the runner creates raw rows, and reporting consumes exactly those rows.
- The only allowed next-stage transition is determined by the frozen R2 decision; no Stage 2 implementation appears here.
