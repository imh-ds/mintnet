# Final methodology outline: exploratory conditional predictive-information networks

Date: 2026-09-19. Status: final consolidated **build specification**, not a validated method or a claim that implementation is complete.

Read next: [technical implementation roadmap](technical_implementation_roadmap_2026-09-19.md). Supporting record: [feasibility smoke review](feasibility_review_2026-09-19.md).

This specification supersedes the earlier Codex and Claude network guidelines and roadmaps used during consolidation. Those source-review artifacts are not active build specifications, and executors do not need to reconcile them again. Other salvage and mediation plans remain separate.

## 1. The final decision

Build a practical, undirected, weighted map of **conditional predictive information** among measured variables. Fit restrained nonlinear node models, measure each variable's held-out contribution after accounting for the other included variables, and average the two prediction orientations for each pair. Compute all pairs through shared ridge algebra. Keep estimation separate from the graph's visible density.

The intended audience is psychology and behavioral-science researchers conducting exploratory theory development with independent-participant, cross-sectional data. The computational design covers 2–100 variables. The main statistical use case is a modest number of construct scores or questionnaire items with enough observations to distinguish meaningful associations. Low-N, high-p input must be usable and transparent, but no arbitrary dense 100-node graph can be reliably recovered from a small sample by changing estimators alone.

The product should answer: **Which measured variables offer useful conditional predictive information about one another, under an explicitly stated modeling procedure, and which relationships remain visible under stricter effect or reproducibility filters?**

It should not require a causal order, a sparse graph, exhaustive conditioning-subset search, or a formally significant edge before a relationship can be explored.

## 2. Why this consolidation is different

Both plans agree on the right architectural change: fixed full-versus-reduced comparisons replace the old combinatorial search. Claude additionally supplied a useful working prototype and emphasized a linear preference with modest nonlinear flexibility. The Codex revision emphasized global computation sharing, observed categorical probability models, and separate display controls.

The final choices are:

| Topic | Final baseline decision |
|---|---|
| Estimation target | All-other-variables conditional predictive information, motivated by conditional MI; undirected output. |
| Continuous predictor model | One linear term plus at most two orthogonalized spline-curvature terms, with stronger regularization of curvature. |
| Continuous response model | Gaussian conditional mean model on the declared continuous scale, with model-specific constant residual variance. |
| Questionnaire categories | Explicit categorical probability model for binary, ordinal, and nominal responses; no five-category Gaussian shortcut. |
| Computation | One shared multiresponse ridge system per training partition and candidate penalty; exact self-block and pair-block deletion. |
| Tuning | Small training-only inner log-score grid, shared computationally across targets. Full and reduced models for a target use the same selected penalty. |
| Normal-score transforms | Optional future sensitivity analysis, not a mandatory transformation or an ordinal-data solution. |
| Shadows and per-row score ratios | Optional future diagnostics, not confidence or baseline edge thresholds. |
| Default graph | All complete positive weights, explicitly labeled an unfiltered exploratory view. |
| Density controls | Minimum effect, optional agreement in both orientations, optional resampling stability, and clearly labeled presentation limits. |
| Association sign | No baseline signed edge weight. Keep magnitude when a sign is undefined. |
| Validation | Early p=100 end-to-end cost pilot, then one small frozen whole-network panel with a total compute ceiling. |

This combines compatible ideas rather than implementing both engines side by side. The final defaults differ from Claude's prototype and require their own bounded evaluation.

## 3. What the smoke test establishes

Claude reports close numerical agreement between selected exact block deletions and direct refits (maximum coefficient discrepancy 7.8e-16), strong ranking on the historical 18-variable fixture (AUC 0.999 at N=300), and a U-shaped example detected by curvature but missed by a linear model. Its restrictive display rules improve precision at a substantial recall cost on three seeds per N. These are useful reasons to pursue the architecture.

They do not establish final p=100 runtime, mixed/ordinal-data validity, a calibrated confidence threshold, performance on varied dense graphs, or the performance of this final candidate. The one-node timing probe is an extrapolation, not an end-to-end run. The final [smoke audit](feasibility_review_2026-09-19.md) records code-level qualifications, the source hash, reported results, and the inability to independently rerun the script with the current local Python environment.

The strongest practical lesson is that good ranking can coexist with many false displayed edges. Preserve weights and make the display tradeoff explicit; do not relabel a successful fixture-specific threshold as universal confidence.

## 4. Statistical target and honest terminology

The ideal information-theoretic quantity is

`C_ij = I(X_i; X_j | X_{-ij})`.

For target j, the full model includes every other measured variable. The reduced model also omits i. Using the same held-out rows, calculate

