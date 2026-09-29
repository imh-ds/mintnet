# CIN Focused F Follow-Up Charter v1

**Status:** Development-selected protocol candidate; source/config hashes and code fingerprint must be frozen in the committed manifest. No hosted phase is authorized by this charter.

**Version:** `cin-followup-f-v1`
**Scope:** Case F, binary categorical simulation, CIN only
**Parent evidence:** Frozen D-106 Task 11 artifacts and the audit in `docs/cin_followup_audit/d106/`
**Configuration:** `configs/cin_followup_v1.yaml`

## Question and hypothesis

Does a development-selected correction for F generator acceptance and/or rare-category inner-fold support increase the proportion of fresh F identities that yield a complete CIN result, while retaining every failed identity and leaving unavailable metrics unavailable?

The generator and fit failures are separate mechanisms. A generation error means the candidate dataset did not meet the configured population-CMI floor; an incomplete fit means at least one required pair remained unsupported. The study will preserve the 0.005 population-CMI floor and the existing target-support guard. It will not lower the floor, replace failed seeds, impute pair scores, or relabel failed rows as complete.

## Scope and claims

The study includes F only (`p=8`, binary variables, `n=150`), one CIN result per identity, and the 28 unordered variable pairs. It excludes all other panel cases, `cin_linear`, EBICglasso, AP-gain testing, stability resampling, and any claim about full-panel completion or network recovery. AP and truth-based edge metrics may be reported descriptively only for fully complete rows. A completion pass cannot be described as an accuracy or recovery pass.

D-106 remains immutable. Its validation identities `1000–1019`, the Task 3/4 exact-seed diagnostic identities, and D-106 development identities `0–9` are never reused as new development or validation data. No D-106 result selects a correction.

## Development stage

Run 20 new development identities, replicate IDs `2000–2019`, using only the development phase. For each identity, record the original expected key before generation so a generation failure remains in the denominator.

The development stage compares these predeclared generator attempt caps: `500`, `1,000`, and `2,500`. Keep the strict CMI floor at `0.005`; retain each identity and its attempt count in `generator_attempts`. The default runner remains at 500 unless the versioned config explicitly sets the F-only `f_max_tries` option. Select the smallest cap that generates all 20 development identities. If none does, do not proceed to validation with a generator candidate.

The fit candidate is a deterministic support-aware inner split for categorical targets. The outer split remains unchanged. For each outer-training partition, the splitter first makes the ordinary seeded inner split. If every inner-training partition already supports every categorical target, it preserves that split. Otherwise, it evaluates 255 further seeded balanced partitions and selects the one with the fewest unsupported categorical target/fold combinations, then the lowest normalized marginal category-count imbalance. It reads category codes only for rows in the current outer-training partition; outer evaluation rows are untouched. The existing target-support guard remains in place. Select the candidate only if it lowers the total unsupported-pair count over the development identities and does not make any previously complete pair unsupported. If the criterion is not met, retain the existing split. If the candidate split implementation is added after an initial baseline development run, rerun the full 20-identity development set under both baseline and candidate settings so the comparison is paired and reproducible. Any code/config change requires a new freeze record before validation.

### Development-only selection evidence

The 20 fresh development identities were evaluated locally with the repository Python 3.11 virtual environment, one numerical thread, and the package versions recorded in `requirements-cin-followup-v1.txt`. This is development evidence only; it is not held-out validation evidence and it does not authorize an Actions run.

| Selection | Baseline | Candidate | Result |
| --- | ---: | ---: | --- |
| Generator cap sweep, IDs 2000–2019 | 20/20 generated at 500 attempts | 20/20 generated at 1,000 and 2,500 also | Select the smallest qualifying cap: 500. Attempts ranged 6–292 (median 86.5); all three caps had identical attempt counts. |
| CIN fit completion, paired IDs 2000–2019 at cap 500 | 19/20 complete; 7 unsupported pairs | 20/20 complete; 0 unsupported pairs | One identity improved (2009); zero previously complete identities regressed. All structure, sample, fit seeds, and generator attempts match between arms. |

