# Task 02 — Feature blocks and response matrix

Roadmap: §4, M1. Files: `src/mintnet/cin/features.py`, `tests/unit/cin/test_features.py`.

## 1. Purpose

Given `PreparedData` and a set of **training row indices**, fit all per-variable preprocessing on those rows only, and produce (a) the design matrix `B` (all variables' predictor blocks, concatenated, target-self blocks included as workspace) and (b) the response matrix `T` (all target response columns concatenated), for any set of rows (training or evaluation). Invariant I3 lives here: nothing is fit on evaluation rows.

## 2. Deliverables

```python
@dataclass(frozen=True)
class ContinuousBlock:      # fitted on training rows
    mean, sd, knots, spline_coef (residualization), directions (V_r), curv_mean, curv_scale,
    width, rank, flags
    def transform(self, x: np.ndarray) -> np.ndarray   # (n, width)

@dataclass(frozen=True)
class CategoricalBlock:
    prevalence (C,), scale, width, flags
    def transform(self, codes) -> np.ndarray

@dataclass(frozen=True)
class ResponseSpec:          # per-target scoring metadata
    kind, columns (slice/indices in T), y_mean, y_sd (continuous) | prevalence, train_counts (categorical)

@dataclass(frozen=True)
class FeatureSpace:
    blocks: tuple[...]        # per variable
    S: tuple[np.ndarray, ...] # column indices of variable j's predictor block within B
    R: tuple[np.ndarray, ...] # column indices of variable j's response columns within T
    q: int; t: int
    col_means: np.ndarray     # (q,) training means of the concatenated design, for recentering
    def design(self, rows) -> np.ndarray      # (n, q)
    def responses(self, rows) -> np.ndarray   # (n, t)

def fit_feature_space(prepared, train_rows, config) -> FeatureSpace
```

`train_rows` is an integer index array into `PreparedData`; evaluation rows are simply passed to `design`/`responses`. There is no method that accepts evaluation data during fitting.

## 3. Continuous predictor block (roadmap §4.1, step by step)

Let `x` be the training column, `m = len(train_rows)`.

1. `μ = mean(x)`, `s = std(x, ddof=0)`. If `s == 0` (constant **within this partition**): return a zero-width block with flag `constant_in_partition`. This does not remove the variable's pairs; the pair row still gets an estimate (the removed predictor changes nothing, so its gain is exactly 0 for that fold and the fold carries the flag `degenerate_predictor`). `l = (x − μ)/s` for training and evaluation.
2. **Knots.** Compute `np.quantile(l_train, np.linspace(0, 1, n_knots))` and `np.unique` them. If ≥ 2 distinct knots remain, build `SplineTransformer(degree=3, knots=<distinct knots as (k,1) array>, include_bias=False, extrapolation="constant")` and fit on `l_train`. **[added]** Passing knots explicitly (rather than `knots="quantile"`) lets duplicate quantiles (heavy ties) be handled deterministically instead of relying on sklearn behavior. If < 2 distinct knots: no spline; block is the linear column only, flag `few_distinct_values`. Keep the transformer's actual output width; do not hardcode. (`SplineTransformer` with `n_knots=5, degree=3, include_bias=False` yields 6 columns; the design must not depend on that.)
3. **Residualize** spline columns `Φ` on `[1, l]`: `G = [1, l_train]`, `coef = lstsq(G, Φ_train)`, `Φ_res = Φ − G @ coef`. Store `coef`; apply to evaluation rows with the *training* `coef`.
4. **SVD** of `Φ_res_train` (thin). Retain at most `config.max_curvature_rank` right singular vectors whose singular value `> 1e-8 * σ_max`. If `σ_max == 0` or rank cap is 0, retain none (rank `r = 0`).
5. **Project**: `Z = Φ_res @ V_r`. Center with **training** column means. Divide each column by its training population SD and by `sqrt(κ · r)`. Drop any column with training SD `< 1e-12` (adjust `r`).
6. **Block** `= [l, Z]`; recentered with training column means (numerically already ~0). **Do not** rescale the assembled block.

Consequences to assert in tests: the linear column has training variance 1; total curvature variance is `1/κ` regardless of `r`; evaluation rows never influence `μ, s, knots, coef, V_r, curvature scales`.

Record evaluation-range excursions (fraction of evaluation rows with `l` outside training `[min, max]`) — computed at transform time and surfaced by the caller in diagnostics; the roadmap explicitly says do not promise bounded extrapolation of the final block.

`max_curvature_rank = 0` yields block `[l]` only (linear-only comparator). Same code path, no special casing beyond `r = 0`.

## 4. Categorical predictor block (§4.2)

For a variable with `C` declared levels and training one-hot `D` (`m × C`):

1. `π̂ = D.mean(0)`; `Dc = D − π̂`.
2. `s = sqrt(mean_rows(sum_cols(Dc²))) = sqrt(Σ_c π̂_c(1−π̂_c))`. If `s < 1e-12` (single training level): zero-width block, flag `constant_in_partition`.
3. Block = `Dc / s`, **all `C` columns kept** (no reference level; absent-in-training levels remain as all-zero-centered columns; evaluation rows carrying such a level produce `1 − π̂ = 1`, scaled, which is well-defined and harmless with λ>0).

Total block variance is 1 by construction. Never infer levels from evaluation rows (codes are pre-validated in task 01).

## 5. Response matrix (§4.3)

For each variable j in schema order, append to `T`:

- **Continuous target**: one column `(y − y_mean)/y_sd` with **training** mean and population SD. Store `y_mean`, `y_sd` for back-transforming the density on the original scale (task 04). If `y_sd == 0` in this partition the target is `unsupported` for this partition (flag propagated to task 05; do not divide by zero).
- **Categorical target**: `C` indicator columns minus training prevalence `π̂`. Store `π̂` and integer training counts. The unpenalized intercept is `π̂` (added back at scoring). No response standardization, no class weights.

Also record `t`, the total response width, and `R[j]`.

## 6. Assembly and caps

- `B = concat_j block_j(rows)`; `S[j]` = column indices of block j. Zero-width blocks have empty `S[j]`.
- `col_means`: training means of the assembled design (≈0 by construction); `design(rows)` subtracts them so the intercept-free ridge is exact.
- `q = B.shape[1]`. Enforce `q <= config.max_expanded_features` on **actual** widths; raise `ValueError` with actual q and categorical response width otherwise.
- Return contiguous float64 arrays. `design` and `responses` build from cached per-block transforms; do not refit per call.
- Do **not** allocate anything N×p×p×C.

## 7. Tests (`test_features.py`)

Unit/property tests, small n:

1. **Training-only fitting**: fit on rows A; perturb evaluation values drastically; `FeatureSpace` internals (`μ, s, knots, coef, V_r, prevalences`) identical (bitwise) and training-row design identical.
2. **Continuous algebra**: linear column variance 1 (rtol 1e-10); curvature columns orthogonal to `[1, l]` on training rows (max abs inner product < 1e-10); total curvature variance `= 1/κ` for `r ∈ {1, 2}`; `r=0` gives width 1; U-shaped x→y data yields a retained direction correlated with `l²−1`.
3. **Ties/duplicates**: constant partition → zero width + flag; two-valued column → linear only; heavy-tie column with duplicate quantiles builds without error; widths taken from the transformer.
4. **Categorical**: block variance 1; relabeling levels (permute the `levels` order and codes consistently) permutes columns but leaves the ridge-relevant Gram matrix unchanged up to that permutation; absent training level keeps its column; single-level partition gives zero width; evaluation-only level never alters fitted prevalence.
5. **Response**: continuous training mean/SD; categorical rows sum to zero across columns after prevalence removal (each row of `T` block sums to `1 − Σπ̂ = 0`).
6. **Caps**: `q` over cap raises with actual width; p=100 five-level items give `q=500`, `t=500`; p=100 ten-level gives `q=1000` exactly (allowed).
7. **Extrapolation record**: evaluation values beyond training range produce a nonzero excursion fraction and finite (not NaN) block values.

## 8. Acceptance

`python -m pytest tests/unit/cin/test_features.py` green. Reviewer checklist: no call in this module reads evaluation rows during a fit function; no `np.random`; no use of `sklearn` beyond `SplineTransformer`.

## 9. Pitfalls

- SVD sign ambiguity: fix signs (e.g., make the largest-magnitude entry of each right singular vector positive) so results are deterministic across BLAS builds. Tests comparing to references must be sign-invariant.
- `SplineTransformer` returns float64 C-order; ensure explicit knots array shape is `(n_knots, 1)`.
- Do not center categorical blocks with evaluation prevalences under any circumstance.
