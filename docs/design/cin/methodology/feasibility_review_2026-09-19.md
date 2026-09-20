# Feasibility smoke review and consolidation decisions

Date: 2026-09-19. Companion documents: [final methodology](methodology_outline_2026-09-19.md) and [final implementation roadmap](technical_implementation_roadmap_2026-09-19.md).

## 1. Evidence reviewed

Reviewed both consolidated Codex documents, both consolidated Claude documents, and Claude's complete feasibility script. The smoke results were reported in Claude's guideline, Section 8. Those local source-review artifacts are provenance for this consolidation, not the final implementation specification.

Inspected script SHA-256:

`D970483811A0AD1A748DFFAB981DBDA411A155031675DCA4CC9558F1D3858337`

Repository HEAD at review: `069c10e`. No separate raw run logs or environment manifest accompanied the smoke script in the reviewed network folder. This review treats the numbers as **Claude-reported smoke results supported by inspectable code**, not independently reproduced benchmark evidence. The local `.venv/Scripts/python.exe` could not launch its referenced base interpreter; `py -0p` reported no installed Pythons. No dependencies were installed and no new statistical campaign was run for this consolidation.

## 2. What the script actually implements

The engine uses five shared outer folds, training-fitted interpolated rank-normal transforms, one linear plus four curvature columns per variable, curvature scaling by `sqrt(10)`, and a 36-value GCV ridge grid. It fits a separate eigensystem for each target/fold. Predictor blocks are correctly built once per variable/fold. Reduced fits use an exact block identity, with model-specific residual variance divided by `n_train − trace(hat_matrix)`.

Six globally permuted shadow variables are appended to the 18 measured variables. Shadows enter the conditioning models and are themselves fitted as responses. The real-shadow score distribution supplies the 95th-percentile threshold. The script also computes directional agreement, curvature-removal gains, linear coefficient signs, and a per-row score ratio.

Three execution modes exist:

| Mode | Actual scope |
|---|---|
| Default | One N=300 historical organic draw: 14 connected variables, 21 edges, four independent distractors, six shadows; selected block-deletion comparisons; transformed twin; a locally altered U-shaped example. |
| `--rules` | Three draws each at N=150, 300, 750 on the same graph topology; compares several display rules. |
| `--cost-probe` | One target/fold at total p=30 and p=120, N=300, independent Gaussian input, full five-column blocks. Extrapolates to a whole run. |

The script fixes curvature rank at four even for N=150 and wide inputs. It therefore does not test the proposed production auto-rule using rank two in those regimes. It implements neither the proposed dual solver nor the final consolidated shared multiresponse solver. Its categorical, stability, and production API paths do not exist.

## 3. Useful findings to retain

| Reported result | What it supports | What it does not establish |
|---|---|---|
| Maximum direct-versus-deletion coefficient difference 7.8e-16 | Excellent numerical agreement for the tested subsets of this well-behaved fixture | Every omitted block, every variance/trace calculation, categorical fits, q>N failures, or the final global self-block deletion implementation |
| AUC 0.999 at N=300 | The prototype ranks the historical fixture's true edges highly | Precision at an arbitrary threshold, performance on new topologies, or superiority to a matched comparator |
| Balanced rule: precision 0.90–1.00, recall 0.43–0.57 at N=150; precision 0.89–0.94, recall 0.76–0.90 at N=300 | Display restrictions can trade recall for precision on these draws | A calibrated confidence level, guaranteed precision, or validated default settings on other datasets |
| U-shaped pair: linear score −0.002, nonlinear score 0.015 nats; curvature gain 0.017 | A restrained nonlinear basis can reveal a relation missed by a linear mean model | Validated recovery of the modified entire graph, or an additive decomposition of MI into linear and nonlinear portions |
| One node/fold approximately 12 ms at p=30 and 0.6 s at p=120 | Large-matrix work matters; exact deletion is a worthwhile optimization | Measured end-to-end p=100 runtime including preprocessing, tuning, all scores, diagnostics, exports, or repeats |

The direct-refit check is restricted by `idx < 3`; it does not compare every predictor removal as the introductory comment suggests. The cost probe excludes feature construction from its timed region and omits several engine operations, including curvature scoring and reduced variance calculations. Treat its whole-network timing as an extrapolation only.

The reported EBICglasso number used a similar earlier draw, not the identical smoke dataset. Do not present it as a paired comparison.

## 4. Corrections required before reuse

### A. Interpolated normal scores are not exactly transformation-invariant

The roadmap proposes exact invariance for `np.interp` applied between training values. That property does not hold. With training values `[0,2]`, assigned probabilities `[0.25,0.75]`, and held-out value `1`, interpolation gives 0.5. Cubing all values gives training `[0,8]`, test `1`, and probability 0.3125. Applying the inverse normal CDF preserves the difference. This deterministic arithmetic counterexample was checked during consolidation.

