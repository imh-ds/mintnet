# Task 03 — Shared ridge engine and exact block omission

Roadmap: §5, M1. Files: `src/mintnet/cin/ridge.py`, `tests/unit/cin/test_ridge.py`. This is the numerical heart; it carries invariants I4 and I5.

## 1. Purpose

For one training partition and one penalty λ, solve a single multiresponse ridge system over the full design `B` and all responses `T`, then produce, for any target j and any predictor i, the **exact** predictions of the restricted ridge fit that drops a set of columns — without refactorizing.

## 2. Mathematics (must be stated in the module docstring)

Objective, per partition with `m` training rows:

`min_β ‖T − Bβ‖_F² /(2m) + λ‖β‖_F²/2`  (B, T centered with training means; intercept handled by the centering; categorical response intercept = training prevalence added back at scoring, task 04).

Equivalent to sklearn `Ridge(alpha=m·λ, fit_intercept=False)` on centered data (multiply the objective by 2m).

- `A = BᵀB + mλ I` (SPD, positive λ ⇒ solvable even for q > m).
- `H = A⁻¹`, `β = H BᵀT`.
- **Omission identity.** For a column set `S`, the restricted ridge over the retained columns `K = S^c` has solution `β_K^{(−S)} = β_K − H_{KS} H_{SS}⁻¹ β_S`, with `β_S^{(−S)} = 0`. Proof sketch to include in the test docstring: block inverse of `A` = `[[A_KK, A_KS],[A_SK, A_SS]]`; `H_KK⁻¹ = A_KK − A_KS A_SS⁻¹ A_SK`, hence `(A_KK)⁻¹ = H_KK − H_KS H_SS⁻¹ H_SK`, and `β_K^{(−S)} = (A_KK)⁻¹ (BᵀT)_K`; simplify using `β = H BᵀT`.
- **Predictions.** For a feature matrix `X` (rows × q, same centering): full `X β`; omitting S: `X β − (X H[:,S]) · solve(H_SS, β[S, :])`. Because omitted-column coefficients are exactly zero, the correction requires no explicit zeroing of X's omitted columns.
- Column sets used by the caller: full model for target j: `S = S_j` (the target's own predictor block — invariant I4); reduced model dropping predictor i: `S = S_j ∪ S_i`; intercept-only: `S = all columns`.
- Response selection: only columns `R_j` of `β`/`T` are needed for target j. Never apply the correction to all `t` responses.

The reduced fit uses the **same λ, same centering, same block scaling**, with **no renormalization after deletion** (invariant I5).

## 3. Deliverables

```python
class RidgeSolution:
    def __init__(self, B, T, lam, config): ...   # builds Gram, cross-products, Cholesky, beta
    m: int; q: int; t: int; lam: float
    beta: np.ndarray               # (q, t)
    def H(self) -> np.ndarray      # lazy, symmetrized, solve against identity via Cholesky (no np.linalg.inv)
    def scaled_normal_residual(self) -> float   # ||A beta - B^T T||_F / max(||B^T T||_F, tiny)

class OmissionWorkspace:
    """Caches X @ H for a set of design matrices (training B, evaluation E) at one λ."""
    def __init__(self, solution, matrices: dict[str, np.ndarray])
    def predict_full(self, name, response_cols) -> (n, |R|)
    def predict_omit(self, name, omit_cols, response_cols) -> (n, |R|)
    def omitted_coefficients(self, omit_cols, response_cols) -> (q, |R|)  # for tests/diagnostics

def direct_restricted_ridge(B, T, lam, keep_cols, m) -> beta_keep    # slow reference AND logged fallback
```

`predict_omit` returns an array and a status flag: `ok` or `fallback`. On a numerical failure of the small `H_SS` solve it calls `direct_restricted_ridge` for that specific omission and increments a fallback counter carried on the workspace (invariant: no jitter, no λ change, no silent switch of algorithm).

## 4. Algorithm and cost discipline

Per `(partition, λ)`:

1. `G = BᵀB`, `C = BᵀT` once. `A = G + mλ I`. `cho_factor(A, lower=True)` (SciPy). `β = cho_solve(c, C)`.
2. `H`: `cho_solve(c, I_q)`, then `H = (H + Hᵀ)/2`. Do **not** call `np.linalg.inv`. `H` is required only when at least one omission is requested at this λ (inner folds need it too, for self-block removal).
3. `BH = B @ H` (m × q) and `EH = E @ H` (n_eval × q) computed once per matrix, cached in `OmissionWorkspace`. Memory: q ≤ 1000 ⇒ `H` is 8 MB; `EH` for n ≤ ~1000 rows is ≤ 8 MB. Fine; peak stays well below 1 GB.
4. Omission of `S` (small; `|S| ≤ 2·10 = 20` for categorical, `≤ 6` for continuous): `HSS = H[np.ix_(S,S)]`; `cho_factor(HSS)`; `W = cho_solve(., β[S][:, R])`; `pred = X β[:, R] − (XH[:, S]) @ W`. If `cho_factor` raises `LinAlgError` or the result contains non-finite values: fallback path.
5. **Batching.** The caller loops over targets j, then over predictors i in batches of `pair_batch_size`. Never materialize an N×p×p×C tensor. Precompute per target j: `H[S_j,S_j]` Cholesky and `β[S_j, R_j]` once. **[added]** Optional optimization if profiling demands: reuse the target's factor for a rank-`|S_i|` update instead of refactorizing `H[S_j∪S_i, S_j∪S_i]` per pair; only if profiling names it as a bottleneck (roadmap allows one profiling-driven pass).

Cost accounting (report in metadata, roadmap §5.2): number of large `cho_factor` calls (`q×q`), expanded widths `q, t`, phase timings (`gram`, `factor`, `H`, `omission`, `score`), peak RSS, fallback count. The invariant to assert in an integration test: large factorizations `≤ K·|λ_grid|·(J+1)` = 45, independent of p.

## 5. Failure handling

- After factoring, verify `scaled_normal_residual ≤ 1e-8` for a random subset of ≤ 3 response columns in the first factorization of each fit; in tests, check for every λ. If a factorization fails with `LinAlgError` (should not with λ ≥ 0.001 and centered scaled features), mark the partition `numerical_failure` and propagate; never bump λ or add jitter.
- Symmetrize `H` before block extraction; assert `max|H−Hᵀ| ≤ 1e-12·‖H‖`.
- Fallback policy (roadmap §5.2): isolated small-block failure → direct restricted solve, logged with `(fold, λ, target, predictor)`. If `fallbacks / requested_directional_outer_fits > 0.01` ⇒ stop the fit as `numerical_failure` (raise a structured error consumed by task 05) — do not quietly become the slow algorithm.
- BLAS: engine performs no threading itself; evidence runs set one BLAS thread (task 09).

## 6. Deferred (do not build)

Dual/kernel solver (q > m), GCV tuning. The roadmap allows a dual solver **only** if the cost pilot's single profiling pass names it; record this as a contingency in task 10 and leave it unimplemented here. Because strictly positive λ makes the primal SPD, q > m needs no special handling.

## 7. Tests (`test_ridge.py`) — the roadmap's M1 correctness contract

Reference implementation: `direct_restricted_ridge` using `np.linalg.solve` on the restricted normal equations, plus a comparison to `sklearn.linear_model.Ridge(alpha=m*lam, fit_intercept=False)` on the centered restricted design.

1. **Full-fit identity**: `beta` equals sklearn `Ridge` for random `B, T` (rtol 1e-8), including `q > m`.
2. **Omission identity**: for random `S` (sizes 1, 3, 6, 20, and a set covering all but one column, and all columns), `omitted_coefficients` equals direct restricted ridge on `K = S^c` with zero rows on `S` (rtol 1e-8; in ill-conditioned q > m case with tolerance justified by the scaled residual).
3. **Predictions**: training and evaluation predictions for full and omitted models match direct fits; residual variances computed from them match.
4. **p = 2 and intercept-only**: `S = all columns` gives exactly zero coefficients and intercept-only predictions; full model for p=2 equals a single-predictor ridge.
5. **Self-leakage adversarial test** (roadmap M1): construct `B, T` where target j's own block is a near copy of its response. The global `β` (workspace) predicts the target almost perfectly via its self block. Assert that `predict_omit(S_j)` matches a model trained with the self columns physically removed, and that its held-out error is *not* near zero. Also assert the uncorrected `predict_full` on the workspace would have leaked (test documents the hazard).
6. **Collinearity**: duplicate columns, categorical all-level blocks (rank-deficient); positive λ still gives finite exact identities.
7. **Zero-width blocks**: omission of an empty `S` returns the full prediction unchanged and flags `degenerate`; omission with an empty predictor block does not raise.
8. **Fallback path**: force `cho_factor` failure via a monkeypatch; the fallback matches the direct fit, is logged, counter increments; exceeding the 1% rule raises the structured error.
9. **Cost invariant**: a workspace run over many targets performs a number of large factorizations independent of the number of targets (instrument `cho_factor` calls on `q×q` matrices).
10. **Symmetry/residual**: `H` symmetric; `scaled_normal_residual < 1e-10` for well-conditioned data.

## 8. Acceptance

`python -m pytest tests/unit/cin/test_ridge.py` green at the stated tolerances; a short benchmark (kept out of `tests/`, in a scratch script) shows omission cost per pair is small compared to one factorization at q=300. Do not publish local timings as evidence.

## 9. Pitfalls

- `cho_factor` returns `(c, lower)`; pass both to `cho_solve`.
- Fortran vs C order affects speed, not results; be consistent.
- Do not form `A⁻¹` for prediction of the full model; use `β` directly. Use `H` only for omission blocks.
- Never share a `RidgeSolution` across partitions or λ.
