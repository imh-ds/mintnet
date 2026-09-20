# Final technical implementation roadmap

> For the implementing agent: execute the milestones in order. If available, use `superpowers:executing-plans` for implementation. This document does not request automatic delegation. Checkboxes are future work, not completed work.

**Goal:** Build and evaluate a usable exploratory conditional predictive-information network for 2–100 variables, including a properly evaluated categorical-item branch.

**Architecture:** A shared multiresponse ridge engine with training-only linear/curvature or indicator blocks; exact omitted-block fits; paired held-out scores; independent display and optional repeat-stability layers.

**Tech stack:** Repository Python 3.11, NumPy, SciPy, scikit-learn, pandas, PyYAML, matplotlib, and pytest. No new runtime framework, service, R installation, or networkx dependency is required.

**Spec:** [Final methodology outline](methodology_outline_2026-09-19.md). Evidence provenance and corrections: [feasibility review](feasibility_review_2026-09-19.md). Date: 2026-09-19; inspected repository HEAD `069c10e`.

This is the final consolidated specification. Do not combine conflicting defaults from the previous Codex or Claude plans. The existing smoke is a numerical reference for a related procedure, not the implementation or validation of this candidate.

## 1. Global constraints and review focus

Required invariants:

1. No conditioning-subset enumeration, Pearson/marginal screening, mandatory neighbor cap, or reuse of historical confidence curves.
2. Every unordered pair has a result/status; incomplete estimates are not zero.
3. All transformations and penalty selection are training-only. All targets share each split.
4. Target-self predictors must be removed before scoring any model, including tuning models.
5. Omitting a predictor means the exact restricted ridge fit at the same penalty and feature convention, not a mask, permutation, or one-step logistic approximation.
6. Keep signed raw gains; only positive complete estimates have display magnitude.
7. View changes do not refit. No sign uncertainty can erase an estimated magnitude.
8. Ordinary fits do not invoke resampling. Requested resampling has explicit count and budget.
9. Preserve historical pipelines/APIs and frozen evidence. Add an experimental namespace first.
10. Local unit/smoke correctness checks are allowed; material comparative evidence follows the existing Actions workflow, with bounded configurations frozen before results.

Review specifically for self leakage, concealed per-pair large factorizations, invalid categorical probabilities, incorrect graph truth, and confidence/causal claims stronger than the evidence.

## 2. Repository integration

Create the following small package and supporting artifacts:

```text
src/mintnet/cin/
  __init__.py          # exports
  config.py            # validated configuration and schema
  features.py          # train-fitted blocks and response transformations
  ridge.py             # shared solve, omitted-block fit, direct test reference
  scores.py            # Gaussian and categorical scores
  fit.py               # splits, tuning, all-pair scoring, budgets
  result.py            # serializable fit/edge/node metadata
  stability.py         # optional repeat records and preflight
  views.py             # pure filters, tables, basic plot/export
src/mintnet/simulation/cin_networks.py
src/mintnet/experiments/cin_cost.py
src/mintnet/experiments/cin_cost_reporting.py
src/mintnet/experiments/cin_baseline.py
src/mintnet/experiments/cin_baseline_reporting.py
tests/unit/cin/test_{features,ridge,scores,fit,views,stability}.py
tests/integration/test_cin_runners.py
configs/cin_cost.yaml
configs/cin_cost_smoke.yaml
configs/cin_baseline.yaml
configs/cin_baseline_smoke.yaml
docs/cin_cost_charter.md
docs/cin_baseline_charter.md
docs/cin_user_guide.md
```

These are proposed files. Inspect the repository again before implementation to avoid overwriting work added since this review. Combine tiny helpers where appropriate; do not build a generic modeling framework first.

Reuse `simulation/motifs.py` only for a historical regression case. Use `mi/structured_density.py` as a scoring reference, not as a source of preprocessing conventions. Read `experiments/stage5a.py`, its reporting module, `.github/workflows/sharded_benchmark.yml`, and `scripts/aggregate_shards.py` for integration. Audit `comparators/ebicglasso.py` failure/convergence reporting before comparative claims. The old `api.py`, search, screening, bootstrap, DPI, and confidence modules are not dependencies of CIN.

