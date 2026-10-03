# F Generator Acceptance Failure Diagnosis

**Scope:** Generator-only diagnosis following the failed F follow-up validation gate. This report preserves the hosted campaign result and does not claim new validation evidence.

## Finding

The seven shared validation errors are reproducible consequences of the generator's declared rejection rule. On attempt 500, every replay's last candidate graph still had between three and seven planted edges below the population-CMI floor of `0.005`. An independent entropy-based calculation of conditional mutual information agreed with the repository calculation to within `1.7e-15`. The evidence does not indicate a CMI arithmetic defect or a difference between candidate and baseline fitting.

The fresh development-only sample also shows that the finite cap can censor otherwise acceptable draws: 96 of 100 identities were accepted by 500 attempts; the other four first passed between attempts 537 and 707, so all 100 were accepted by 1,000. This supports investigating a larger finite cap as a possible operational correction. It does not by itself authorize changing the cap or establish that the full pipeline will meet a 100% completion gate.

## Preserved validation identity replays

The replay used each `structure_seed` from the candidate validation aggregate and repeated exactly 500 graph/field/interactions draws. These are forensic replays of consumed identities, not a new validation campaign. `sample_seed` is retained in the record but does not affect population-CMI acceptance.

| Replicate | Minimum planted-edge CMI on attempt 500 | Planted edges below 0.005 | Maximum independent/repository CMI difference |
| ---: | ---: | ---: | ---: |
| 3007 | 0.003729 | 4 / 10 | 1.7e-15 |
| 3010 | 0.002845 | 4 / 10 | 8.9e-16 |
| 3025 | 0.001703 | 4 / 10 | 1.7e-15 |
| 3057 | 0.001536 | 7 / 10 | 1.0e-15 |
| 3062 | 0.002110 | 5 / 10 | 8.7e-16 |
| 3082 | 0.000946 | 7 / 10 | 1.2e-15 |
| 3090 | 0.002598 | 3 / 10 | 8.4e-16 |

No replay had an accepted draw in the first 500 attempts. Across those attempts, each identity's best (largest) minimum planted-edge CMI ranged from `0.004730` to `0.004983`, still below the floor. The final rejected draws were not all just-rounding failures: some limiting CMIs were substantially below `0.005`, and the independent formula reproduced them. This is consistent with valid draws rejected by the generator's declared threshold rule.

## Fresh development-only cap sensitivity

The protocol file was written before this run. The cohort comprised replicate IDs `4000–4099`, with seed bundles derived from master seed `20261003`, F case index 5, and development phase index 0. Each identity was generated once, stopping at the first draw satisfying the same 10-edge `0.005` floor or at 2,500 attempts. The recorded first-acceptance count permits paired descriptive summaries at caps 500, 1,000, and 2,500.

| Measure | Result |
| --- | ---: |
| Accepted by 500 | 96 / 100 |
| Accepted by 1,000 | 100 / 100 |
| Accepted by 2,500 | 100 / 100 |
| Median first-acceptance attempt | 90 |
| 95th percentile, linear interpolation | 371.25 |
| Maximum first-acceptance attempt | 707 |

Four identities first passed after the original cap: replicate 4012 at attempt 544, 4074 at 707, 4081 at 537, and 4088 at 596. The results indicate a finite-cap effect in this development sample, while retaining all generation rules and the same acceptance threshold.

## Reproduction and limits

- Source revision at execution: `e5f32d8cc25932a093365f3e54bb4c877d6315f7`.
- Generator source SHA-256: `549741a766c1f4e5d99e0ec54f56eee90f0ae83786d1806a3bd3dc399679ca20`.
- Local environment: Python 3.11.9, NumPy 1.26.4, SciPy 1.11.2. Hosted validation used Python 3.11.16, NumPy 2.4.6, and SciPy 1.17.1. This diagnostic was not run in GitHub Actions; treat the local yield as development evidence and retain the environment difference as a reproducibility limit.
- The audit script repeats the generator's graph, field, interaction, normalization, and CMI sequence. The independent check uses the entropy identity `H(X,R) + H(Y,R) - H(R) - H(X,Y,R)` for each planted edge.
- No model fitting, AP calculation, code fix, threshold change, cap change, or hosted dispatch occurred. The committed 97-identity result remains candidate `90/97`, baseline `88/97`, strict gate failed.

## Recommended next decision

Do not change the frozen campaign or claim the gate passed. The current evidence supports the cap as the direct cause of the seven generation errors and does not show a generator arithmetic bug. Before changing the production cap, assess a proposed cap (for example, 1,000) on a separately frozen development protocol that runs the full candidate pipeline and compares generation yield, fit completion, runtime, and generated-data characteristics. If that development work supports the change, freeze it and use a new disjoint validation cohort for any pass/fail claim. The seven consumed identities and the 100 diagnostic identities must remain excluded from that future validation set.

## Files

- [`acceptance_diagnostic_protocol_20261003.md`](acceptance_diagnostic_protocol_20261003.md): predeclared development diagnostic procedure.
- [`audit_f_generator_acceptance.py`](audit_f_generator_acceptance.py): reproducible forensic replay and fresh-cohort generator audit.
- [`validation_failure_replay.csv`](validation_failure_replay.csv): seven identity-level replay results.
- [`fresh_development_acceptance.csv`](fresh_development_acceptance.csv): 100 identity-level cap-sensitivity results.
