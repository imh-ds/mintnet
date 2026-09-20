# Task 05 — Cross-fitting and fit orchestration

Roadmap: §5.2, §6.3, §7 (fit outputs), M2. Files: `src/mintnet/cin/fit.py`, `src/mintnet/cin/result.py`, `tests/unit/cin/test_fit.py`.

## 1. Purpose

Wire tasks 01–04 into `fit_network(frame, schema, config) -> NetworkFit`: shared shuffled splits, nested penalty tuning, exact full/reduced scoring for every ordered pair, row-sum aggregation, symmetrization, statuses, budgets, and cost counters. Implements invariants I2, I3, I4, I5 end-to-end.

## 2. Deliverables

- `fit_network(frame, schema, config, *, deadline=None) -> NetworkFit` (`deadline` is an absolute `time.monotonic()` value used by stability to impose a budget from outside; default derives from `config.max_seconds`).
- `NetworkFit` dataclass in `result.py` (fields specified in §7 and in task 06).
- Internal: `make_splits`, `tune_lambdas`, `score_partition`, `aggregate`, `Budget`.

## 3. Splits (deterministic, shared)

- `root = np.random.SeedSequence(config.seed)`; spawn children by fixed keys: `root.spawn(1)[0]` for outer permutation; per outer fold `f`, child `f` for the inner split. Persist the entropy/seed tuple in metadata.
- Outer: one shuffled permutation of retained rows partitioned into `K=3` folds (sizes differ by ≤1). **All targets share it** (no target-specific stratification, roadmap §6.3).
- Inner: within each outer-training partition, shuffle and split into `J=2` folds using that outer fold's child seed. Shared by all targets.
- Minimum-size guarantee is checked in config (task 01). N=30 ⇒ outer-train 20, inner-train 10: flag `tiny_partition` diagnostics but proceed.

## 4. Per-outer-fold procedure (roadmap §6.3, exact order)

```text
for f in outer folds:
    train_f, eval_f = ...
    # (a) tuning: shared inner splits, full target models only
    for each inner fold g of train_f:
        fs = fit_feature_space(prepared, inner_train_g)                # task 02, inner-train only
        B_in, T_in, E_in = design(inner_train_g), responses(...), design(inner_eval_g)
        for lam in grid (sequential):
            sol = RidgeSolution(B_in, T_in, lam)                        # 1 factorization
            ws  = OmissionWorkspace(sol, {"train":B_in, "eval":E_in})
            for target j (skipping unsupported):
                pred_train, pred_eval = ws.predict_omit(S_j, R_j)       # self block removed (I4)
                logq_eval = score(target j)                             # task 04, own training variance
                accumulate score_sum[j, lam] and row count
    lam_j = choose_lambda(...)                                          # per target, task 04
    # (b) outer scoring at chosen penalties only
    fs = fit_feature_space(prepared, train_f)
    for lam in sorted(set(lam_j)):                                      # <= |grid| factorizations
        sol, ws = ...
        for target j with lam_j == lam:
            full pred/score with S_j
            intercept-only score (S = all columns)
            for predictor i != j in batches:
                reduced pred/score with S_j ∪ S_i                       # exact omission (I5)
                d_ij_rows = logq_full - logq_reduced                   # per held-out row
                sum_diff[i, j] += d_ij_rows.sum(); n_rows[i, j] += len(eval_f)
                fold_count[i, j] += 1
    check budget between (fold, lambda) factorizations and between target batches
```

`gain_i_to_j = sum_diff[i,j] / n_rows[i,j]` is the mean over **all held-out rows** (row-sum aggregation; equal-fold-mean averaging is forbidden).

Large-factorization budget: inner `K·|grid|·J` + outer `K·|distinct chosen λ|` ≤ `K·|grid|·(J+1) = 45`. Instrument and assert via a counter.

## 5. Aggregation and statuses

After all folds, for each unordered pair `(i, j)` in schema order with `i < j`:

- `weight_nats_raw = (gain_i_to_j + gain_j_to_i)/2`, negatives preserved.
- `complete` iff both directions have `n_rows == N_retained` and `fold_count == K`. Otherwise no weight is published (partial sums stay in the diagnostics tables only).
- Status assignment, highest priority first: `unsupported` (response constant in any partition for i or j, or an unsupported degenerate case documented in task 02), `numerical_failure` (structured error from task 03 or non-finite score), `budget_exceeded` (work started but deadline hit), `not_started`.
- Degenerate predictor block in some fold: the reduced fit equals the full fit; the gain contribution is exactly 0 for that fold; the pair stays `complete` with flag `degenerate_predictor_fold{f}`.
- Never convert NaN to zero. Non-finite scores ⇒ `numerical_failure` for the affected directional pair(s).

