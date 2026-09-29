# F Follow-Up Hosted Validation Report

**Protocol:** `cin-followup-f-v1`
**Outcome:** **Strict candidate gate failed**
**Validation identities:** `F/validation/3000–3096` (97 paired identities)
**Frozen source revision:** `d006f7f46a9011125f923de540dce6ac90d3ab11`
**GitHub Actions dispatch revision:** `ad4bf8ae6a6f3f3316db1652a832b61da9002c8d`

## Contents

| Section | What it covers |
| --- | --- |
| [Result](#result) | Gate outcome and paired completion table |
| [Failure details](#failure-details) | Generator errors and baseline-only unsupported pairs |
| [Interpretation](#interpretation) | What the candidate improved and why the strict gate still fails |
| [Provenance and artifacts](#provenance-and-artifacts) | Hashes, environments, preserved files, and workflow links |
| [Follow-up](#follow-up) | Guardrails for the next campaign |

## Result

The predeclared validation gate requires the candidate to complete **all 97 identities**. The support-aware candidate completed 90 identities (92.78%), so it **fails** that gate. The baseline completed 88 identities (90.72%). Both arms retained all 97 rows and used the same identity and five-seed bundle for each row.

| Measure | Baseline (`support_aware_inner_splits=false`) | Candidate (`true`) |
| --- | ---: | ---: |
| Complete identities | 88 / 97 | 90 / 97 |
| Completion rate | 90.72% | 92.78% |
| 95% Wilson interval | [83.30%, 95.04%] | [85.85%, 96.46%] |
| Generator-acceptance errors | 7 | 7 |
| Fit-incomplete identities | 2 | 0 |
| Complete pair rows | 2,506 / 2,520 | 2,520 / 2,520 |
| Unsupported pair rows | 14 | 0 |
| Total shard runtime | 37.92 s | 32.70 s |

The paired table is 88 complete-to-complete, 2 incomplete-to-complete, and 7 generator-error-to-generator-error. There were **2 improvements and 0 regressions**. This is evidence that the support-aware split resolves the two observed fit-support failures on this cohort. It does not satisfy the campaign's 97/97 primary completion criterion because generator rejection remains.

Average precision is descriptive among complete rows only: mean/median were 0.6263/0.6150 for baseline and 0.6297/0.6269 for candidate. These values are not the primary gate and do not change the failed outcome. AP remains unavailable for every failed or incomplete identity.

## Failure details

All seven generation errors are `GeneratorAcceptanceError` after exhausting 500 attempts. The same validation identities failed in both arms because the fit-split option is applied after data generation:

| Replicate | Baseline | Candidate | Attempts |
| ---: | --- | --- | ---: |
| 3007 | Generator acceptance error | Generator acceptance error | 500 |
| 3010 | Generator acceptance error | Generator acceptance error | 500 |
| 3025 | Generator acceptance error | Generator acceptance error | 500 |
| 3057 | Generator acceptance error | Generator acceptance error | 500 |
| 3062 | Generator acceptance error | Generator acceptance error | 500 |
| 3082 | Generator acceptance error | Generator acceptance error | 500 |
| 3090 | Generator acceptance error | Generator acceptance error | 500 |

The baseline also had two fit-incomplete identities:

| Replicate | Failed pairs | Pair-sidecar result |
| ---: | ---: | --- |
| 3029 | 7 of 28 | Seven `unsupported` rows; two inner folds complete; zero scored observations for those pairs |
| 3071 | 7 of 28 | Seven `unsupported` rows; two inner folds complete; zero scored observations for those pairs |

The candidate completed all 28 pairs for both identities. Across its 90 generated datasets, no unsupported pair rows remained. Across the baseline's 90 generated datasets, the two incomplete fits account for all 14 unsupported pair rows.

Generator attempts across the 97 validation identities had a median of 110 and a minimum of 1. The observed maximum was the configured cap of 500, reached by the seven rejected identities. The development cap sweep had a maximum of 292 attempts on its separate 20 identities; that result did not predict the seven fresh validation rejections.

## Interpretation

The selected support-aware split improved the fit-completion component without regressions, but the primary completion gate counts generator failures in the denominator. Seven identities could not be generated under the frozen 500-attempt cap, so neither arm passed. The candidate's 90/97 result is a failed validation gate, not a reason to tune against these same identities.

Do not raise the cap and rerun identities `3000–3096`, remove rejected rows, or weaken the strict threshold after seeing this result. A follow-up generator correction should be selected using development identities only, then evaluated on a new, predeclared validation cohort with a new freeze and fresh seed inventory.

## Provenance and artifacts

The aggregate artifacts report validated shard provenance at dispatch revision `ad4bf8ae6a6f3f3316db1652a832b61da9002c8d`. The committed freeze manifests pin source revision `d006f7f46a9011125f923de540dce6ac90d3ab11`; the frozen protocol source fingerprint at `d006f7f` and at the docs-only dispatch revision `ad4bf8a` is identical. Later commits `e190169` and `7b3f3a9` correct the validation checker only; they do not change the simulation, generator, CIN fit, configuration, or workflow that produced these results.

Both validation aggregates passed the workflow's full-grid and sidecar aggregation checks. The local strict gate then verified exact identities, seed bundles, cap, split arm, source/config/charter hashes, raw aggregate hashes, raw pair counts, unavailable AP for failures, and the paired completion table. Its saved result is [`gate-result.json`](gate-result.json); its status is `fail` because candidate completion was 90/97, below 97/97.

| Arm | Aggregate | Raw rows | Runtime metadata | Pair sidecars |
| --- | --- | --- | --- | --- |
| Baseline | [`baseline/`](baseline/) | [`baseline/raw_metrics.csv`](baseline/raw_metrics.csv) | [`baseline/metadata.json`](baseline/metadata.json) | [`baseline/sidecars/`](baseline/sidecars/) |
| Candidate | [`candidate/`](candidate/) | [`candidate/raw_metrics.csv`](candidate/raw_metrics.csv) | [`candidate/metadata.json`](candidate/metadata.json) | [`candidate/sidecars/`](candidate/sidecars/) |

The hosted environment was Linux x86_64 with Python 3.11.16, NumPy 2.4.6, pandas 3.0.5, SciPy 1.17.1, scikit-learn 1.9.0, PyYAML 6.0.3, and threadpoolctl 3.6.0. The shard metadata records one numerical thread for BLAS/OpenMP pools.

## Follow-up

The valid next experiment is a development-only investigation of F generator acceptance at fresh development identities, including failure taxonomy and cap sensitivity. If a correction is selected, freeze it before assigning a new validation cohort. This validation cohort is now consumed and must not be reused for selection or another pass/fail attempt.