No blocking housekeeping changes to archived APIs are required before the pilot. A later deprecation decision can address their historical claims separately. Append evidence findings to `docs/decision_log.md` using the next available identifier; never rewrite frozen entries or require a particular AI coauthor identity.

## 3. Public API and fixed initial defaults

```python
from mintnet.cin import CINConfig, fit_network, estimate_stability, make_view

fit = fit_network(
    frame,
    schema={
        "stress_score": {"kind": "continuous"},
        "sleep_item": {"kind": "categorical", "levels": [1, 2, 3, 4, 5],
                       "ordered": True},
        # Explicitly declare every included column.
    },
    config=CINConfig(seed=2026, missing="error", max_seconds=300),
)
view = make_view(fit, min_effect=0.01, require_both_positive=False)
# 0.01 is an illustrative display threshold, not a significance threshold.
repeats = estimate_stability(fit, frame, repeats=10, fraction=0.8,
                             max_seconds=600)
stable = make_view(fit, min_effect=0.01, stability=repeats,
                   min_stability=0.8)
```

| Setting | Initial contract |
|---|---|
| Observations | Independent rows; retained N≥30, 2≤p≤100 |
| Types | Explicit continuous or categorical; categorical level schema of 2–10 levels |
| Missing | Error by default; explicit `complete_case` removes rows once globally |
| Outer folds K | 3 shuffled folds, shared by all variables |
| Inner folds J | 2 shared folds within each outer-training partition |
| Normalized λ grid | `[0.001, 0.01, 0.1, 1.0, 10.0]` |
| λ selection | Per target, maximum full-model inner held-out log score; ties within 1e-8 choose larger λ |
| Continuous basis | One linear column plus up to two residualized spline-curvature columns |
| Curvature multiplier κ | 10; fixed, not tuned |
| Spline | Cubic, five quantile knots, no bias, constant extrapolation before residualization |
| Probability mixture ε | 0.01 |
| Standardized Gaussian variance floor | 0.0025 |
| Expanded feature cap | q≤1000; report actual q and categorical response width |
| Point-fit budget | 300 seconds, checked cooperatively between batches |
| Repeats | Off by default; requested initial B=10, fraction=0.8, budget=600 seconds |

All are initial engineering settings, not empirical guarantees. The grid adds stronger shrinkage compared with the prior Codex plan, but remains finite and shared. Curvature rank is fixed rather than switching at N=300/p=40. This makes the procedure simpler to audit and benchmark.

Require unique column names and stable row identities. Reject constant variables with their names; never silently remove them. Record continuous columns with very few unique values for user review, without silently changing the declared type. Unknown categorical values are errors. Record rare categories and p≥N as diagnostics, not universal invalidity rules.

Persist configuration, schema, retained/excluded counts, data/row-identity digests, dependency versions, split seeds, code revision, and runtime/status metadata. Stability checks data identity before refitting. Raw participant data need not be retained in the result.

## 4. Feature and response specification

### 4.1 Continuous predictor block

On a training partition of m rows:

1. Compute training mean μ and population SD s; define linear predictor `l=(x−μ)/s`. Apply the same transformation to evaluation rows.
2. Fit `SplineTransformer(n_knots=5, degree=3, knots="quantile", include_bias=False, extrapolation="constant")` on training l. Keep actual output widths, not hardcoded widths.
3. Residualize spline columns on `[1,l]` using training least-squares coefficients; apply those coefficients to evaluation spline columns.
4. SVD the training residual matrix. Retain at most two right singular directions with singular values >1e-8 times the largest. If the largest is zero, retain none.
5. Project train/evaluation residual columns onto those directions. Center using training means. Divide each retained column by its training population SD and by `sqrt(κ*r)`, where r is the number retained.
6. Return `[l, curvature_columns]`, recentered using training column means for numerical precision. Do not subsequently normalize this whole block to unit variance.

The linear column has training variance one; total curvature variance is 1/κ. This incorporates Claude's linear preference while controlling total curvature capacity independently of the retained rank. A common isotropic ridge penalty on the scaled design implements the intended stronger curvature shrinkage.

