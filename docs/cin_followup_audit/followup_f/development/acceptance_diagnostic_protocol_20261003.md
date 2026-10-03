# F Generator Acceptance Diagnostic Protocol

**Purpose:** Diagnose the F generator's 500-attempt rejection failures after the hosted follow-up campaign. This is a development-only generator audit, not a validation run and not evidence for changing the frozen F campaign result.

## Frozen limits

- Preserve the hosted validation outcome: candidate 90/97, baseline 88/97, with seven shared `GeneratorAcceptanceError` identities. Do not alter or rerun the hosted campaign.
- First replay the seven recorded failures only to audit deterministic reproduction and population-CMI arithmetic. Label those results as forensic replays of consumed validation identities.
- Assess acceptance-cap sensitivity only on a fresh development cohort. Do not fit CIN models or calculate prediction metrics.
- Do not select or authorize a future validation cohort in this diagnostic. Any future validation identities must be distinct from prior campaign identities and these diagnostic identities.

## Predeclared development cohort and procedure

- Source revision: the current checked-out generator source; record its Git revision and source-file hash with the results.
- Generator case: F, 8 binary variables, 10 planted edges, `n=150`; population CMI floor `0.005`.
- Seed coordinates: master seed `20261003`, case index `5` (F in `ABCDEFGHI`), phase index `0` (development), replicate IDs `4000–4099`, using the repository's `derive_seed_bundle`; use each bundle's structure seed for graph/field generation and sample seed only for provenance.
- Search cap: run each identity once through at most 2,500 attempts and record its first accepted attempt. This yields paired descriptive outcomes at caps 500, 1,000, and 2,500 without changing seeds or refitting. No accepted draw after 2,500 remains a failure in the 2,500 denominator.
- Reproduction check: compare repository CMI values for the final attempt of each recorded validation failure with an independent entropy-identity calculation; record maximum absolute disagreement and per-identity threshold shortfall.
- Environment: run with local Python 3.11 and record NumPy/SciPy versions. Differences from the hosted Python/NumPy environment are a stated reproducibility limit.

## Interpretation rules

- Exact agreement of independent CMI calculations, plus all planted edges below `0.005` on the last attempt, supports a legitimate rejection rather than a CMI arithmetic defect for those replays.
- The fresh cohort estimates only generator yield under these seeds and this implementation/environment. It does not establish a future campaign completion rate or justify raising the cap.
- Any implementation correction requires a separately isolated root cause and regression test. Any protocol change requires a new freeze and a disjoint held-out validation cohort.