`d_(i→j) = mean[log q_full,j(X_j | X_-j) − log q_reduced,j,i(X_j | X_-ij)]`.

Then `w_ij = (d_(i→j) + d_(j→i))/2`. The arrow is prediction orientation, never a causal arrow. Weight units are nats per observation. Negative estimates are preserved in exports; only display magnitude is clipped at zero.

For fitted distributions, expected log-score gain equals

`CMI − E KL(true_full || fitted_full) + E KL(true_reduced || fitted_reduced)`.

Thus the implemented weight is a model-based estimate, affected by misspecification, regularization, tuning, and sampling. A positive value does not itself reject conditional independence. Separate fitted node conditionals need not define a compatible joint distribution. Call the result a **conditional predictive-information network**; reserve “true CMI” for the ideal target or an analytic oracle.

In a multivariate Gaussian population, `CMI = −0.5 log(1−partial_r²)`. An optional unsigned display transform is

`gaussian_equivalent_magnitude = sqrt(1−exp(−2*max(w_ij,0)))`.

This is an analogy outside Gaussian populations, not a signed partial correlation or a universally calibrated nonlinear effect size. It must never be multiplied by an unknown sign and thereby set to zero. Nats remain the primary reported unit.

## 5. Model scope

### Continuous scores

Use explicitly declared continuous variables, including defensible composite/scale scores. Training-only standardization handles units. A linear-plus-curvature basis allows smooth departures from linear conditional means while preferring simpler relationships at limited N. Fixed low curvature rank prevents an uncontrolled model-size search.

The baseline does not generally capture variance-only dependence, arbitrary multimodal conditional distributions, or interactions that only appear jointly, such as XOR. Its Gaussian response approximation can be poor for extreme skew, severe floor/ceiling effects, or counts. Report residual/prediction diagnostics. Do not describe it as invariant to all marginal transformations.

