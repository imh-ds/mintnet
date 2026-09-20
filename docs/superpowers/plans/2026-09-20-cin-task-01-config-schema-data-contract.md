# CIN Task 01 — Configuration, Schema, and Data Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the validated, immutable input boundary that every later CIN estimator component consumes.

**Architecture:** Put `CINConfig`, schema parsing, data preparation, diagnostics, and digest helpers in one focused `mintnet.cin.config` module. Keep the public `mintnet.cin` package import-light: expose the configuration entry point and explicit `NotImplementedError` stubs for future fitting/view APIs without importing scikit-learn or matplotlib.

**Tech Stack:** Python 3.11, frozen dataclasses, NumPy, pandas, SHA-256, pytest.

**Spec:** `docs/design/cin/build-plan/01_config_schema_data_contract.md`, governed by `docs/design/cin/methodology/technical_implementation_roadmap_2026-09-19.md` §§3–4.

## Global Constraints

- New numerical code lives under `src/mintnet/cin`; do not reactivate or modify archived methodology.
- `CINConfig`, `VariableSpec`, `PreparedData`, and `DataDiagnostics` are frozen dataclasses.
- All retained data arrays are NumPy `float64`/`int16` arrays, C-contiguous, and marked read-only before returning.
- Schema order is the canonical node and array order; no set iteration may determine output order.
- Missing declared values are either rejected or removed once by global complete-case filtering; never use pairwise deletion or imputation.
- Categories are declared explicitly; never infer or add levels from observed data or evaluation data.
- Configuration defaults are initial engineering settings, not empirical guarantees.
- `config_hash()` excludes only `pair_batch_size` and `max_seconds`; those fields are recorded separately by later metadata code.
- The Task 01 acceptance suite must not import scikit-learn or matplotlib through `mintnet.cin`.

## Review Focus

- Nullable/object columns: `pd.NA`, `None`, and nullable categorical values must be audited before conversion rather than silently coded as categories.
- Boolean continuous inputs: a boolean column declared continuous must fail and require an explicit categorical declaration.
- Numeric category identity: `1.0` and `1` match, while `True` and `1` remain distinct.
- Training-independent input identity: frame-column order may change without changing the digest, while a cell or retained index label change must change the relevant digest.
- Structural degeneracy: constant variables fail at the global preparation boundary, while rare/absent declared categorical levels are recorded diagnostically rather than inferred away.

---

### Task 1: Add the configuration and data-contract test scaffold

**Files:**
- Create: `tests/unit/cin/test_config.py`
- Create: `tests/unit/cin/` directory; do not add `__init__.py`, matching the existing `tests/unit` layout.

**Interfaces:**
- Consumes: the public signatures specified below; the first run is expected to fail because `mintnet.cin` does not yet exist.
- Produces: focused tests that define the contract before implementation.

- [ ] **Step 1: Add reusable test fixtures and helpers.**

Use a 30-row `DataFrame` so the default `min_rows=30` is satisfied, with schema order intentionally different from frame-column order. Include one continuous column, one categorical column with declared levels `[1, 2, 3]`, and an extra ignored column. Add helpers for a valid schema and for constructing a frame with a unique `RangeIndex`.

The valid-schema helper should return exactly:

```python
{
    "stress": {"kind": "continuous"},
    "sleep_item": {"kind": "categorical", "levels": [1, 2, 3], "ordered": True},
}
```

- [ ] **Step 2: Write configuration and package-surface tests.**

Add tests named `test_config_defaults_are_stable`, `test_config_rejects_invalid_values`, `test_config_hash_ignores_only_batch_and_timing`, and `test_public_import_is_lightweight`. Assert the roadmap defaults exactly, reject negative seeds, invalid missingness, nonpositive/nonfinite timing, invalid fold counts, unsorted/nonpositive lambda grids, invalid curvature/probability/range fields, and impossible minimum-row/fold combinations.

For the import-boundary test, use a subprocess so the assertion is made in a fresh interpreter:

```python
code = "import sys; import mintnet.cin; " \
       "assert 'sklearn' not in sys.modules; " \
       "assert 'matplotlib' not in sys.modules"
subprocess.run([sys.executable, "-c", code], check=True)
```

Also assert that `fit_network`, `estimate_stability`, and `make_view` exist and raise `NotImplementedError` when called, rather than importing unfinished modules.

- [ ] **Step 3: Run the initial tests and confirm the failure is for missing implementation.**

Run:

```text
python -m pytest tests/unit/cin/test_config.py -q
```

Expected: collection fails because the new `mintnet.cin` package and configuration symbols do not exist. Do not change existing active tests to make this expected failure pass.

### Task 2: Implement `CINConfig` and the lazy package API