Training ranks themselves are preserved under strictly increasing transformations. The gap is the interpolation for unseen values, not the population MI invariance theorem. An order-only empirical mapping could have a different invariance contract, but finite step maps are not automatically invertible population transforms. Remove the exact-invariance tests proposed for the supplied implementation. [NumPy documents `interp` as piecewise linear interpolation](https://numpy.org/doc/stable/reference/generated/numpy.interp.html).

### B. Five categories do not become a continuous Gaussian response after ranking

An injective relabeling of categories preserves their information, but it does not turn probability masses into a Gaussian density. Neither five categories nor tied normal scores establishes a valid categorical conditional likelihood. Consequently the smoke engine cannot validate item-level ordinal CMI. The final candidate uses explicit category probabilities at every category count, including five and seven levels.

Likewise, a latent Gaussian precision graph is not generally the conditional-independence graph of its categorized observations. The proposed ordinal benchmark's latent graph cannot serve as exact observed-network truth. Use finite categorical joints with calculable observed truth; retain discretized Gaussian data only as descriptive measurement-sensitivity examples.

### C. The per-row ratio is not a standard error of the fitted procedure

`std(per_row_gain)/sqrt(N)` treats the score contributions as if their relevant sampling dependence were captured by row dispersion. Cross-fitted scores share fitted and tuned models across overlapping training sets. This formula does not establish the sampling variance of the network estimator. The problem is broader than a boundary at zero.

If retained later, call it a descriptive score-dispersion ratio. Do not call it confidence, a z-score, a p-value, or a replacement for refitting-based stability. No baseline default will depend on 1.5 or 2 as if those were calibrated cutoffs.

### D. Shadows do not calibrate conditional-null edges

Permuted copies retain marginal distributions and can show a useful noise reference, but finite permutations need not be exactly independent, and they do not reproduce correlated-nuisance leakage on real conditional-null pairs. The smoke already demonstrates this limitation through low precision from the shadow threshold alone.

Appending shadows also changes finite-sample real-real fits and the variables being conditioned on; toggling them is not a display-only action. Permuting the full dataset before splitting can place held-out participant values into training shadow columns, violating the strict training-data boundary desired for the final pipeline. Any later shadow diagnostic needs a separately specified, fold-safe construction and cannot silently modify the baseline fitted graph. Boruta is a useful reference for shadow-feature ideas, not a calibration proof for this estimator. [Original Boruta paper](https://www.jstatsoft.org/article/view/v036i11).

### E. Separate magnitude, sign, and curvature evidence

Claude's proposed `r_equiv = sign * sqrt(1-exp(-2*max(C,0)))` becomes zero when the sign is unknown. Its later absolute-weight filtering and edge widths would then hide exactly the nonlinear edges the method is meant to reveal. The final display magnitude is always unsigned; unknown direction of association never means zero information.

Curvature-removal gain can exceed total omission gain, as 0.017 versus 0.015 already illustrates. It can also be negative. It is a model comparison, not a component constrained between zero and total information. Do not report “percentage nonlinear” or subtract it to recover a unique linear MI component.

### F. Smoke results belong to the tested procedure

The final basis normalization, tuning, number of folds, scoring, absence of shadows, and categorical adapter differ from the smoke. No reported precision, recall, runtime, or null threshold transfers automatically. Reuse the math reference and historical fixture; run the final candidate on new whole-network cases.

## 5. Adjudication for the final plan

Adopt Claude's explicit linear-plus-curvature structure, heavier curvature regularization, exact omission reasoning, orientation diagnostics, practical export emphasis, and evidence that display restrictions require an explicit recall tradeoff. Adopt the Codex shared all-variable ridge algebra, proper categorical probability route, immutable fitted weights, budgeted optional stability, and small bounded panel.

Choose a single small inner log-score grid for the baseline, rather than combining GCV and categorical tuning as separate procedures. Defer GCV/dual acceleration unless profiling establishes a need. Use a fixed two-curvature-column candidate, avoiding an N/p discontinuity and an additional tuning problem. Both choices remain unvalidated engineering decisions.

Do not adopt shadows, per-row confidence presets, signed MI magnitudes, automatic Gaussian treatment of Likert items, mandatory marginal networks, or a large Cartesian benchmark. Claude's proposed 5×3×3×50 benchmark is 2,250 datasets before comparators; the final panel has 270 core datasets plus a small cost pilot and explicitly capped repeat checks.

The final pair of documents is self-contained and supersedes both previous consolidated build plans. This audit preserves the useful existing work without overstating its evidential reach.
