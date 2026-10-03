# F Full-Pipeline Development Cap Comparison

**Outcome:** The 1,000-attempt cap completed all 100 candidate fits in this local development cohort; the 500-attempt cap completed 98 and had two generator errors. This is development evidence only and does not change the failed hosted validation result.

## Results

| Measure | Cap 500 | Cap 1,000 |
| --- | ---: | ---: |
| Identities retained | 100 | 100 |
| Generated datasets | 98 | 100 |
| Fit complete | 98 | 100 |
| Fit incomplete | 0 | 0 |
| Generation errors | 2 | 0 |
| Pair sidecars verified | 98 × 28 rows | 100 × 28 rows |
| Total generator attempts, including capped errors | 13,898 | 13,970 |
| Runner elapsed time | 107.05 s | 120.71 s |
| Maximum point-fit time | 1.672 s | 2.438 s |

The paired status table was 98 `complete → complete` and two `error → complete`, with no regressions. Cap-500 generation errors were F/5029 and F/5047, both `GeneratorAcceptanceError` at attempt 500. At cap 1,000, both first passed on attempt 536. No fit-incomplete rows occurred in either arm.

The successful draws were unchanged when the cap increased. All 98 identities generated at both caps had identical frame hashes, generator attempt counts, planted edges, and population-CMI summaries. Every non-timing raw fit metric for those 98 identities also matched exactly. The higher cap used 72 additional generator attempts in total: 36 attempts beyond the former cap for each of the two recovered identities.

Both recovered datasets met the declared data contract. F/5029 had a minimum planted-edge CMI of `0.00502556` and F/5047 had `0.00621274`, both at or above `0.005`; both had 10 planted edges and both binary levels observed for every node. Across the cap-1,000 datasets, the minimum planted-edge CMI per dataset ranged from `0.00500047` to `0.00680213`. All generated datasets had 10 planted edges. The cap increase therefore admitted two later first-success draws under the same acceptance rule and left all earlier accepted draws unchanged.

The runner recorded 107.05 seconds at cap 500 and 120.71 seconds at cap 1,000. This total-run difference includes two additional full fits and ordinary local timing variation; it should not be interpreted as a controlled estimate of cap-only overhead. The 72 extra generation attempts are the directly measured incremental search work.

## Interpretation

This experiment supports the finite 500-attempt limit as the direct reason for the two generator errors in this fresh cohort. The follow-up cap-1,000 arm generated and fit all 100 identities, and did not change fit results for the 98 shared datasets. Together with the generator-only cap audit, the evidence supports a future implementation candidate that changes the F cap to 1,000 while preserving the `0.005` CMI threshold and strict completion denominator.

This does not show that a future held-out cohort will reach 100/100. The cohort was used for development selection, and the local software environment differs from the hosted validation environment. Any pass/fail claim still requires a new source/config freeze and a disjoint hosted validation cohort. Do not retune the threshold or reuse this cohort or any earlier identities for that validation.

## Provenance and verification

- Protocol and config were committed before the run in `46c9b4b` (`Freeze F full-pipeline cap diagnostic`).
- Cap 500 ran at `46c9b4b`; cap 1,000 ran at `08ff689` after a fix to the audit driver only. The generator, runner, shared-seed, and config hashes match across the two arms. No production code changed between arms.
- Python 3.11.9, NumPy 1.26.4, pandas 2.2.3, SciPy 1.11.2, scikit-learn 1.3.0, PyYAML 6.0.2, and threadpoolctl 3.2.0 on Windows 10. The hosted validation environment used newer numerical packages; this comparison was local and was not dispatched to GitHub Actions.
- Both arms have exactly the 100 configured development identities, no validation batch was run, and each complete identity has a 28-row pair sidecar whose manifest checksum and row count were verified.
- The run manifest records the config and source hashes, environment, per-arm commit, outcomes, attempts, and runtimes in [`run_manifest.json`](run_manifest.json).
- [`checksums.sha256`](checksums.sha256) records SHA-256 hashes for every report, raw output, metadata file, and sidecar in this comparison bundle.

## Evidence files

- Frozen inputs: [`protocol`](../full_pipeline_cap_comparison_20261004.md), [`config`](../../../../../configs/cin_f_cap_full_pipeline_dev_20261004.yaml), and [`runner`](../run_f_full_pipeline_cap_comparison.py).
- Identity-level comparison: [`paired_cap_comparison.csv`](paired_cap_comparison.csv).
- Data summaries: [`data_characteristics_cap_500.csv`](data_characteristics_cap_500.csv) and [`data_characteristics_cap_1000.csv`](data_characteristics_cap_1000.csv).
- Runner outputs: [`cap-500/`](cap-500/) and [`cap-1000/`](cap-1000/), including all raw rows, metadata, reports, manifests, and pair sidecars.
- Previous generator-only diagnosis: [`generator_acceptance_diagnosis.md`](../generator_acceptance_diagnosis.md).