**Files:**
- Create: `src/mintnet/cin/config.py`
- Create: `src/mintnet/cin/__init__.py`
- Test: `tests/unit/cin/test_config.py`

**Interfaces:**
- Consumes: no project-local modules beyond `mintnet` package discovery.
- Produces: `CINConfig`, `CINConfig.config_hash()`, and package-level `CINConfig`, `fit_network`, `estimate_stability`, `make_view`.

- [ ] **Step 1: Add the frozen configuration dataclass with exact fields and defaults.**

Define the fields in this order so the required `seed` precedes defaulted fields:

```python
@dataclass(frozen=True)
class CINConfig:
    seed: int
    missing: str = "error"
    max_seconds: float = 300.0
    outer_folds: int = 3
    inner_folds: int = 2
    lambda_grid: tuple[float, ...] = (0.001, 0.01, 0.1, 1.0, 10.0)
    curvature_multiplier: float = 10.0
    max_curvature_rank: int = 2
    n_knots: int = 5
    spline_degree: int = 3
    probability_mixture: float = 0.01
    count_pseudocount: float = 0.5
    variance_floor: float = 0.0025
    max_expanded_features: int = 1000
    min_rows: int = 30
    max_variables: int = 100
    tie_tolerance: float = 1e-8
    fallback_stop_fraction: float = 0.01
    pair_batch_size: int = 256
```

Normalize `lambda_grid` to a tuple in `__post_init__` using `object.__setattr__` before validation. Reject booleans where an integer is required. Validate: nonnegative integer seed; `missing` in `{"error", "complete_case"}`; finite positive `max_seconds`; folds and integer limits at their documented lower/upper bounds; strictly increasing positive lambdas; positive `curvature_multiplier`, `count_pseudocount`, and `variance_floor`; `0 <= max_curvature_rank <= 2`; `0 < probability_mixture < 1`; `0 <= fallback_stop_fraction <= 1`; and positive `pair_batch_size`.

Require `min_rows >= 2 * outer_folds * inner_folds`. Also compute the roadmap feasibility check using `outer_train = ceil(30 * (outer_folds - 1) / outer_folds)` and `inner_train = outer_train - ceil(outer_train / inner_folds)`; reject configurations where `inner_train < 2`.

- [ ] **Step 2: Implement the stable configuration hash.**

Build a canonical mapping from dataclass fields, omit exactly `pair_batch_size` and `max_seconds`, sort keys, and serialize with compact JSON. Normalize tuples to lists for JSON and use Python’s `repr`-based float serialization; reject nonfinite values during validation so the hash cannot contain `NaN` or infinity. Return `hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()`.

The test must verify that changing each of the two excluded fields preserves the hash and changing every other field changes it. Use `dataclasses.replace` so the test remains independent of implementation internals.

- [ ] **Step 3: Add the lazy package exports and stubs.**

In `src/mintnet/cin/__init__.py`, import only `CINConfig` from `.config`, set `__all__`, and define:

```python
def fit_network(*args, **kwargs):
    raise NotImplementedError("CIN fitting is implemented in a later build task")


def estimate_stability(*args, **kwargs):
    raise NotImplementedError("CIN stability is implemented in a later build task")


def make_view(*args, **kwargs):
    raise NotImplementedError("CIN views are implemented in a later build task")
```

Do not import `features`, `ridge`, `scores`, scikit-learn, or matplotlib from this module.

- [ ] **Step 4: Run the configuration tests.**

Run:

```text
python -m pytest tests/unit/cin/test_config.py -k "config or public_import" -q
```

Expected: all configuration/default/hash/import/stub tests pass.

- [ ] **Step 5: Commit the independently reviewable configuration surface.**

```text
git add src/mintnet/cin tests/unit/cin/test_config.py
git commit -m "feat: add CIN configuration contract"
```

Preserve the pre-existing `.gitignore` modification; do not stage it.

### Task 3: Implement schema parsing and immutable prepared-data types

**Files:**
- Modify: `src/mintnet/cin/config.py`
- Test: `tests/unit/cin/test_config.py`

**Interfaces:**
- Consumes: `CINConfig` from Task 2 and a pandas `DataFrame`.
- Produces:
  - `VariableSpec(name: str, kind: Literal["continuous", "categorical"], levels: tuple[Any, ...] | None, ordered: bool)`
  - `parse_schema(schema: Mapping[str, Mapping[str, Any]]) -> tuple[VariableSpec, ...]`
  - frozen `DataDiagnostics`
  - frozen `PreparedData`

- [ ] **Step 1: Write schema-validation tests.**

Add tests named `test_parse_schema_preserves_insertion_order`, `test_schema_rejects_unknown_or_missing_keys`, `test_schema_rejects_invalid_levels`, `test_schema_rejects_continuous_metadata`, `test_prepare_data_enforces_variable_bounds`, and `test_prepare_data_rejects_duplicate_frame_columns`.