`display_magnitude_nats = max(weight,0)`, `gaussian_equivalent_magnitude = sqrt(-expm1(-2*display_magnitude))`, `orientation_gap = |g_ij − g_ji|`, `n_scored`, `folds_complete`, `diagnostic_flags` (semicolon-separated tokens) are assigned here and stored on the pair table (roadmap §7 schema). Unavailable ⇒ `NaN` in the DataFrame with the status explaining why, and the CSV writer emits empty fields.

## 6. Node table and diagnostics

Per node: `lambda_fold_1..K`, `full_score_mean`, `intercept_score_mean`, `full_minus_intercept`, prediction counts, type-specific diagnostics:

- continuous: variance-floor hits per model type, training vs evaluation MSE, standardized residual skew/kurtosis of evaluation residuals (descriptive, supports the methods-text warnings), evaluation-range excursion fractions, constant-partition flags;
- categorical: clipped fraction, zero-sum fallbacks, min probability, rare/absent training levels.

Per fold table: fold sizes, factor counts, wall times per phase, fallback counts.

## 7. `NetworkFit` and provenance (roadmap §3, last paragraph)

Persist: config (+hash), schema, retained/excluded counts, `data_digest`, `row_identity_digest`, dependency versions (`numpy, scipy, scikit-learn, pandas, python`), split seeds/entropy, git commit (best effort; `None` if unavailable), runtime and status metadata, cost counters (`n_large_factorizations, q, t, phase_seconds, peak_rss_mb (if available), n_fallbacks`), and `fit_id = sha256(config_hash, schema_json, data_digest, code_rev)[:16]`. Raw participant data is **not** retained. The object supports `to_dict()`/`from_dict()` used by task 06's directory writer.

## 8. Budgeting

- `Budget(deadline)` with `check(phase)` called between (fold, λ) factorizations and between target batches; raises internal `BudgetExceeded`.
- On exceed: stop, mark every pair not yet complete as `budget_exceeded` if any of its work started, otherwise `not_started`; return a `NetworkFit` with `metadata["complete"] = False` and elapsed time. Never return a partially averaged weight.
- Point-fit default `max_seconds=300`.

## 9. Tests (`test_fit.py`)

Small problems (p ≤ 6, N ≤ 120), seconds each:

1. **End-to-end vs brute force**: for p=4 continuous, replicate the entire outer/inner pipeline with a slow direct implementation (refit restricted ridge per pair from scratch using `direct_restricted_ridge` and the same splits/λ per target) and require `gain_i_to_j` equal to rtol 1e-7.
2. **Training-only tuning**: changing evaluation-fold response values changes nothing about that outer fold's selected λ or transforms (assert equality of stored `lambda_fold`, fitted feature-space internals); changing a held-out row's values changes only that fold's scores.
3. **Row-sum aggregation**: with unequal fold sizes, the aggregated gain equals `total sum / N`, not the mean of fold means (construct N not divisible by K).
4. **Completeness**: a forced budget stop yields `budget_exceeded`/`not_started`, weights NaN, never 0; a failure injected for one target makes only its incident pairs incomplete.
5. **Sign/negatives**: a pure-noise pair can yield negative raw weight; it is preserved in `weight_nats_raw` and `display_magnitude_nats = 0`.
6. **Deterministic reproducibility**: same config/seed/data ⇒ bit-identical pair table; different seed changes splits; `pair_batch_size` changes nothing.
7. **Factorization count invariant**: instrumented count `≤ 45` for p=3 and p=12 alike.
8. **Self-leakage end-to-end**: a synthetic target column that is an exact duplicate of another variable: the target's own block cannot inform its own model (I4); the duplicate predictor gets a large gain and gains for other pairs are not inflated by the workspace.
9. **Type mixing**: one categorical, one continuous, one 3-level categorical fit completes, probabilities valid, node diagnostics populated.
10. **p=2**: full model has only the other variable; reduced is intercept-only; result complete.
11. **Symmetrization**: weight equals the mean of the two saved directional gains exactly.
12. **Dense-dependence sanity**: a p=8 Gaussian toy with a known strong edge ranks it above non-edges (loose sanity; not a statistical claim).

## 10. Acceptance

`python -m pytest tests/unit/cin/test_fit.py` plus tasks 01–04 suites green. Peak memory at q=1000 stays under 1 GB (verified in task 10, not locally). Reviewer checks: no per-pair large factorization, no scoring of workspace models containing the self block, statuses always assigned.

## 11. Pitfalls

- Sequential λ loop matters for memory: free `H` and `BH/EH` before the next λ.
- Indexing: work in schema order; a single `pair_index` helper mapping `(i,j)` ↔ row keeps tables aligned.
- Do not compute the reduced models for `(i, j)` when `i == j`.
- Keep the outer scoring loop keyed by target λ so at most five distinct factorizations happen per outer fold.