The selected fit candidate therefore satisfies the predeclared development rule on this 20-identity sample. It does not establish a completion probability or guarantee that validation will pass. The baseline and candidate raw development CSVs, sidecar manifests, and pair sidecars are retained under `docs/cin_followup_audit/followup_f/development/` with a comparison table and checksums.

If neither correction qualifies, stop without validation. If one or both qualify, freeze only the selected correction(s), implementation revision, environment, configuration, and all validation rules before opening validation outcomes.

## Validation design and outcome

Validation uses 97 fresh F identities, proposed replicate IDs `3000–3096`, disjoint from all prior identities and diagnostic seeds. The validation phase is run once after development selection and refreeze. Baseline and the single frozen candidate are evaluated on the same validation identities; they use identical structure/sample seeds. A larger generator attempt cap continues the deterministic candidate sequence beyond the baseline 500-attempt limit. The validation comparison is paired by identity.

The primary outcome for each identity is `complete` only when generation succeeds and all 28 CIN pair rows are complete. Every generation error, fit error, incomplete fit, missing row, or unavailable result counts as a non-complete identity. The primary candidate gate preserves the original strict completion threshold: `97/97` complete. The baseline comparison is reported as a paired diagnostic; it does not change the candidate denominator or gate. The result applies only to this F-focused follow-up, not to D-106's full-panel completion gate.

Report candidate and baseline complete counts, the paired completion table, a 95% Wilson interval for each completion proportion, generator attempt/failure taxonomy, unsupported-pair counts, sidecar integrity, and elapsed/runner time. Run `scripts/cin_followup_f_gate_check.py` on the candidate aggregate and provide the baseline aggregate with its own metadata and freeze manifest using `--baseline-raw`, `--baseline-metadata`, and `--baseline-freeze-manifest`; the report then validates both provenance records and emits the paired completion table. Keep AP null for every incomplete/error row. Report AP only for complete rows and label it descriptive. Do not substitute zeros or drop failures from the denominator.

The target sample size is 97 distinct identities to target a worst-case nominal 95% completion-proportion interval half-width near 0.10. The implementation freeze must record the exact Wilson interval width across possible counts for `n=97`; this is a precision target, not a rare-failure or tail-risk claim.

The exact 95% Wilson interval calculation gives a worst-case half-width of `0.0975835` at 48/97 completions. At 97/97 completions, the interval is approximately `[0.961906, 1.000000]`. This calculation supports the nominal precision target only; it does not establish a low failure rate or tail bound.

## Seed, environment, and identity rules

The configuration declares development IDs `2000–2019` and validation IDs `3000–3096`, with distinct deterministic seed bundles derived from master seed `20260928`. Before any F shard runs, the workflow invokes `python scripts/cin_followup_f_gate_check.py --config configs/cin_followup_v1.yaml --preflight-only --freeze-manifest <manifest> --code-revision <dispatch-sha>` and supplies `--support-aware-inner-splits false` for the baseline arm. This mechanically verifies the frozen source/config/charter/code/seed hashes, selected cap and split mode, compute ceiling, and all five seed streams against the complete D-106 historical development/validation rows and the explicit Task 3 F diagnostic inventory at `docs/cin_followup_audit/d106/diagnostic_seed_inventory.csv`; any mismatch blocks the shard. Also check unique `(case, phase, replicate, method)` keys and exact expected counts of 20 development and 97 validation identities. The validation gate repeats the seed check before it can pass.

The Actions environment is Ubuntu GitHub-hosted with Python 3.11, the exact package pins in `requirements-cin-followup-v1.txt`, and one-thread numerical library limits. The local development environment used Python 3.11.9 with NumPy 2.4.6, pandas 3.0.5, SciPy 1.17.1, scikit-learn 1.9.0, PyYAML 6.0.3, threadpoolctl 3.6.0, and matplotlib 3.11.1. Record Python/package/platform/thread metadata per shard, source and resolved config hashes, charter hash, dispatch revision, frozen source-code fingerprint, and raw aggregate hash. The source-code fingerprint covers the CIN config/fit/runner/generator, this gate checker, both aggregators, the Actions workflow, and the dependency lock. A manual Actions shard must pass the frozen preflight guard before running.

