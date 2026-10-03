# F Full-Pipeline Development Cap Comparison Protocol

**Purpose:** Determine whether increasing the F generator attempt cap from 500 to 1,000 reduces generation-stage failures without shifting fit-completion behavior, creating unacceptable runtime, or changing generated-data characteristics for identities already accepted within 500 attempts. This is a development experiment only; it cannot pass or replace the frozen validation gate.

## Frozen cohort and inputs

- Source revision: the commit containing this protocol, config, and driver. Record the exact revision and source hashes in the results.
- Config: `configs/cin_f_cap_full_pipeline_dev_20261004.yaml`.
- Case F, `n=150`, master seed `20261004`, development replicates `5000–5099`, using the repository seed bundle at F case index 5 and development phase index 0.
- The historical `validation_replicates` field in the runner config is present only because the schema requires a nonempty development and validation list. The driver runs only `dev0`; it must not dispatch or generate the validation phase.
- Run the selected support-aware candidate (`support_aware_inner_splits=true`) at attempt caps 500 and 1,000 with every other fit, score, and generator parameter held fixed. Use the same seed bundle in both arms. The 500 arm runs first and is retained even if the second arm fails.
- One sequential worker; no stability resampling; no baseline comparator arm; no cap or threshold search beyond the paired 500/1,000 comparison.
- Record all 100 rows, including generation errors and fit-incomplete rows, in each arm's denominator.

## Outcomes and checks

1. Generation: errors and attempts consumed, by identity and in total.
2. Fit completion: complete/incomplete/error counts, pair completeness, and paired status transitions between caps.
3. Runtime: per-identity elapsed and point-fit seconds, plus total runner time from provenance metadata.
4. Generated-data characteristics: deterministic frame hash, planted edge count, accepted planted-edge population-CMI minimum/median/maximum, strong-edge count at `0.01`, observed levels per node, and minimum observed level count. All accepted data must satisfy the `0.005` population-CMI floor.
5. Pair identity check: identities accepted at both caps must produce the same accepted frame hash, generator attempt count, planted edges, and population-CMI summary. A difference is a stop-and-investigate condition.
6. Report exact local Python/NumPy/SciPy/scikit-learn versions and mark results as local development evidence. Do not claim they reproduce hosted package versions.

## Decision rules

- Retain the 500-attempt result as the reference and do not omit failed identities from denominators.
- Consider a production cap change only if the 1,000 arm removes generation failures, does not introduce fit regressions on paired generated identities, stays within the predeclared 600-second per-fit limit, and preserves the accepted-data contract. Report descriptive differences; do not tune against AP or treat this 100-identity cohort as validation.
- If generation, fit status, data identity, or provenance checks fail unexpectedly, stop and diagnose before any protocol change.
- A future strict validation must use a separately frozen source/config/environment and new identities disjoint from the D-106 data, the hosted 3,000–3,096 cohort, the generator-only 4,000–4,099 cohort, and this 5,000–5,099 development cohort.