When quantile knots coincide, use distinct training knots if at least two remain; otherwise keep only a nonconstant linear column. If the predictor is constant within this partition, return a zero-width block and a flag. This does not erase its pair rows. If a continuous response is constant within a training partition, that target/fold is unsupported.

No rank-normal transform is applied by default. Constant spline extrapolation does not imply the residualized curvature stays constant outside the training range, because the removed linear component still varies; record evaluation-range excursions instead of promising bounded extrapolation for the final block.

### 4.2 Categorical predictor block

Create indicators for **all declared levels**, not a reference category. Center with training prevalences and divide the entire block by

`sqrt(mean_rows(sum_columns(centered_block²)))`.

This makes total block variance one, avoids arbitrary reference-label dependence, and does not inflate each rare level independently. Rank deficiency is harmless with positive λ. Absent training levels retain their schema columns; a fully constant training block has zero width. Never infer categories from evaluation outcomes.

### 4.3 Response matrix

Concatenate all target response columns into T:

- Continuous target: one column standardized by training mean and population SD; preserve those for scoring on its original scale.
- Categorical target with C levels: all C indicator columns minus empirical training prevalences. Its unpenalized intercept is that prevalence vector. Do not response-standardize or class-weight it.

Let `S_j` be target j's predictor-column block and `R_j` its response-column indices. The full training feature matrix B contains every variable's block, including target-self blocks as a computational workspace. They must be removed before any target model is scored.

## 5. Shared ridge and exact omitted-variable fits

### 5.1 Numerical contract

For each training partition and λ solve

`min_beta ||T−B beta||_F²/(2m) + λ||beta||_F²/2`.