Pin these cases from the specification: unknown key, missing categorical `levels`, duplicate levels, one level, eleven levels, continuous with `levels` or `ordered`, non-string schema names, missing frame column, `p=1`, and `p=101`. Confirm every error message identifies the relevant variable where one exists.

- [ ] **Step 2: Implement `VariableSpec` and canonical category identity.**

Preserve declared levels as a tuple. Validate categories through a private key helper that treats real numeric values `1` and `1.0` as equal but gives booleans a separate key, so `True` is not equal to numeric `1`. Reject unhashable or missing/NaN declared levels with `ValueError`. Keep `ordered` as metadata only; it must not alter the estimator-facing representation.

`parse_schema` must preserve mapping insertion order, reject unknown keys, require exactly the supported metadata for each kind, and return a tuple rather than a mutable list.

- [ ] **Step 3: Define immutable diagnostics and prepared-data records.**

Use these fields so later tasks have a stable contract:

```python
@dataclass(frozen=True)
class DataDiagnostics:
    few_unique_continuous: tuple[str, ...]
    rare_levels: tuple[tuple[str, Any, int], ...]
    p_ge_n: bool
    extra_columns: tuple[str, ...]
    q_estimate: int
    q_limit: int


@dataclass(frozen=True)
class PreparedData:
    names: tuple[str, ...]
    specs: tuple[VariableSpec, ...]
    kinds: np.ndarray
    values: np.ndarray
    codes: np.ndarray
    index: pd.Index
    n_input: int
    n_retained: int
    n_excluded: int
    excluded_labels_digest: str | None
    excluded_labels: tuple[Any, ...] | None
    data_digest: str
    row_identity_digest: str
    diagnostics: DataDiagnostics
```

The `rare_levels` tuple is ordered by schema order and declared-level order and includes every level with fewer than five retained observations, including zero-count levels. `kinds` is boolean with `True` for categorical variables; `codes` is `int16` with `-1` for continuous variables; categorical columns in `values` are zero placeholders.

- [ ] **Step 4: Run schema tests to confirm they initially fail at the missing symbols.**

Run:

```text
python -m pytest tests/unit/cin/test_config.py -k "schema or bounds or duplicate_frame" -q
```

Expected: failure until the types and parser are implemented; then a passing focused subset.

### Task 4: Implement `prepare_data` and all input-boundary behavior

**Files:**
- Modify: `src/mintnet/cin/config.py`
- Test: `tests/unit/cin/test_config.py`

**Interfaces:**
- Consumes: `frame: pd.DataFrame`, `schema: Mapping[str, Mapping[str, Any]]`, and `config: CINConfig`.
- Produces: `prepare_data(frame, schema, config) -> PreparedData`, with no mutation of the caller’s frame.

- [ ] **Step 1: Add missingness and type-conversion tests.**

Add tests named `test_missing_error_reports_counts_and_labels`, `test_complete_case_drops_declared_columns_once`, `test_extra_column_missingness_is_ignored`, `test_retained_rows_guard`, `test_continuous_rejects_boolean_and_infinite_values`, `test_categorical_codes_are_explicit`, `test_numeric_category_equivalence_preserves_boolean_distinction`, and `test_constant_variables_are_rejected`.

Assert the following exact behaviors:

- Duplicate frame indexes fail before preparation.
- `missing="error"` reports per-variable missing counts and offending index labels.
- `missing="complete_case"` removes rows with missing values in any declared column once, records input/retained/excluded counts, stores excluded labels when the exclusion count is at most 1000, and leaves missingness in extra ignored columns irrelevant.
- Retained `N < min_rows` raises with both counts.
- Continuous conversion yields finite `float64`, rejects boolean dtype and `inf`/`-inf`, and rejects nonnumeric values.
- Categorical values outside declared levels raise and identify the offending value.
- A globally constant continuous variable or a categorical variable with only one observed level raises rather than being silently dropped.

- [ ] **Step 2: Implement ordered extraction and missingness handling.**

Require a unique frame index. Parse the schema, enforce `2 <= p <= config.max_variables`, reject duplicate frame column labels, and extract declared columns in schema order. Compute missing masks only for declared columns before conversion. For complete-case mode, build one combined row mask, preserve original row order/index labels, and never call `dropna()` on the whole frame.

Use `excluded_labels_digest = _digest_index(excluded_labels)` when rows are excluded; retain the actual labels only when there are at most 1000. Leave both exclusion fields `None` when no rows are excluded.

- [ ] **Step 3: Implement continuous and categorical materialization.**

