# Task 04 — Scores and penalty tuning

Roadmap: §6.1, §6.2, part of §6.3, M1. Files: `src/mintnet/cin/scores.py`, `tests/unit/cin/test_scores.py`.

## 1. Purpose

Convert fitted ridge predictions into per-row **log scores** (nats) for continuous and categorical targets, provide the intercept-only baseline through the same adapters, and select each target's penalty from inner-fold full-model scores. The scoring functions are pure (arrays in, arrays out) so they can be tested against closed-form and analytic oracles.

## 2. Continuous Gaussian score (§6.1)

Inputs: standardized evaluation response `y_std`, evaluation prediction `pred` (standardized scale), training residuals `r_train` (same model, standardized scale), training response SD `sd_y`.

```text
v      = max(mean(r_train**2), variance_floor)      # RSS/m, floor 0.0025
logq   = -0.5*(log(2*pi*v) + (y_std - pred)**2 / v) - log(sd_y)
```

Rules:

- `v` is each **model's own** training variance (full and each reduced model separately). Never estimated from evaluation residuals.
- Simple RSS/m convention, no effective-df correction; the roadmap explicitly rejects switching per fixture. Record the floor-hit indicator (`v` was raised to the floor), the training loss, and the evaluation mean-squared error per model for diagnostics.
- The `−log(sd_y)` term puts scores on the original response scale; it cancels in full-minus-reduced differences for the same target but keeps node scores interpretable. Keep it for consistency with the categorical adapter.
- Constant response in the partition: caller marks the target `unsupported` (task 02); this function is never called with `sd_y = 0`.

## 3. Categorical score (§6.2)

For a target with `C` declared levels, a training partition of `m` rows, and ridge raw class scores `a = prevalence + ridge_output` (shape `n × C`; task 03 returns the ridge part, this task adds `π̂`):

```text
pi_c   = (train_count_c + 0.5) / (m + 0.5*C)          # smoothed prior
u      = max(a, 0)
v      = u / u.sum(1)        if u.sum(1) > 0 else pi      # row-wise
q      = 0.99*v + 0.01*pi
logq   = log(q[row, observed_level])
```

- Full, every reduced model, **and** the intercept-only baseline use exactly the same normalization and mixture (invariant I5 spirit: no per-model conventions).
- Guarantees: `q > 0` (floor `0.01·pi_c > 0`), rows sum to 1 within 1e-12, all finite. Assert this in a debug/test path; in production cost mode assert once per fit on the first scored batch and record min probability.
- Record per node/fold: fraction of clipped (`a < 0`) entries, count of zero-sum fallbacks, absent training levels, levels with `< 5` training observations.
- This is the finite additive LSPC-type adaptation; do not describe it as multinomial logistic regression or claim compatibility of the node conditionals as a joint model.

## 4. Intercept-only baseline

Use the same adapters with predictor set `S = all columns` (task 03): continuous → prediction 0 on the standardized scale, `v = 1` (training residual variance of a centered standardized response = 1 → `max(1, floor) = 1`); categorical → `a = prevalence`, so `v = π̂` (or `pi` fallback if a level absent — note `π̂` may contain exact zeros; normalization handles it, and the 0.01·pi mixture keeps `q>0`). Report each node's mean **full-minus-intercept** held-out gain per observation. Do not delete incident edges if this is poor (roadmap §6.2).

## 5. Penalty selection (roadmap §6.3 steps 2–3)

Implement as a function used by task 05, kept here so it is unit-testable:

```python
def choose_lambda(scores_by_lambda: np.ndarray,   # (n_lambda,) sums of inner held-out logq over all inner folds
                  n_rows: int,                     # total inner-held-out rows contributing
                  grid: tuple[float, ...],
                  tie_tolerance: float) -> tuple[float, int]
```

- Objective: **maximum** total inner held-out log score (sum over rows across inner folds = row-count-weighted mean).
- Ties: all λ with score `>= best − tie_tolerance` are tied; choose the largest λ.
- Full-model scores only; **no reduced-model search**, per-target λ; the same λ is then used for that target's full and every reduced model (I5).
- Return the index for auditing (persist λ per outer fold per target).
- If any inner fold lacks support (e.g. continuous response constant in an inner-training partition), the target is `unsupported` for that outer fold; do not tune on the remaining folds silently.

## 6. Public helper surface

```python
gaussian_logscore(y_std, pred, r_train, sd_y, variance_floor) -> (logq, info)
categorical_logscore(codes, ridge_out, prevalence, train_counts, m, mixture, pseudocount) -> (logq, info)
intercept_scores(...)  # thin wrappers reusing the two above
choose_lambda(...)
```

`info` dicts hold the diagnostics listed above (floor hit, clipped fraction, zero-sum count, min probability). They are aggregated by task 05 into node/fold tables.

## 7. Tests (`test_scores.py`)

1. **Gaussian closed form**: for a known linear-Gaussian toy with training-variance `v`, `logq` equals `scipy.stats.norm.logpdf(y_original, mean, sd=sqrt(v)*sd_y)` (rtol 1e-12).
2. **Own-variance rule**: the reduced model with larger training residuals gets larger `v`; mutating evaluation residuals does not change `v`.
3. **Floor**: perfectly fitted training data hits `v = 0.0025`; flag set.
4. **Categorical normalization**: rows sum to 1, `q > 0`, negative scores clipped, zero-sum row falls back to `pi` and yields `q = pi` (mixture leaves it unchanged), absent-level smoothing matches the formula by hand for a 3-level example.
5. **Relabeling equivariance**: permuting categorical levels (and codes) permutes probabilities and leaves per-row `logq` unchanged.
6. **Oracle**: Gaussian population with known partial correlation ρ; using exact-population coefficients (no ridge) the expected full-minus-reduced log score equals `−0.5·log(1−ρ²)` within Monte Carlo error at n=200k **as a slow marker-excluded check kept outside `tests/`** (roadmap: no N=20,000 stochastic recovery in the unit suite). In the unit suite, use a deterministic analytic check instead: compute the expected log score difference by numerical quadrature over the bivariate normal.
7. **Exact categorical oracle**: with a known finite joint (2 binary variables), plug true conditionals (as if the ridge output were exact) and confirm `sum p·(log q_full − log q_reduced)` equals the analytic CMI; also verify the mixture-smoothed version deviates by at most a computable epsilon bound.
8. **Intercept baselines**: continuous intercept-only score equals training-mean Gaussian log density; categorical equals the smoothed empirical prevalence log-loss.
9. **`choose_lambda`**: max selection, tie → larger λ within `1e-8`, a strictly worse larger λ is not chosen, deterministic under array permutation of nothing else.
10. **No leakage of evaluation data into `v` or `pi`**: mutate evaluation labels; `v` and `pi` unchanged.

## 8. Acceptance

`python -m pytest tests/unit/cin/test_scores.py` green; docstrings state units (nats/observation), the model-based interpretation, and the identity `E[gain] = CMI − E KL_full + E KL_reduced` (roadmap methodology §4) so a reader does not equate the number with true CMI.

## 9. Pitfalls

- Mixing scales: the Gaussian score is on the original response scale; do not compare continuous scores against categorical scores across nodes.
- `log(q)` of the *observed* level only; do not use argmax.
- Equal-weight averaging of fold means is forbidden; downstream aggregation is sum-of-rows (task 05).