A normal-score sensitivity mode may later help continuous skewed data, motivated by Gaussian-copula modeling, but changes the finite-sample fitted procedure. Population invariance under invertible transformations does not validate every empirical transformation or Gaussian approximation. [Nonparanormal framework](https://www.jmlr.org/papers/v10/liu09a.html).

### Binary and ordinal items

Require explicit category levels. Treat ordinal items categorically in the initial adapter; their order remains metadata, and equal spacing is not assumed. Predictor indicator blocks and indicator response columns use the same ridge solver. Convert class scores to positive normalized probabilities before log scoring.

This probability adapter uses the least-squares probabilistic classification idea. It is computationally compatible with exact omission, unlike treating one logistic IRLS step as an exact reduced refit. The particular additive model and smoothing rule still require validation. [LSPC authors' formulation](https://www.ms.k.u-tokyo.ac.jp/sugi/2012/IWSML2012.pdf).

Observed categorical support is a **required candidate capability** for the intended behavioral-science product, not something to claim from a continuous prototype. If its bounded tests fail, a continuous-score preview may be released explicitly; the full item-level baseline remains incomplete. Do not silently recode failed categorical cases as continuous.

### Missingness and dependence between participants

Default to an input error on missing values. Permit explicitly requested global complete-case analysis, with excluded rows and retained N reported. No automatic pairwise deletion or imputation. Complete-case analysis does not remove missingness bias by itself.

The initial estimand assumes independent rows. Group-aware splitting can prevent some leakage but does not create a valid multilevel, longitudinal, or within-person model. Multiple imputation, repeated-measures models, and survey weights require separately specified analysis and uncertainty semantics; they are not minor checkbox additions.

## 6. Dense networks and low sample sizes

Every unordered pair receives an estimate or an explicit failure status. Ridge permits dense coefficients; no mandatory neighborhood cap or sparse selection rule excludes potential edges. The graph can therefore represent dense weighted relationships without searching increasingly large conditioning subsets.

Nevertheless, conditioning on many redundant variables can make each one's unique contribution weak or unstable. That can be scientifically appropriate. A sparse visible graph is not automatically an implementation failure, and a dense visible graph is not proof of a rich causal system.

Initial input limits are 2≤p≤100 and retained N≥30; the lower bound is an engineering guard for splitting, not a recommended sample size. The evaluation includes N=60, 100, 150, 200, and larger runtime probes. There is no universal N/p validity rule. Show retained N, p, rare-category counts, model predictive performance, and optional stability so the researcher can assess the result.

For p near 100, a matrix and sortable edge table are required alongside a graph drawing. Researchers may choose a top-count or top-fraction display to make a figure readable. This must be marked as presentation filtering, not evidence-driven discovery or a refitted sparse network.

## 7. Researcher-facing controls

1. Declare variables/types and missingness handling; fit the weighted network once.
2. Inspect the estimated landscape, diagnostics, and complete edge table.
3. Adjust the minimum effect threshold in nats. Optionally require both directional gains to be positive.
4. If desired, request budgeted repeated subsampling and filter by repeat selection frequency.
5. Export the fit, view settings, displayed edges, and methods text.

Provide named views with literal meanings:

| View | Rule and interpretation |
|---|---|
| Landscape | All complete edges with w>0; no statistical-confidence implication. |
| Effect-filtered | Landscape plus w≥δ; δ is the researcher's relevance threshold. |
| Agreement-filtered | Effect-filtered plus both directional gains >0; can hide asymmetric nonlinear/model-misspecified relationships. |
| Stable subset | A chosen effect/agreement rule plus a minimum frequency in completed repeated refits. |
| Presentation limit | An optional count/fraction limit after the preceding filters; no scientific-confidence claim. |

There is no validated universal δ. The UI may show example values, but must not call 0.01 nats a significance threshold. Changing these views cannot change fitted weights. Changing included variables, type declarations, transformations, basis, or tuning requires a new fit.

Use unsigned widths, and optional opacity for available stability. No causal arrows, default centrality rankings, or signed red/blue interpretation. A curvature-removal diagnostic, if requested later, is extra predictive value from those basis terms, not a decomposition of MI or a percentage nonlinear.

## 8. Optional stability in the baseline package

The software must support repeated-refit stability, but ordinary point fitting defaults to no repeats. Initial requested setting: B=10 subsamples of 80% of retained participants without replacement; refit preprocessing, tuning, and scoring independently each time.

Store both directional gains for every repeat/pair. For any chosen effect/agreement rule, stability is the fraction of all B requested complete refits where the edge passes. Changing display thresholds recomputes this fraction without refitting. If any required pair estimate is incomplete, that pair's stability is unavailable; show the completion count.

This is reproducibility under a specified subsampling procedure, not an edge-existence probability, p-value, confidence interval, or FDR. Ten repeats have 0.1 resolution. Higher B is optional and budgeted. Point results remain usable if a repeat request is declined by preflight or interrupted.

## 9. Need-to-have baseline and nice-to-haves

| Required to call the baseline complete | Optional after the release decision |
|---|---|
| Shared all-pair solver, exact full/reduced fits, no self leakage | Dual/GCV acceleration if measured performance demands it |
| Linear-leaning nonlinear continuous models | Normal-score sensitivity, richer densities, location/scale models |
| Validated categorical candidate or explicitly incomplete item support | Ordinal-order efficiency or a validated logistic replacement |
| Training-only preprocessing/tuning and correct score aggregation | Declared predictor interactions |
| Effect/agreement/display controls without refitting | Marginal predictive-information overlay, shape plots, curvature diagnostics |
| Optional budgeted repeated-refit stability | Formal uncertainty or conditional-null inference |
| Explicit failures, runtime budget, metadata, complete tables | More advanced parallelism or long-run checkpoint systems |
| Missingness/type audit, simple plots, portable CSV/matrix exports | Interactive app, communities, centrality and their uncertainty |
| Early p=100 runtime test and one bounded statistical panel | Larger confirmatory/publication benchmark |
| Clear methods text and operating-scope report | Imputation, clustered/time-series models, group comparisons, causal extensions |

Marginal and conditional information can differ through mediation, redundancy, synergy, conditioning, or model error. A later marginal overlay must not call their difference a mediated effect or use it to screen conditional edges.

Do not orient a displayed conditional graph by feeding it directly to a DAG algorithm: conditional Markov graphs and DAG skeletons differ, including co-parent edges. Larger N alone does not resolve that distinction. Any causal extension is a new design with its own assumptions.

## 10. What success means

The method should run in seconds to a few minutes through p=100 on the stated reference runner, preserve dense weighted output, recover useful whole-network patterns in moderate-N cases, and demonstrate a relevant nonlinear improvement over a matched linear scorer. Gaussian EBICglasso remains a strong comparator in its own regime; Bayesian networks are not inherently restricted to linear models. This project offers a different exploratory tradeoff, not universal superiority.

Use eight one-dataset cost probes followed by nine prespecified statistical cases, with 10 development and 20 fresh validation replicates each. Cap aggregate evidence compute and allow one global development correction before validation. Include exact categorical truth, a mixed-variable case, a low-N null case, and dense p=100 stress. The roadmap supplies the equations, contracts, gates, and stop rules.

Do not turn every failed scope demonstration into another specialized model. If the core fails, narrow or decline the release claim. If it succeeds, finish the baseline and stop; optional extensions do not reopen completion indefinitely.