For continuous columns, reject pandas boolean dtypes and all-boolean object values, convert with `pd.to_numeric(..., errors="raise")` to `float64`, and reject nonfinite values. Store the converted column in `values[:, j]` and set `codes[:, j] = -1`.

For categorical columns, build a declared-level key-to-code map using the numeric/boolean distinction from `parse_schema`, map every retained value to its declared position, and store `int16` codes. Keep `values[:, j]` at zero. Reject any unknown value with its value and count.

After conversion, reject global constants. Compute diagnostics in deterministic order: continuous columns with at most seven unique values; categorical `(name, level, count)` entries below five; `p >= n_retained`; extra frame columns; and `q_estimate = 3 * n_continuous + sum(len(levels))`. Raise when `q_estimate > config.max_expanded_features`, reporting both actual and allowed widths.

- [ ] **Step 4: Implement stable identity digests and freeze arrays.**

Create a canonical schema JSON from parsed specs, a canonical retained-index string from `repr(label)` joined by `"\x1f"`, and digest bytes in this order: schema JSON, retained index labels, then each column’s little-endian `float64` bytes for continuous data or little-endian `int16` bytes for categorical codes. Use explicit separators between components so concatenation boundaries are unambiguous. Compute `row_identity_digest` from retained index labels alone.

Use the same index digest helper for excluded labels. Before constructing `PreparedData`, make `kinds`, `values`, and `codes` C-contiguous and set `flags.writeable = False`. Return the original retained index as an immutable pandas `Index`; no raw frame is stored.

- [ ] **Step 5: Add diagnostics, digest, and immutability tests.**

Add tests named `test_diagnostics_are_recorded_without_type_changes`, `test_q_estimate_limit_is_enforced`, `test_digest_ignores_frame_column_order`, `test_digest_changes_when_cell_changes`, `test_row_identity_digest_changes_when_index_changes`, and `test_prepared_arrays_are_read_only`.

Use a lowered `max_expanded_features` to exercise the q-cap error rather than constructing a schema that violates the 100-variable or ten-level schema caps. Verify rare/zero-observation level flags, few-unique continuous flags, ignored extra columns, `p >= N`, and the exact placeholder/sentinel conventions for `values` and `codes`.

- [ ] **Step 6: Run the complete Task 01 test file.**

Run:

```text
python -m pytest tests/unit/cin/test_config.py -q
```

Expected: all Task 01 tests pass, including the subprocess import-boundary test.

### Task 5: Verify repository integration and hand off Task 01

**Files:**
- Test: `tests/unit/cin/test_config.py`
- Inspect: `src/mintnet/cin/config.py`, `src/mintnet/cin/__init__.py`

**Interfaces:**
- Consumes: the completed Task 01 package and tests.
- Produces: verified input contracts for Task 02’s feature-space implementation.

- [ ] **Step 1: Run the active regression tests alongside Task 01.**

Run:

```text
python -m pytest tests/unit/test_ebicglasso.py tests/unit/test_motifs.py tests/unit/cin/test_config.py -q
```

Expected: the existing active tests and all new Task 01 tests pass. Historical tests under `archive/` are not part of this active verification command.

- [ ] **Step 2: Check the import boundary and tracked-file scope.**

Run:

```text
python -c "import sys; import mintnet.cin; print('sklearn' in sys.modules, 'matplotlib' in sys.modules)"
git diff --check
git status --short
```

Expected: the import command prints `False False`; the diff has no whitespace errors; only the intended new CIN files are staged/modified, and the pre-existing `.gitignore` change remains unstaged.

- [ ] **Step 3: Commit the completed Task 01 contract.**

```text
git add src/mintnet/cin/config.py src/mintnet/cin/__init__.py tests/unit/cin/test_config.py
git commit -m "feat: implement CIN config and data contract"
```

The next dependency-ordered implementation is Task 02, `Feature blocks and response matrix`. Task 08’s simulation generators may begin in parallel only after this schema shape is stable; no cost pilot or statistical panel work should start yet.

## Self-Review Checklist

- [x] All Task 01 deliverables are assigned to an exact file and interface.
- [x] Every build-plan requirement has a test owner: configuration and hash behavior (Task 2), schema rules (Task 3), missingness/types/categoricals/constants (Task 4), diagnostics/digests/immutability (Task 4), and import-light package behavior (Task 2).
- [x] Review-focus failures have explicit tests: nullable/object values, boolean continuous inputs, numeric-vs-boolean category identity, digest stability, and rare/absent levels.
- [x] No implementation step modifies archived code, changes the active package metadata, or introduces a new runtime dependency.
- [x] Later-task interfaces are explicit: `PreparedData` supplies schema order, kinds, values, codes, retained index, diagnostics, and digests to feature fitting.
- [x] The plan contains no unresolved placeholders or unspecified “appropriate” behavior.