Let `A=BᵀB+mλI`, `H=A⁻¹`, and `beta=H BᵀT`. Factor A with Cholesky and use triangular solves. Obtain H by solving against the identity if required for block corrections; do not call a generic inverse. The sklearn reference uses `Ridge(alpha=m*lambda)` with matching centered design/intercept treatment. [Ridge documentation](https://scikit-learn.org/1.3/modules/generated/sklearn.linear_model.Ridge.html).

For an omitted column set S:

`beta^(-S) = beta − H[:,S] solve(H[S,S], beta[S,:])`.

For evaluation feature matrix E:

`prediction^(-S) = response_intercept + E beta − E H[:,S] solve(H[S,S], beta[S,:])`.

The retained rows solve the restricted normal equations and omitted rows are zero to numerical precision. This is an exact restricted fit for fixed λ, basis, centering, and scaling.

For target j, full model S=`S_j`; reduced model removing i, S=`S_j ∪ S_i`; select only response columns `R_j`. Never score the global self-containing workspace. Use the same equation on B to obtain training predictions and residuals. Handle intercept-only models directly, including p=2. A zero-width removed predictor gives identical full/reduced predictions and a degeneracy flag.

Selecting a different reduced λ or renormalizing retained blocks after deletion changes the procedure and defeats this specific reuse contract. Neither is allowed in the baseline.

### 5.2 Work sharing and cost

Build B, T, Gram matrix, and cross-products once per training partition. Process penalties sequentially. Cache `B H`, `E H`, and needed full predictions. Restrict each pair correction to its target response columns instead of applying it to every response. Batch pairs; do not allocate an N×p×p×C tensor.

With K=3, J=2, and five penalties there are at most `K*5*(J+1)=45` large factorizations per point fit, independent of target count. Inner folds evaluate only full target models. Outer folds factor only penalties chosen by at least one target. There remain p(p−1) directional comparisons and their small block solves.

Report costs honestly: factorization O(q³), cross-products and predictions depending on m/q/response width, and pair corrections depending on row count and block size. The improvement is removal of per-pair large factorizations, not a claim that all work is simply O(p²). q may exceed m; strictly positive ridge still makes the primal system solvable. Start with the primal implementation, q≤1000, and one BLAS thread in evidence runs.

Log factor count, expanded widths, phase timings, peak process memory, and fallback count. Symmetrize H before block extraction and check representative scaled normal-equation residuals. An isolated small-block failure may fall back to a direct restricted ridge solve, explicitly logged. If fallbacks exceed 1% of requested directional outer fits, stop as numerical failure; do not silently become the slow algorithm. No hidden λ/jitter changes.

The dual solver is a possible algebra-preserving optimization only if the cost pilot identifies this need within its one profiling pass. GCV is a change of tuning procedure and remains deferred. Do not implement both tuning systems in the baseline.

## 6. Scores, tuning, and aggregation

### 6.1 Continuous score

For each full or reduced model, compute standardized training residuals and

`v=max(mean(residual_train²), 0.0025)`.

For each evaluation row:

`logq=−0.5*[log(2πv)+(y_standardized−prediction)²/v]−log(training_response_SD)`.

Use each model's own training variance; never estimate it on evaluation residuals. This chooses the simple RSS/m convention from the earlier Codex plan, not Claude's effective-df correction. It can underestimate variance after fitting; held-out log scoring measures the practical consequence but does not eliminate the issue. Record floor hits and training/evaluation loss. Do not switch variance estimators per fixture or call either convention unbiased under shrinkage/misspecification.

### 6.2 Categorical score

Add empirical-prevalence intercepts to the ridge output, yielding raw class scores a_c. For a declared C-level target:

```text
pi_c = (training_count_c + 0.5) / (m + 0.5*C)
u_c = max(a_c, 0)
v_c = u_c / sum(u) if sum(u)>0 else pi_c
q_c = 0.99*v_c + 0.01*pi_c
logq = log(q_observed_level)
```

Both models use the same normalization convention. Probabilities must be finite, positive, and sum to one. Record negative-score clipping, zero-sum fallback, absent training levels, and levels with fewer than five training observations. This is a finite additive adaptation of LSPC, not multinomial logistic regression and not an inherited network-consistency result. [LSPC formulation](https://www.ms.k.u-tokyo.ac.jp/sugi/2012/IWSML2012.pdf).

Score an intercept-only baseline through these same response adapters. Report each node's full-versus-intercept held-out gain. Do not automatically delete all incident edges when that diagnostic is poor.

### 6.3 Cross-fitting

For each outer split:

1. Create shared inner splits within its training rows.
2. Refit transforms on each inner-training partition. For each λ compute target full-model predictions by removing the target's self block.
3. Select λ per target by mean inner held-out log score, weighted by evaluation row counts. No reduced-model search.
4. Refit transforms on the full outer-training partition. At the chosen target λ, obtain full and every reduced fit.
5. Accumulate held-out log-score differences and counts, with fold diagnostics.

Aggregate per-row sums, not equal fold means. After all folds, set `weight=(d_i_to_j+d_j_to_i)/2`. Preserve negatives. Both orientations must cover every intended outer evaluation row for an edge to be complete. Partial sums are diagnostic only and do not produce a displayed weight.

Use shared shuffled folds rather than different target-specific stratifications. Keep rare-level diagnostics visible. Cross-fitting does not make the score unbiased CMI or provide a calibrated per-row standard error.

## 7. Output and display contract

One row per unordered pair:

```text
node_i, node_j, gain_i_to_j, gain_j_to_i, weight_nats_raw,
display_magnitude_nats, gaussian_equivalent_magnitude,
orientation_gap, n_scored, folds_complete, status, diagnostic_flags
```

For complete pairs, display magnitude is `max(weight,0)` and Gaussian equivalent is `sqrt(-expm1(-2*display_magnitude))`; for incomplete pairs both are unavailable. Orientation gap is the absolute directional difference. No sign field is required. Status distinguishes `complete`, `unsupported`, `numerical_failure`, `budget_exceeded`, and `not_started`. No NaN-to-zero conversion.

Node tables include λ per fold, full/intercept scores, type-specific diagnostics, and prediction counts. Metadata records fitting provenance and completion. Preserve full pair tables even when exporting a filtered edge list.

`make_view` is a pure function, in this order:

1. Require complete status, w>0, and w≥`min_effect` (default 0).
2. If requested, require both directional gains >0.
3. If requested, require available stability≥`min_stability` for the exact effect/agreement rule.
4. Optionally apply a maximum edge count or top fraction, deterministically tie-broken by stable node names.

Label step 4 as presentation filtering. Make count and fraction mutually exclusive. Missing stability never passes a filter. Changing these arguments never calls the estimator. Export underlying fit ID, thresholds, agreement setting, repeat metadata, and presentation limits with every view.

Provide a basic unsigned plot, matrix, CSV pair table, node diagnostics, metadata JSON, and plain edge list usable by other graph packages. Width depends on unsigned magnitude. Avoid requiring a new layout library. Generate a methods paragraph describing the actual model, conditioning set, missingness, tuning, units, display filters, and limitations.

## 8. Optional repeated-refit stability

Implement the capability in the baseline package; do not execute it by default. B=10, fraction=0.8 initially. Sample retained independent rows without replacement and rerun preprocessing, tuning, and scoring with deterministic child seeds from `SeedSequence`.

Preflight also requires `floor(fraction*retained_N) >= 30`. Otherwise return an unsupported repeat request while preserving the valid point fit; do not silently change the fraction or lower the fitting minimum.

Store per-repeat/per-pair raw weight, both directional gains, status, seed, and fit identifier. This supports later changes to either effect or agreement filters without fitting. Stability is the number of passes divided by requested B, but only when that pair has B complete repeat estimates. Otherwise return unavailable with completion counts. Do not treat failed repeats as absent edges or change the denominator silently.

Preflight using roughly `1.5*B*point_fit_elapsed` as an initial conservative estimate. If beyond the supplied repeat budget, return `budget_not_started` and an estimate; the point fit remains usable. Never silently reduce B. Check deadlines between repeats and inside their point fits; export completed repeat records. Resuming validates data, config, seeds, and existing keys. Whole-fit process supervision is unnecessary.

Required unit checks: selection rules recalculate from saved directions; threshold changes do not refit; failed repeats do not masquerade as stability; samples contain no duplicates; seeds and resume keys are deterministic. Group sampling is outside this baseline's independent-row scope.

## 9. Implementation milestones and commands

### M1 — Correct shared numerical core

- [ ] Implement config/schema, features, responses, scores, and a slow direct restricted-ridge reference for tests.
- [ ] Implement shared factorization and exact block deletion.
- [ ] Test p=2, p=8, q>m, collinear indicators, rare/absent levels, and degenerate blocks. Compare full/reduced coefficients, training predictions, evaluation predictions, variances, and log scores against direct fits.
- [ ] Add an adversarial self-leakage test: the uncorrected workspace can predict its own target; the scored full model must instead match a model trained without the self block.
- [ ] Check categorical relabeling equivariance and finite normalized probabilities; check feature fitting is unchanged when evaluation values change.

Command after files exist: `python -m pytest tests/unit/cin/test_features.py tests/unit/cin/test_ridge.py tests/unit/cin/test_scores.py`.

Use around 1e-8 tolerances for well-conditioned double-precision comparisons; justify scaled residual tolerances for harder cases. Use deterministic analytic Gaussian CMI utilities and exact finite categorical calculations as oracle tests; do not require large N=20,000 stochastic recovery tests in the unit suite.

### M2 — End-to-end fit and early p=100 cost gate

- [ ] Implement nested fitting, aggregation, statuses, and runtime counters.
- [ ] Test held-out changes cannot affect an outer fold's training transforms or inner-selected λ; test row-weighted aggregation and complete-pair requirements.
- [ ] Add the cost runner and a local tiny smoke configuration. Freeze its charter and dispatch the eight cases in Section 10 through Actions.
- [ ] If necessary, allow one profiling-driven implementation pass; rerun only failed cases. No screening, category coercion, or dropped edges as a speed fix.

Command: `python -m pytest tests/unit/cin/test_fit.py tests/integration/test_cin_runners.py` plus `python -m mintnet.experiments.cin_cost --config configs/cin_cost_smoke.yaml --output results/generated/cin_cost_smoke` for correctness only, not published local timings.

Exit: all-pair completion and budget gates met on the declared runner. If p=100 remains too slow, record unsupported p=100 operation and stop broadening claims; a smaller-p preview is not completion of the original 100-variable objective.

### M3 — Researcher-usable output and optional stability

- [ ] Implement pure views, matrix/table/plot exports, node diagnostics, and methods text.
- [ ] Implement optional budgeted repeats with saved directional gains.
- [ ] Test nonexistent sign does not erase nonlinear magnitude; presentation limits never change the fit; unavailable stability never passes; interrupted work is visibly incomplete.
- [ ] Supply one continuous and one categorical/mixed example with explicit type schemas. Label item examples experimental until M4 passes.

Command: `python -m pytest tests/unit/cin/test_views.py tests/unit/cin/test_stability.py`.

Exit: fit once, adjust density, inspect/export evidence, optionally refit for stability. No UI application is required.

### M4 — Bounded statistical evaluation

- [ ] Implement the nine fixed cases and truth metadata below. Check positive definiteness, exact categorical truth, and observed versus latent graph semantics.
- [ ] Audit comparator status handling and freeze case definitions, metrics, defaults, and gates.
- [ ] Run 10 development replicates per case. Allow at most one global methodological correction, documenting a version change and updating the protocol before validation.
- [ ] Run 20 new validation replicates per case; do not reuse smoke/development seeds for acceptance.
- [ ] Produce one report with distributions, runtime, failures, scope outcomes, and no unsupported confidence claims.

Command: `python -m pytest tests/integration/test_cin_runners.py`; then the documented Actions dispatch. Material evidence is not a local unit-test run.

### M5 — Close and hand off

- [ ] Run relevant integration/regression checks and the CIN suite: `python -m pytest tests/unit/cin tests/integration/test_cin_runners.py`.
- [ ] Write user documentation, example commands, exact environments/configs/run IDs, and operating-scope conclusions.
- [ ] Append actual findings to the decision log; preserve historical results and charters.
- [ ] State whether the continuous preview, categorical branch, p=100 runtime, and low-N statistical claims passed individually.

Stop after the baseline decision. Optional extensions require a separate prioritized request or proposal; they are not unfinished baseline tasks.

## 10. Cost pilot

Eight one-dataset cells, same end-to-end default fit, one BLAS thread on a documented runner:

| Input | (p,N) | Purpose |
|---|---|---|
| Dense correlated continuous | (8,100), (30,100), (100,100), (100,300), (100,1000) | Small, broad, low-N and larger-N matrix costs |
| Five-level categorical | (30,150) | Ordinary item-level execution |
| Ten-level categorical | (100,200) | Maximum declared feature/response width stress |
| 50 continuous + 50 five-level categorical | (100,200) | Mixed adapter execution |

The categorical/mixed cost inputs need not carry network truth; do not score recovery against an invented graph. Record timings by phase, factorization count, peak RSS, q/response width, numerical fallbacks, and pair completion.

Initial gates: p≤30 fit≤30 s; p=100 fit≤180 s; peak process memory<1 GB; no ordinary failed pairs; at most 45 large factorizations. These are proposed targets, not measured results. Repeat a near-boundary timing once to distinguish gross timing noise, documenting both runs. A cost pilot is not a statistically precise speed comparison.

## 11. One bounded whole-network panel

### 11.1 Nine cases; no Cartesian explosion

| Case | N,p | Distribution / question |
|---|---|---|
| A | 100,8 | Sparse connected Gaussian conditional graph; small-network use. |
| B | 200,30 | Connected Gaussian graph with about 25% edge density; diffuse and strong edges. |
| C | 150,100 | Gaussian graph with a dense community and between-community links; broad low-N boundary. |
| D | 200,30 | Invertible monotone transform of B, e.g. `sinh(0.5*z)` on half the coordinates; exact zero-pattern preserved. |
| E | 200,30 | A connected 25-node nonlinear tree plus five independent distractors; mixed linear, saturating, and even-shaped conditional means with derivable truth. |
| F | 150,8 | Binary positive pairwise Ising joint, exactly enumerated. |
| G | 150,6 | Positive three-level pairwise categorical joint, 3^6 states exactly enumerated. |
| H | 150,8 | Observed binary parent with conditionally independent Gaussian children plus independent distractors; mixed-variable star with known observed truth. |
| I | 60,30 | Independent continuous/three-level variables; low-N null behavior. |

Total: 9×10 development + 9×20 validation = **270 core datasets**, before matched comparators. Include the historical organic fixture as a small regression smoke, not a tenth large campaign. Include one variance-only and one XOR demonstration outside recovery gates; their expected failures do not create new modeling requirements.

For Gaussian truth use a symmetric sparse weighted adjacency W and `Omega=I+aW`, with `a=0.8/||W||₂` or another fixed predeclared safe choice. Verify positive definiteness, graph connectivity/density, partial correlations, and analytic CMI. Randomize topology/weights by replicate within the case definition; pair B/D using the same underlying draw. Many dense-graph edges can be intrinsically weak: record population signal distributions before interpreting recall. Ensure A/B include edges with CMI≥0.01 using population checks before freezing, not method-result-driven graph selection.

For E draw a rooted 25-node tree with maximum depth three; each nonroot has exactly one parent. Set `X0~N(0,1)` and `Xk=a_k*g_k(X_parent)+epsilon_k` with independent nonzero-variance Gaussian errors. Assign a fixed, prespecified mix of linear `g(x)=x`, saturating `tanh(1.5*x)`, and even `2*x²/(1+x²)−1` functions across edges; use bounded coefficient/noise settings frozen from population properties. Add five independent distractors. Every joint factor involves only a parent and child, so its observed conditional graph is the tree for nonconstant links; there are no co-parent edges. Bounded nonlinear functions limit explosive propagation. Randomize the tree/assignments by replicate without changing the case's signal specification. This is a whole-network nonlinear test at p=30, not another two-variable demonstration. Avoid arbitrary nonlinear SEM edge lists: a moral graph is an upper bound on potential pairwise structure, with faithfulness/cancellation issues requiring care.

For F/G use `P(x) proportional to exp(sum node_potentials + sum pair_potentials)` with fixed bounded nondegenerate potentials; enumerate the joint, verify nonzero edge CMI, and sample independently. No MCMC study is necessary. For H take an observed Bernoulli variable H and children `Xk=a_k*H+epsilon_k`; factorization gives the observed star. This exercises both response orientations without claiming a discretized latent precision graph as truth.

These categorical statistical cases are small and exact; the wide categorical pilot tests cost only. High-p categorical recovery remains an evidence gap to disclose, not something inferred from Gaussian or runtime results.

### 11.2 Comparators and metrics

On continuous A–E compare the candidate with the **same scoring/tuning engine using linear-only predictor blocks**, plus the audited repository EBICglasso reimplementation on identical data. Do not call that reimplementation reference-verified against qgraph unless an actual reference comparison exists. Do not apply Gaussian comparators to categorical integer codes. Bayesian-network comparison is optional because its target differs.

Report per-case distributions/Monte Carlo uncertainty for:

- Complete pair counts, failures, timings, memory, prediction diagnostics and directional disagreement.
- Average precision (AP) over all pairs against observed conditional-edge truth; graph prevalence as the random-ranking baseline.
- Precision, recall, number displayed, and empty-view frequency at δ in {0,0.005,0.01,0.02}; optional both-positive rule reported separately.
- Gaussian/exact-categorical oracle CMI error, with the estimator's model-based interpretation stated.
- Recall of population-strong edges CMI≥0.01 where available, alongside all-edge precision/recall. Weak true edges remain true positives in all-edge precision.

For the all-null case I, AP is undefined: report positive weight quantiles/maxima and displayed fractions instead. Precision for an empty view is unavailable, not one. Comparator failures remain failures, not correct empty graphs. Report counts behind every mean.

Do not market 20 validation replicates as precise tail-error estimation or general FDR control.

### 11.3 Prespecified release gates

Freeze these proposed gates before validation:

1. All ordinary validation datasets complete within the point-fit budget, with valid probabilities/scores. Report all failures; no dropping difficult draws.
2. For A and B, mean AP exceeds mean edge prevalence by at least 0.20. Select one δ from {0.005,0.01,0.02} using development data only. At that δ, each case has mean all-edge precision≥0.70 over nonempty views, strong-edge recall≥0.50 over all replicates, and nonempty views in at least 80% of replicates. Ensure the declared strong-edge set exists before freezing.
3. For E, nonlinear mean AP exceeds the matched linear scorer by at least 0.10. This checks the intended nonlinear value proposition without claiming superiority to all other network methods.
4. F, G, and H each have mean AP at least 0.15 above prevalence. In F/G, mean full-model categorical held-out excess loss versus the intercept is no worse than 0.10 nats per node. These are initial utility gates, not general probability-calibration claims.
5. C must pass runtime/completion; its recovery quality determines the low-N/p=100 claim. D and I are mandatory descriptive boundaries, not cases to omit if disappointing.

If a gate fails after validation, report the corresponding scope as unsupported or unfinished; do not repeatedly tune against those seeds. A continuous preview may pass while item support fails. Failure of basic Gaussian utility or nonlinear gain means this proposed method has not yet earned release as the intended solution; calling it exploratory is not a substitute for utility.

### 11.4 Compute ceiling and stop rule

Cap pilot plus development plus validation plus comparator/repeat evidence at **12 aggregate runner-hours**, excluding installation. Estimate the panel using the pilot before dispatch. If necessary, lower replicate counts openly before freezing and label the report as reduced feasibility evidence; never silently remove hard cases. Keep actual counts in the report.

Use optional stability on only three prespecified validation datasets, from A, B, and F, B=10, subject to the same ceiling. Do not multiply the entire panel by resampling. Allow one profiling pass in the cost phase and one global methodological correction after development, then stop post hoc repair. No third large campaign is a baseline requirement.

## 12. Runner contract and evidence completeness

The existing generic workflow expects runner `load_config`, `expected_row_count`, `expected_combinations`, `COMBINATION_COLUMNS`, a CLI accepting config/output/shard selectors, and a companion reporting module exposing `write_report(raw, config, output_dir)`. Recheck signatures against current source before coding. Use case and replicate-batch axes with a small matrix; do not reproduce Claude's 225-shard proposed benchmark.

Derive seeds from stable full-grid identities and master seed; shards must equal unsharded results. Append/flush raw summary rows after each completed method/dataset, including failure rows. Persist config hash, charter hash, code revision, environment, and runner thread settings. Do not count repeated method rows as independent datasets.

Pair tables and repeat tables require their own manifests, duplicate-key checks, and aggregation. The existing summary CSV aggregator does not automatically validate or collect those extra artifacts. Prefer preserving the generic workflow and add runner/report-specific sidecar handling; change shared infrastructure only if actually necessary and covered by focused tests.

Integration tests must verify expected summary combinations, edge counts, deterministic seeds, sharded/unsharded equivalence excluding elapsed time, duplicate detection, incremental rows, and complete sidecars. Supply the exact verified Actions dispatch command in the implemented user/developer guide, using the final runner flags; a speculative command in this planning document is not an executable deliverable.

## 13. Deferred features and completion contract

Nice-to-haves: continuous normal-score sensitivity, curvature-ablation plots, unsigned Gaussian-equivalent UI sliders, marginal predictive-information networks, GCV/dual optimization, ordinal-order models, richer continuous densities, declared interactions, formal conditional-null inference, multiple imputation, clustered/time-series estimands, group comparison, centrality uncertainty, and causal extensions.

If adding curvature ablation later, for target j omit `S_j` plus only predictor i's curvature columns. Its score gain is not an additive MI component and may exceed total omission gain. If adding a marginal network, label it a separate model-based target, never a conditional screening mask or mediation estimator. If adding normal scores, specify unseen-value mapping and its actual invariance limitations. If adding sign, keep it separate from magnitude and never use unknown sign as zero weight.

Baseline is complete when the numerical and integration contracts pass, the measured cost/utility scope is recorded honestly, exports and optional stability work, the intended input-type claims are supported or explicitly withheld, and the user guide lets another researcher reproduce a fit and its displayed view. It is not complete merely because the smoke looks attractive, nor incomplete because nice-to-haves remain unbuilt.