## Failure, retry, and stopping rules

- A generator's 500/1,000/2,500 attempt limit is a method setting, not permission to change the replicate identity. Do not retry with a replacement seed.
- If a hosted shard fails operationally before producing complete artifacts, rerun only that same shard and same identities under the frozen commit; preserve the failed attempt and all logs. Do not inspect partial statistical outcomes to decide whether to retry.
- If a shard returns a valid row with `error` or `incomplete`, retain it as an outcome; do not retry it as if it were infrastructure failure.
- Abort aggregation on a missing, duplicate, foreign, mixed-phase, changed-hash, missing-sidecar, tampered-sidecar, or orphan-sidecar condition.
- Do not dispatch validation if development selects no correction, if validation identities collide, if any freeze hash changes, or if the compute ceiling would be exceeded.
- Do not tune, modify code, or change stopping/retry rules after validation begins.

## Stability and compute

Stability resampling is excluded from this protocol. D-106 stability identity/method selection was ambiguous and it has no gate; this study will make no stability claim.

The combined development-plus-validation ceiling is **1.25 runner-hours**, including candidate comparisons, all shards, sidecars, aggregation, and one full operational replay. This estimate uses 23 hosted jobs: three generator-cap runs, paired baseline/candidate development runs, paired baseline/candidate validation runs (two validation shards per arm), and each workflow's plan and aggregation jobs. Applying Task 11's observed average runner time per job to each phase gives a conservative one-pass estimate of 0.585 runner-hours (5 development shards at 125 seconds each, 4 validation shards at 216 seconds each, and 14 plan/aggregate jobs at the Task 10 average of 44 seconds each). Doubling this to cover one complete replay gives 1.17 hours; the ceiling rounds that up to 1.25. The estimate is deliberately based on broader historical jobs even though this F-only work excludes stability and comparator methods. Expected wall time is approximately 15–30 minutes if the seven workflow runs proceed sequentially, and up to about an hour with one full replay or queue delays. This is still an estimate, not hosted timing evidence. The prior 12-hour Task 11 cap is not authorization or budget for this study.

A local correctness smoke on the separate diagnostic identity `F/development/4000` (`n=150`, 28 pairs) completed all pairs in `0.186281` seconds. The development comparison also measured fit elapsed time: baseline median/max `0.125/0.484` seconds and candidate median/max `0.125/0.188` seconds in the same local environment. These timings exclude GitHub-hosted startup, queue delays, shard upload/download, and operational retries; the 1.25 runner-hour ceiling therefore uses historical hosted job timing instead. A deterministic archived-failure diagnostic confirms that cap 2,500 accepts at attempt `502` and repeats identically. That replay is diagnostic only, not new campaign evidence.

## GitHub Actions dispatch sequence

Use `.github/workflows/sharded_benchmark.yml`, `mintnet.experiments.cin_baseline`, `configs/cin_followup_v1.yaml`, and case `F`. Set `dim1_flag=--cases`, `dim1_values=F`, and `dim2_flag=--replicate-batches`. For development cap comparison, use `dim2_values=dev0`, `dim3_flag=--f-max-tries`, and three separate runs with `dim3_values` `500`, `1000`, and `2500`; these runs are completed locally for selection, and the hosted Task 8 may reproduce them before its final refreeze. Do not combine caps into one aggregate because their identity keys are identical. For the paired baseline development arm, pass `dim3_flag=--support-aware-inner-splits` and `dim3_values=false`; for the candidate arm, omit dim3 so the frozen config uses `true`. For validation, use `dim2_values=val0,val1` and run both baseline and candidate arms separately. Supply the corresponding committed freeze manifest to each dispatch and set aggregation phase explicitly. The workflow rejects generator-cap overrides after freeze and runs the seed/hash/revision/budget preflight before any F shard. Store artifacts under a versioned `cin_followup_f_v1` name/path and do not overwrite D-106.

This charter itself does not authorize either dispatch. The exact workflow inputs, frozen hashes, implementation revision/fingerprint, expected runner-hours, and expected wall-clock duration must be presented to the owner before a separate dispatch authorization.
