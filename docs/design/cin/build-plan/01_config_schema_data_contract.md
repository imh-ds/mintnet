# Task 01 — Configuration, schema, and data contract

Roadmap: §3, §4 (inputs), M1. Files: `src/mintnet/cin/config.py`, `src/mintnet/cin/__init__.py`, `tests/unit/cin/test_config.py` (small; may be folded into `test_features.py` if preferred).

## 1. Purpose

Turn a user `DataFrame` plus a declared schema into a validated, immutable `PreparedData` object, and turn user settings into a validated immutable `CINConfig`. Everything downstream consumes only these two objects. No estimation code runs in this task.

## 2. Deliverables

1. `CINConfig` (frozen dataclass) with validation in `__post_init__` and a stable `config_hash()`.
2. `VariableSpec` (frozen dataclass) and `parse_schema(schema) -> tuple[VariableSpec, ...]`.
3. `prepare_data(frame, schema, config) -> PreparedData`.
4. `PreparedData` (frozen dataclass) plus `DataDiagnostics`.
5. `mintnet/cin/__init__.py` exporting `CINConfig, fit_network, estimate_stability, make_view` (the latter three raise `NotImplementedError` stubs until tasks 05–07 land; do not import unfinished modules eagerly).

## 3. `CINConfig`

Fields (all defaults are the roadmap's fixed initial values; validate ranges, do not tune):

| Field | Default | Validation |
|---|---|---|
| `seed` | required `int` | `>= 0` |
| `missing` | `"error"` | in `{"error", "complete_case"}` |
| `max_seconds` | `300.0` | `> 0`, finite |
| `outer_folds` (K) | `3` | `>= 2` |
| `inner_folds` (J) | `2` | `>= 2` |
| `lambda_grid` | `(0.001, 0.01, 0.1, 1.0, 10.0)` | strictly increasing, all `> 0` |
| `curvature_multiplier` (κ) | `10.0` | `> 0` |
| `max_curvature_rank` | `2` | `0 <= r <= 2`; `0` means linear-only (comparator use) |
| `n_knots` | `5` | `>= 3` |
| `spline_degree` | `3` | `>= 1` |
| `probability_mixture` (ε) | `0.01` | `0 < ε < 1` |
| `count_pseudocount` | `0.5` | `> 0` |
| `variance_floor` | `0.0025` | `> 0` |
| `max_expanded_features` | `1000` | `>= 1` |
| `min_rows` | `30` | `>= 2*outer_folds*inner_folds` — see below |
| `max_variables` | `100` | `>= 2` |
| `tie_tolerance` | `1e-8` | `>= 0` |
| `fallback_stop_fraction` | `0.01` | `in [0, 1]` |
| `pair_batch_size` | `256` | `>= 1` (memory only; must not change results) |

`min_rows`: the roadmap fixes N≥30. Verify at construction that `ceil(30 * (K-1)/K)` rows in an outer training partition can be split into J inner folds with at least 2 rows in each inner-training partition; raise `ValueError` for configurations that cannot (this only bites if someone raises K/J).

Provide `config_hash() -> str`: SHA-256 hex of a canonical JSON dump (`sort_keys=True`, floats via `repr`) of all fields. **[added]** Changing any field other than `pair_batch_size` and `max_seconds` changes the procedure; hash includes all fields except those two so that resumed/sharded runs remain comparable when only batching/timing differ. Record `pair_batch_size` and `max_seconds` in metadata separately.

`CINConfig` is documented as "initial engineering settings, not empirical guarantees". Do not add per-variable overrides.

## 4. Schema

Accepted input, keyed by column name, insertion-ordered:

```python
{"stress": {"kind": "continuous"},
 "sleep_item": {"kind": "categorical", "levels": [1,2,3,4,5], "ordered": True}}
```

`VariableSpec(name: str, kind: Literal["continuous","categorical"], levels: tuple | None, ordered: bool)`.

Rules (each is a `ValueError` with the variable name in the message):

- `kind` required and one of the two values. Unknown keys are errors (catches typos like `level`).
- `continuous`: must not carry `levels`/`ordered`.
- `categorical`: `levels` required, unique, `2 <= len(levels) <= 10`. `ordered` defaults `False`; it is **metadata only** (roadmap: equal spacing never assumed; the estimator treats all categorical variables as unordered indicator sets).
- Column names must be unique strings and present in the frame.
- Schema length `p` satisfies `2 <= p <= config.max_variables`.
- Node order = schema insertion order. This order defines every array axis and the canonical orientation of unordered pairs (`node_i` precedes `node_j` in schema order).
- Extra frame columns not in the schema are ignored and listed in diagnostics.

## 5. `prepare_data`

Steps, in order; each failure names the offending variable(s):

1. **Row identity.** Require `frame.index.is_unique`. The index is the row identity used for digests and exclusion reporting. (No separate id column in the baseline.)
2. **Column extraction** in schema order.
3. **Missingness audit.** Count NaN/None/pd.NA per declared column. If any and `missing == "error"`: raise listing per-variable missing counts and the first few offending index labels. If `complete_case`: drop rows with any missing declared value **once, globally**; record `n_input`, `n_retained`, `n_excluded`, excluded index labels (stored as a digest plus, if ≤ 1000, the list). No pairwise deletion, no imputation.
4. **Retained-N guard.** `n_retained >= config.min_rows`, else `ValueError` stating both counts.
5. **Continuous coercion.** Must convert to float64 without loss; reject non-numeric, `inf`, `-inf`. Reject boolean dtype declared continuous (force explicit categorical declaration).
6. **Categorical coding.** Map each value to its position in `levels` by equality. Implementation: build `dict(level -> code)`; for numeric levels normalize `1.0`/`1` to the same key (compare via `==` after `float()` where both are real numbers) but do not merge `True`/`1`. Any value outside `levels` is an error listing the offending distinct values and counts. Never infer or add levels from data.
7. **Constant-variable rejection.** A continuous variable with zero SD over retained rows, or a categorical variable with a single observed level, is an error naming it. Never silently drop.
8. **Diagnostics (non-fatal, recorded):**
   - continuous variables with `<= 7` unique values (`few_unique_continuous`) — no type change;
   - categorical levels with `< 5` retained observations, and levels with zero observations (`rare_levels`);
   - `p >= N` flag;
   - extra ignored columns;
   - expanded-width preview `q_estimate = 3 * n_continuous + sum(len(levels))` and its comparison to `max_expanded_features`. If `q_estimate > max_expanded_features`: error (the roadmap caps q ≤ 1000; report actual q and the categorical response width). **[added]** This is the only place q is checked before fitting; task 02 asserts it again on actual widths (continuous blocks may be narrower than 3).
9. **Digests.** `data_digest`: SHA-256 over, in order, the schema JSON, the retained index labels (canonical `repr` joined with `\x1f`), then per column the little-endian float64 bytes (continuous) or int16 codes (categorical). `row_identity_digest`: SHA-256 of the index labels alone. Both are hex strings.

`PreparedData` fields:

```text
names: tuple[str, ...]; specs: tuple[VariableSpec, ...]
kinds: np.ndarray[bool]  # True = categorical
values: np.ndarray (N, p) float64   # continuous columns; categorical columns hold 0.0 placeholder
codes: np.ndarray (N, p) int16      # categorical codes; -1 for continuous
index: pd.Index (retained row labels)
n_input, n_retained, excluded_labels_digest, excluded_labels (optional)
data_digest, row_identity_digest, diagnostics: DataDiagnostics
```

The object is treated as read-only (`arr.flags.writeable = False`). Raw data is **not** stored in fit results; only digests and counts (roadmap §3).

## 6. Tests (`test_config.py`)

- Default `CINConfig(seed=1)` values equal the roadmap table (a regression test that fails if a default silently changes).
- Each invalid field value raises `ValueError`; `config_hash` is invariant to `pair_batch_size`/`max_seconds` and changes for every other field.
- Schema: unknown key, missing `levels`, duplicate level, 1 level, 11 levels, continuous with levels, duplicate column, missing column, `p=1`, `p=101` each raise.
- Data: NaN with `error`; `complete_case` retains expected rows and reports excluded; retained N=29 raises; inf raises; unknown category raises with the value; constant variable raises with its name; `True/1` not merged; numeric `1.0` matches level `1`.
- Digest stability: same data reordered columns in the *frame* (not schema) gives the same digest; changing one cell changes it; changing index labels changes `row_identity_digest`.
- Diagnostics: few-unique and rare-level flags appear without altering types; `q_estimate` limit error triggers with 101 five-level items is not applicable (p cap hits first) — use 100 variables of 11-level is rejected by schema; test the q cap with `max_expanded_features` lowered.

## 7. Acceptance

`python -m pytest tests/unit/cin/test_config.py` green; no import of numerics beyond numpy/pandas; `import mintnet.cin` does not import scikit-learn or matplotlib (keep import cost low; later modules import lazily where reasonable).

## 8. Pitfalls

- pandas nullable dtypes and `Categorical` columns: convert through `.to_numpy(dtype=object)` before mapping to avoid silent NaN-to-category coding.
- Do not `dropna()` on the whole frame — only on declared columns.
- Never mutate the caller's frame.
