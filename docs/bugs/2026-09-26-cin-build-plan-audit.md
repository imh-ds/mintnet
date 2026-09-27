# CIN build-plan implementation audit

Audit date: 2026-09-26. Scope: all task plans 01–12 in `docs/design/cin/build-plan/`, the active CIN estimator, simulations, runners, scripts, tests, charters, and decisions D-092–D-106. The original findings below describe behavior at audit time; the status and fix updates track later changes. Hosted validation evidence remains frozen.

Priority convention: P1 affects result integrity, availability, or evidence acceptance; P2 is a material contract or reporting gap; P3 is lower-impact exactness. Reproduction probes used small fabricated or synthetic inputs. The full local suite on repository Python 3.11 finished **277 passed, 1 failed, 3 warnings in 233.30 s**; BUG-23 describes the failure. Passing tests do not establish the correctness of untested branches described below.

Follow-up verification on 2026-09-26 used Python 3.12.14: **297 passed, 1 failed, 3 skipped in 202.78 s**. The one failure is the existing BUG-23 cost-ledger snapshot assertion; the three skips require optional matplotlib. This run includes the BUG-04–11 regression tests. The focused fit, view, and stability suites passed (61 tests, with three optional matplotlib skips); Ruff and `git diff --check` passed for BUG-09–11.

Follow-up verification for BUG-12–15 used Python 3.12.14: the final full suite reported **312 passed, 1 failed, 3 skipped in 183.07 s**. The sole failure remains the existing BUG-23 cost-ledger snapshot assertion; the skips require optional matplotlib. The focused panel-selection/gate and shard-equivalence tests passed (25 tests); Ruff and `git diff --check` passed. The implementation is committed as `d69e457`.

The hosted Task 11 result recorded in D-106 remains frozen: 396/400 complete rows, two incomplete rows, two generation errors, and failed completion and E nonlinear-gain gates. A/B/F/G/H/C conclusions should be revisited after correcting gate semantics, but the historical table must not be silently rewritten or validation retuned. D/I and high-p categorical outcomes remain descriptive or unsupported as recorded. The original plan proposed stability on three validation CIN datasets, whereas the frozen charter says broadly A/B/F and the runner evaluates more; resolve and disclose this scope ambiguity rather than treating it as proof of a false statistical result.

| Issue | Priority | Theme | Short description | Status | Related commits |
| --- | --- | --- | --- | --- | --- |
| [BUG-01](#bug-01) | P2 | Input contracts | Reject exact constant decimal inputs and training partitions | Fixed | `48d4b75`, `b50b69b` |
| [BUG-02](#bug-02) | P2 | Input contracts | Reject complex values before lossy float conversion | Fixed | `3d5b8cf` |
| [BUG-03](#bug-03) | P2 | Input contracts | Match equivalent NumPy and Python category strings | Fixed | `e1081f9` |
| [BUG-04](#bug-04) | P1 | Fit and stability | Return an incomplete fit when tuning is interrupted | Fixed | `7e79b96` |
| [BUG-05](#bug-05) | P1 | Fit and stability | Keep valid pair stability when another pair is unsupported | Fixed | `97afd2a` |
| [BUG-06](#bug-06) | P1 | Fit and stability | Validate all completed-repeat records and seeds on stability resume | Fixed | `3b739ca` |
| [BUG-07](#bug-07) | P2 | Fit and stability | Keep point-fit evidence if optional stability errors | Fixed | `71aea51` |
| [BUG-08](#bug-08) | P2 | Fit and stability | Complete required continuous-node diagnostics | Fixed | `825bfc7` |
| [BUG-09](#bug-09) | P1 | Persistence and methods | Preserve schema order when saving fits and stability | Fixed | `8c4dd7e` |
| [BUG-10](#bug-10) | P3 | Persistence and methods | Restore exact float64 CSV round trips | Fixed | `8c4dd7e` |
| [BUG-11](#bug-11) | P2 | Persistence and methods | State the stability cutoff in methods text | Fixed | `8c4dd7e` |
| [BUG-12](#bug-12) | P1 | Statistical evidence | Compute selected-threshold strong-edge recall correctly | Fixed | `d69e457` |
| [BUG-13](#bug-13) | P1 | Statistical evidence | Require each named case to pass validation gates | Fixed | `d69e457` |
| [BUG-14](#bug-14) | P1 | Statistical evidence | Enforce the Case C point-fit runtime threshold | Fixed | `d69e457` |
| [BUG-15](#bug-15) | P1 | Statistical evidence | Validate development identities before freezing delta | Fixed | `d69e457` |
| [BUG-16](#bug-16) | P2 | Statistical evidence | Use paired B/D dataset seeds in the runner | Open | — |
| [BUG-17](#bug-17) | P2 | Statistical evidence | Count isolated nodes in population edge density | Open | — |
| [BUG-18](#bug-18) | P2 | Statistical evidence | Average categorical excess loss over categorical nodes only | Open | — |
| [BUG-19](#bug-19) | P1 | Aggregation and sidecars | Support the prescribed phase-only aggregation sequence | Open | — |
| [BUG-20](#bug-20) | P1 | Aggregation and sidecars | Stage validated panel sidecars before writing reports | Open | — |
| [BUG-21](#bug-21) | P1 | Aggregation and sidecars | Reject mixed shard provenance and retain environment details | Open | — |
| [BUG-22](#bug-22) | P1 | Aggregation and sidecars | Validate pair identities and requested stability repeat coverage | Open | — |
| [BUG-23](#bug-23) | P2 | Aggregation and sidecars | Update the cost ledger test for later dispatches | Open | — |
| [BUG-24](#bug-24) | P2 | Documentation and reporting | Produce the declared descriptive statistical-panel report | Open | — |
| [BUG-25](#bug-25) | P2 | Documentation and reporting | Complete the Task 12 researcher guide and close-out | Open | — |

## Input contracts

### BUG-01: Reject exact constant decimal inputs and training partitions

**Priority:** P2. **Source:** `src/mintnet/cin/config.py:294; src/mintnet/cin/features.py:132,301`. **Build plan:** Task 01–02.

**Erroneous behavior and reproduction.** `np.full(30, 0.1)` is accepted as a continuous column because NumPy reports SD `2.78e-17`. On a 20-row training partition its SD is `1.39e-17`; the feature builder retains predictor and response columns, flags no constant, and standardizes the constant response to -1. A globally varying column with a constant training partition also bypasses the partition guard.

**Cause and impact.** The checks equate `sd == 0` with exact constancy, which floating-point centering does not guarantee. This violates global rejection and can scale held-out values by roundoff.

**Recommended revision.** Detect exact constancy from values before SD-based scaling in all three paths. Keep genuine small nonzero variation valid.

**Regression check.** Test decimal constants at several N, a globally varying column constant only in training rows, and small legitimate variation.

**Fix update (2026-09-26).** Commit `48d4b75` added failing regression tests for exact decimal constants and a constant training partition, plus a control for small real variation. Commit `b50b69b` replaced the global SD-equality check with an exact min/max check and makes predictor and response fitting identify constant training values before scaling. Constant partitions now have zero-width predictor and response blocks with their existing flags. The focused config, feature, and fit suites passed (94 tests). The full active suite finished with 282 passed and one failure: the unchanged cost-ledger assertion tracked separately as BUG-23.

### BUG-02: Reject complex values before lossy float conversion

**Priority:** P2. **Source:** `src/mintnet/cin/config.py:283–291`. **Build plan:** Task 01; D-095.

**Erroneous behavior and reproduction.** A column `np.arange(30)+1j*np.arange(30)` is accepted with only a ComplexWarning; prepared data contains just the real sequence.

**Cause and impact.** Casting to float discards imaginary components; the losslessness check covers integral inputs only. The fit uses altered observations.

**Recommended revision.** Reject non-real complex values before casting, naming the affected variable.

**Regression check.** Complex dtype and object scalars with nonzero imaginary parts must error; real numeric data must still work.

**Fix update (2026-09-26).** Commit `3d5b8cf` checks parsed continuous values for a complex dtype before converting to float64. Inputs with nonzero imaginary components now raise a variable-named `ValueError`; complex representations with an all-zero imaginary component are converted to their real values. Added regression coverage for both complex NumPy arrays and complex object columns, plus the zero-imaginary control. The focused numeric-conversion tests passed (6 tests). The full active suite finished with 285 passed and one unrelated stale ledger assertion (BUG-23); three existing matplotlib deprecation warnings remain.

### BUG-03: Match equivalent NumPy and Python category strings

**Priority:** P2. **Source:** `src/mintnet/cin/config.py:50`. **Build plan:** Task 01.

**Erroneous behavior and reproduction.** Observed builtin strings `['a','b']*15` are rejected as unknown if declared levels are `list(np.array(['a','b']))`; builtin-string levels succeed.

**Cause and impact.** Category keys embed the scalar's concrete module/type, so equal `np.str_('a')` and `'a'` do not match.

**Recommended revision.** Canonicalize equivalent NumPy scalars or use equality-based matching while retaining intentional `True` versus `1` separation.

**Regression check.** Check NumPy/Python strings both ways, cross-type duplicate levels, and boolean/numeric separation.

**Fix update (2026-09-26).** Commit `e1081f9` normalizes NumPy Unicode scalars to builtin Python strings when constructing categorical keys. Observed values and declared levels now match in either direction, and mixed NumPy/Python duplicate levels are rejected. The numeric-category key path remains separate, preserving the `True` versus `1` distinction. Added tests for both matching directions and duplicate rejection. Focused config tests passed (7 tests). The full active suite finished with 288 passed and one existing stale ledger assertion (BUG-23); three existing matplotlib deprecation warnings remain.

## Fit and stability

### BUG-04: Return an incomplete fit when tuning is interrupted

**Priority:** P1. **Source:** `src/mintnet/cin/fit.py:971–972,1008–1026`. **Build plan:** Task 05 §8.

**Erroneous behavior and reproduction.** Injecting `BudgetExceeded` from `tune_lambdas` yields `UnboundLocalError` when the catch path reads `tuning.lambda_by_fold`. `RidgeNumericalFailure` has the same path.

**Cause and impact.** `tuning_started` becomes true before `tuning` is assigned. A valid budget/numerical failure is replaced by an exception.

**Recommended revision.** Initialize `tuning=None`; access tuning diagnostics only after a successful return and preserve partial counters/statuses.

**Regression check.** Inject budget and numerical failures during inner tuning; require a returned NetworkFit with all pairs and explicit incomplete statuses.

**Fix update (2026-09-26).** Commit `7e79b96` initializes tuning diagnostics as unavailable until `tune_lambdas` returns, then records penalty counters only after a successful return. Budget and numerical failures during tuning now return an incomplete `NetworkFit` with `budget_exceeded` or `numerical_failure` pair statuses and NaN weights instead of raising `UnboundLocalError`. Both injected-failure regression cases passed; all 22 focused fit tests passed.

### BUG-05: Keep valid pair stability when another pair is unsupported

**Priority:** P1. **Source:** `src/mintnet/cin/stability.py:348–363`. **Build plan:** Task 07 §4.

**Erroneous behavior and reproduction.** For N=80, two normal columns, rare categorical `c=[1,1]+[0]*78`, seed 17 and lambda grid `(0.1,)`, the first repeat finishes with a–b complete and c-incident pairs unsupported. A two-repeat request instead stops at repeat 0 and rewrites every pair to interrupted/NaN.

**Cause and impact.** The global fit `complete` flag is treated as execution interruption even when computation ended and only some pairs are unavailable.

**Recommended revision.** Distinguish execution/deadline interruption from per-pair status; retain valid records and continue repeats after completed execution.

**Regression check.** The rare-category fixture must yield two valid a–b records and unavailable c pairs; true deadline interruption remains separately tested.

**Fix update (2026-09-26).** Commit `97afd2a` determines repeat execution completion from `runtime.status`, which distinguishes a finished computation from a fit summary made incomplete by pair-level unsupported or numerical statuses. A rare-category regression fixture now retains both completed a–b records and continues through the requested repeats while preserving unavailable c-incident pairs. The full focused stability suite passed (18 tests), including the deadline-interruption checks.

### BUG-06: Validate all completed-repeat records and seeds on stability resume

**Priority:** P1. **Source:** `src/mintnet/cin/stability.py:175–187,441–468`. **Build plan:** Task 07; D-101.

**Erroneous behavior and reproduction.** A genuine completed one-repeat result with its records removed is accepted as `complete`, with one completed repeat and zero rows. Replacing every record seed with 0 is also accepted.

**Cause and impact.** Validation checks keys present but never requires the full pair set for each claimed completed repeat or seed equality with metadata. Resume skips missing work.

**Recommended revision.** Require every canonical pair exactly once per completed repeat and cross-check repeat IDs/seeds/statuses before resuming.

**Regression check.** Reject a deleted pair/repeat, altered seed, and duplicate/missing pair combination; intact saved results resume.

**Fix update (2026-09-26).** Commit `3b739ca` validates each record's repeat ID and seed against metadata, requires every claimed completed repeat to contain the full canonical pair set without interrupted rows, and revalidates an in-memory result before resume. This catches record-table changes made after construction as well as corrupt saved results. Regression cases for a removed pair and altered seed are rejected; the focused stability suite passed (18 tests).

### BUG-07: Keep point-fit evidence if optional stability errors

**Priority:** P2. **Source:** `src/mintnet/experiments/cin_baseline.py:405–452`. **Build plan:** Task 07,09.

**Erroneous behavior and reproduction.** The runner writes the point pair table and manifest before calling optional stability in the same try block. If stability raises, the whole method row becomes `error`, while `pair_sidecar_file` is still unset; aggregation sees an orphan pair file.

**Cause and impact.** Optional resampling failure is allowed to overwrite ordinary fit status and leave sidecar promises inconsistent.

**Recommended revision.** Commit ordinary fit status and pair promise before stability; catch and record stability errors separately and clean or account for partial optional files.

**Regression check.** Inject a stability exception after a successful point fit; preserve its metrics and sidecar while reporting unavailable stability.

**Fix update (2026-09-26).** Commit `71aea51` records the pair sidecar promise as soon as its manifest entry is written, before running optional stability. Stability now has independent `stability_status` and `stability_error` fields; an exception no longer changes the point-fit status or removes its metrics, and a partial stability sidecar is cleaned up. The new integration regression forces `estimate_stability` to fail after a successful point fit and verifies the pair file and manifest remain consistent while no stability sidecar is promised. This regression passed in both the focused runner/fit suite and the full suite; the suite's only failure was the unrelated BUG-23 ledger snapshot assertion.

### BUG-08: Complete required continuous-node diagnostics

**Priority:** P2. **Source:** `src/mintnet/cin/fit.py:549–592`. **Build plan:** Task 05 §6.

**Erroneous behavior and reproduction.** The continuous node outputs omit evaluation residual skew/kurtosis, out-of-training-range fractions, and variance-floor counts by model type promised in the plan.

**Cause and impact.** The scoring path records MSE and limited floor summaries but never computes or exports these diagnostics. Edge weights are not shown incorrect by this omission.

**Recommended revision.** Compute descriptive diagnostics from the correct evaluation rows with training-only fitted transforms, attributed by model and fold. Define unavailable values for degenerate samples.

**Regression check.** Use skewed residuals, held-out range excursions, and controlled floor hits; compare with independent hand calculations.

**Fix update (2026-09-26).** Commit `825bfc7` exports continuous evaluation residual skew and Fisher excess kurtosis, the evaluation fraction outside the training response range, and variance-floor hit/observation counts separately for full, reduced, and intercept models. Continuous model MSE and residual summaries are aggregated with evaluation-row weights; existing generic full-model fields remain available for compatibility. The regression test independently checks full-model residual moments and range excursions and verifies the floor-observation counts for each model type. This regression passed in both the focused runner/fit suite and the full suite. Ruff passed on the changed implementation and tests.

## Persistence and methods

### BUG-09: Preserve schema order when saving fits and stability

**Priority:** P1. **Source:** `src/mintnet/cin/result.py:202; src/mintnet/cin/stability.py:515`. **Build plan:** Task 06–07.

**Erroneous behavior and reproduction.** A real fit with node order `z,a,m` saves but `load_fit` fails: `nodes table order does not match metadata schema`. Its stability save/load fails with `non-canonical pair`.

**Cause and impact.** `json.dump(..., sort_keys=True)` alphabetizes `metadata.schema`, though insertion order defines node order and pair orientation. The fit-ID recomputation does not detect it.

**Recommended revision.** Persist an explicit ordered node list or preserve schema order in serialization and validate both formats.

**Regression check.** Round-trip complete/incomplete fits and stability with nonalphabetical schema; check views, pair orientation and resume.

**Fix update (2026-09-26).** Commit `8c4dd7e` stores an explicit `node_order` list alongside schema metadata in fit and stability artifacts, preserving the build plan's sorted JSON representation without losing semantic order. Fit loading validates the list and can recover older fit files from the preserved `nodes.csv` order. Stability validation, rule evaluation, and repeat setup use the explicit list to preserve canonical pair orientation. Regression tests round-trip nonalphabetical `z,a,m` fit and stability schemas and verify legacy fit recovery. Both targeted round-trip tests passed.

### BUG-10: Restore exact float64 CSV round trips

**Priority:** P3. **Source:** `src/mintnet/cin/result.py:127–141,222,262–263; src/mintnet/cin/stability.py:519–530`. **Build plan:** Task 06 §2.

**Erroneous behavior and reproduction.** A real saved/reloaded fit differs in numeric values by up to `9.71e-17`, despite 17-digit writing. Current approximate DataFrame assertions do not detect it.

**Cause and impact.** Default pandas parsing and numeric coercion are not guaranteed to reconstruct the exact float64 values. An inclusive threshold set at a stored weight can change membership.

**Recommended revision.** Use round-trip-safe numeric parsing with explicit identifier/missing-value types across fit and stability files.

**Regression check.** Use exact DataFrame comparisons, values at an inclusive effect threshold, and compressed stability records.

**Fix update (2026-09-26).** Commit `8c4dd7e` enables pandas' `float_precision="round_trip"` parser for fit pair/node/fold/matrix files and plain or gzip stability records. Empty fields are treated as missing only for declared numeric columns, so identifiers and empty diagnostic strings remain strings while missing numeric values remain NaN. Regression tests use adjacent float64 values around 0.1, compare persisted frames exactly, include a pair at its stored inclusive effect threshold, and verify compressed stability precision. Both exact-round-trip tests passed.

### BUG-11: State the stability cutoff in methods text

**Priority:** P2. **Source:** `src/mintnet/cin/views.py:310–327`. **Build plan:** Task 06 §7.

**Erroneous behavior and reproduction.** `methods_text()` states B and subsampling fraction but omits the applied `min_stability`, so views with different cutoffs can have the same methods description.

**Cause and impact.** The cutoff exists in view settings but is not included in generated text; the displayed subset cannot be reproduced from it.

**Recommended revision.** Print the actual cutoff with its applied rule and keep the subsampling interpretation.

**Regression check.** Compare text for 0.5 and 0.9 cutoffs against the same stability result.

**Fix update (2026-09-26).** Commit `8c4dd7e` adds the actual inclusive rule (`stability >= cutoff`) and formatted `min_stability` value to generated methods text whenever stability filtering is applied. A regression test compares the same fit and stability result at 0.5 and 0.9 and confirms both distinct cutoffs are stated. The test passed.

## Statistical evidence

### BUG-12: Compute selected-threshold strong-edge recall correctly

**Priority:** P1. **Source:** `src/mintnet/experiments/cin_baseline.py:295–308,351–363; src/mintnet/experiments/cin_baseline_reporting.py:63–70; scripts/cin_gate_check.py:139`. **Build plan:** Task 11; frozen charter.

**Erroneous behavior and reproduction.** One recovered strong edge and one missed weak edge give `delta_01_recall=0.5`, while true strong-edge recall is 1.0. Development selection and the validation gate read that all-edge recall as strong recall. Existing `strong_edge_recall` ignores the selected delta.

**Cause and impact.** The numerator/denominator and selection threshold of the declared estimand are not implemented. Delta selection and the gate verdict can change.

**Recommended revision.** Persist per-delta strong-edge recall alongside the existing all-edge recall; consume the correct field in selection and gates. Version any corrected analysis of hosted evidence and preserve the frozen original.

**Regression check.** Include mixed weak/strong truth, strong edges above/below delta, and empty views.

**Fix update (2026-09-26).** Commit `d69e457` adds `delta_{token}_strong_recall` for each display threshold and computes it over the declared strong-edge truth set. Delta selection and validation gates now consume that selected-threshold metric while preserving the legacy all-positive-edge recall. Regression coverage distinguishes the two estimands with mixed weak/strong truth and checks the selected-threshold values. No hosted result or frozen charter was recalculated. The focused panel checks passed.

### BUG-13: Require each named case to pass validation gates

**Priority:** P1. **Source:** `scripts/cin_gate_check.py:132–152`. **Build plan:** Task 11.

**Erroneous behavior and reproduction.** Otherwise-valid input with A selected precision 0.5 and B 1.0 passes pooled `A_B_selected_precision` at 0.75. A/B AP, recall and nonempty; F/G/H AP; and F/G loss are similarly pooled.

**Cause and impact.** A strong case masks a failing case despite the plan's case-specific A/B conditions and scope decisions.

**Recommended revision.** Emit per-case gate rows, or make each combined gate require all constituent case means to pass, with case-level counts and unavailable statuses.

**Regression check.** For each pooled quantity, make one case fail and another offset its mean; the verdict must identify the failing case.

**Fix update (2026-09-26).** Commit `d69e457` replaces pooled A/B, F/G/H, and F/G validation conditions with independent per-case gates, so one case cannot mask another. Strong-set availability is also checked across every replicate, with a missing denominator causing that case's gate to fail. Regression tests force one case to fail while its neighbor passes. Focused gate tests passed.

### BUG-14: Enforce the Case C point-fit runtime threshold

**Priority:** P1. **Source:** `src/mintnet/experiments/cin_baseline.py:160–178; scripts/cin_gate_check.py:154–156`. **Build plan:** Task 11.

**Erroneous behavior and reproduction.** Setting every C elapsed time to `1e9` seconds still passes `C_runtime_completion`. Configured `point_fit_max_seconds` is parsed and serialized but not used by the fit or gate.

**Cause and impact.** The runtime gate tests only finite elapsed time, so any completed run can exceed the declared limit and pass.

**Recommended revision.** Compare measured point-fit time with the configured threshold, handling missing, negative and nonfinite values. Document separately whether the field is also a hard execution budget.

**Regression check.** Test below, at and above threshold, plus missing, negative and infinite elapsed values.

**Fix update (2026-09-26).** Commit `d69e457` records `point_fit_seconds` from fit runtime metadata and makes the Case C gate require a completed fit with a finite, nonnegative point-fit duration no greater than `point_fit_max_seconds`. Missing runtime evidence fails the gate; this implements the declared reporting gate and does not add a hard interruption budget. Boundary, above-limit, missing, negative, and infinite-value regressions passed.

### BUG-15: Validate development identities before freezing delta

**Priority:** P1. **Source:** `src/mintnet/experiments/cin_baseline_reporting.py:74–110`. **Build plan:** Task 11.

**Erroneous behavior and reproduction.** Just two A/B rows labelled development with replicate 9999 return `selection_status=selected` under the full frozen config. Duplicates, missing replicates and row charter mismatch are not rejected.

**Cause and impact.** Selection only filters phase/method and checks case presence, then stamps the config charter hash on its output. Partial or mislabeled evidence can appear frozen.

**Recommended revision.** Require the full configured A/B development identity set, unique permitted replicate IDs, and matching input/config provenance before freezing. Mark partial shard reports unavailable.

**Regression check.** Reject missing, duplicate, out-of-range and wrong-hash input; confirm valid complete input selects deterministically.

**Fix update (2026-09-26).** Commit `d69e457` requires unique A/B development CIN identities to exactly match the configured replicate set and requires every row's charter hash to match the config before selection. Invalid replicate values, partial/extra/duplicate identities, missing required metrics, unavailable strong-edge denominators, or undefined per-threshold strong recall now produce `selection_status=unavailable` rather than a frozen delta. Validation rows remain excluded. The regression suite covers incomplete, duplicate, out-of-range, wrong-charter, and missing-strong-set inputs as well as deterministic valid selection.

### BUG-16: Use paired B/D dataset seeds in the runner

**Priority:** P2. **Source:** `src/mintnet/experiments/cin_baseline.py:486–492`. **Build plan:** Task 08,11.

**Erroneous behavior and reproduction.** For development replicate 0, B uses structure/sample seeds `(789166437,3319252032)` and D `(4218215934,104051035)`; generated truth sets differ.

**Cause and impact.** Case-specific seed coordinates break the intended experiment where D is a monotone transform of the same B draw. The generator pairs correctly when given common seeds.

**Recommended revision.** Share B/D structure and sample coordinates while documenting fit-seed policy. Label the existing D evidence as unpaired; any new evidence campaign needs separate authorization.

**Regression check.** Capture runner-level datasets for the same phase/replicate: identical truth and latent draws, prescribed transformation only.

### BUG-17: Count isolated nodes in population edge density

**Priority:** P2. **Source:** `src/mintnet/simulation/cin_networks.py:139–167`. **Build plan:** Task 08.

**Erroneous behavior and reproduction.** E reports density 0.08 rather than `24/435=0.05517`; H reports 0.4 rather than `4/28=0.142857`.

**Cause and impact.** With unavailable population CMI, node count is inferred only from edge endpoints, excluding isolated distractors from the denominator.

**Recommended revision.** Supply the full schema or explicit p to population_signal_summary and retain CMI as unavailable per D-102.

**Regression check.** Check E/H and a small graph with isolates and no oracle CMI.

### BUG-18: Average categorical excess loss over categorical nodes only

**Priority:** P2. **Source:** `src/mintnet/experiments/cin_baseline.py:416–419`. **Build plan:** Task 11.

**Erroneous behavior and reproduction.** In mixed H/I cases the runner detects at least one categorical node, then averages `full_minus_intercept` over every node, including continuous targets. F/G gates are unaffected because those cases are all categorical.

**Cause and impact.** The reported quantity has the wrong target population and can misdescribe mixed-case categorical performance.

**Recommended revision.** Filter node diagnostics to declared categorical targets and preserve a contributor count/unavailable state.

**Regression check.** Make categorical and continuous gains differ in a small mixed fixture; only categorical gains may determine the field.

## Aggregation and sidecars

### BUG-19: Support the prescribed phase-only aggregation sequence

**Priority:** P1. **Source:** `scripts/aggregate_shards.py:55–67; docs/cin_user_guide.md:59–74`. **Build plan:** Task 09,11.

**Erroneous behavior and reproduction.** The full config expects 600 rows, while development-only and validation-only dispatches yield 200 and 400. The documented generic command rejects both; D-106 records exactly this failure and a local workaround.

**Cause and impact.** The aggregator validates only the entire grid and has no phase-aware CLI contract, although delta must be frozen between phase runs.

**Recommended revision.** Add a CIN phase-aware wrapper or safe extension that validates exact identities for one phase and rejects missing/duplicate/foreign rows. Update workflow and guide accordingly.

**Regression check.** Aggregate each smoke phase independently; reject missing/duplicate identities and phase mixing.

### BUG-20: Stage validated panel sidecars before writing reports

**Priority:** P1. **Source:** `scripts/aggregate_shards.py:74–77; src/mintnet/experiments/cin_baseline_reporting.py:34–49`. **Build plan:** Task 09.

**Erroneous behavior and reproduction.** With full-grid raw rows, generic aggregation reaches `write_report` and raises `FileNotFoundError` for a promised pair file: it has copied no sidecars. The guide's next command to aggregate sidecars runs too late; the Actions aggregate job never stages them.

**Cause and impact.** Raw aggregation invokes the report before sidecar collection/validation. Existing generic aggregation integration coverage exercises only cost shards.

**Recommended revision.** Use one orchestration path that validates and stages raw plus sidecars before report generation, or split raw aggregation and report writing explicitly.

**Regression check.** From clean output, aggregate a complete panel smoke grid and produce its report; deleting a promised sidecar must fail before publication.

### BUG-21: Reject mixed shard provenance and retain environment details

**Priority:** P1. **Source:** `scripts/aggregate_shards.py:98–127`. **Build plan:** Task 09,11.

**Erroneous behavior and reproduction.** Two fabricated shards with different configs, charter hashes and git revisions are accepted by `_write_provenance`. Aggregate metadata advertises only the first shard's charter/commit while summing both runtimes, and omits config hash, package versions, thread settings, CPU and RSS.

**Cause and impact.** Shard invariance is assumed, never checked. Mixed experiments can be presented as one evidence bundle.

**Recommended revision.** Check each required config/charter/code identity, require metadata, preserve per-shard environments and meaningful aggregate summaries. Bind gate input to validated provenance.

**Regression check.** Reject conflicting or missing provenance; confirm a valid aggregate retains package/thread/CPU records.

### BUG-22: Validate pair identities and requested stability repeat coverage

**Priority:** P1. **Source:** `scripts/aggregate_cin_sidecars.py:81–86,118–136`. **Build plan:** Task 09 §6.

**Erroneous behavior and reproduction.** For p=3, a stability file containing only repeat 0's three rows passes aggregation even when ten repeats were requested. Missing `repeat_id` skips that check; pair row counts alone can hide a duplicate and missing pair. A manifestless shard with no raw promises can also leave orphan files unchecked.

**Cause and impact.** Hash and row count prove byte consistency, not canonical pair/repeat completeness. The runner lacks request/completion metadata needed to distinguish a legitimate partial result from truncation.

**Recommended revision.** Persist stability request/status/completed IDs and canonical node order; validate exact pair sets and record identities/seeds for each required repeat, with honest partial status. Check orphans even without a manifest.

**Regression check.** Reject missing repeat, duplicate/missing pair swap, wrong identity, absent repeat ID and orphan; accept explicitly partial output only with matching status.

### BUG-23: Update the cost ledger test for later dispatches

**Priority:** P2. **Source:** `tests/integration/test_cin_runners.py:544–552; docs/cin_compute_ledger.csv`. **Build plan:** Task 09,10,11.

**Erroneous behavior and reproduction.** The full active suite returned 277 pass, one fail. `test_compute_ledger_records_task_10_dispatch` asserts the entire ledger has exactly the header plus the Task 10 row. The ledger legitimately has two later Task 11 development/validation rows.

**Cause and impact.** The test encodes a historical whole-file snapshot instead of checking the Task 10 record and ongoing ledger invariants.

**Recommended revision.** Assert the Task 10 row is present and validate header, unique dispatch identities, dates and numeric runner-hour fields across all rows. Keep Task 11 rows.

**Regression check.** Run the focused integration test and full suite with all current ledger entries; add a later valid row fixture to ensure it remains accepted.

## Documentation and reporting

### BUG-24: Produce the declared descriptive statistical-panel report

**Priority:** P2. **Source:** `src/mintnet/experiments/cin_baseline_reporting.py:17–21,169–175,207–241`. **Build plan:** Task 11 §11.

**Erroneous behavior and reproduction.** The metric summary covers a short list plus selected delta and discards its `pairs` argument. Markdown contains prose but no metric tables. Oracle error, null quantiles, agreement views, other thresholds and stability descriptives are not summarized; variance-only/XOR demonstrations are mentioned without runner implementation.

**Cause and impact.** The panel's promised descriptive evidence cannot be reviewed from its report, even where raw columns exist. This is a deliverable gap, not a claim that the estimator must recover XOR.

**Recommended revision.** Render required summaries with counts/MCSE and explicit empty/failure/unavailable status; consume validated stability records; mark absent demonstrations unfinished. Document the plan/charter ambiguity about the number of stability datasets.

**Regression check.** Assert each required section has actual values and denominators; preserve unavailable results and avoid implying absent demonstrations ran.

### BUG-25: Complete the Task 12 researcher guide and close-out

**Priority:** P2. **Source:** `docs/cin_user_guide.md:1; README.md:12; docs/decision_log.md:D-106`. **Build plan:** Task 12.

**Erroneous behavior and reproduction.** The guide remains a runner guide without a `fit_network` quick start, schema/missingness and view/export/stability walkthroughs, or the two worked examples. README still says the engine is unimplemented; the decision log has no Task 12 per-scope close-out.

**Cause and impact.** The reusable researcher-facing baseline is undocumented and repository status is contradictory. Known failed validation gates do not remove Task 12's honest documentation obligation.

**Recommended revision.** Write and execute continuous and mixed examples; document defaults, statuses, views, exports, dense/low-N use and limitations; correct README and append an evidence-backed scope decision without rewriting D-106 or rerunning validation.

**Regression check.** Execute every guide code block; check examples and save/load, corrected aggregation commands, and explicit support/withheld statements for continuous, categorical, p=100 runtime and low-N scopes.
