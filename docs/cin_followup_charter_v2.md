# CIN Focused F Follow-Up Charter v2

**Status:** Frozen protocol candidate for dispatch review. The committed freeze manifest, source/config/charter hashes, seed inventory, and source-code fingerprint must all pass the local preflight tests. This charter does not authorize a GitHub Actions run.

**Protocol:** `cin-followup-f-v2`\
**Scope:** F-only categorical simulation, CIN, `n=150`\
**Parent:** D-106 and the Task 11 F follow-up; all prior outcomes remain immutable.

## Question and claim boundary

The question is whether a prospectively selected F-only implementation candidate can meet the strict completion gate on a new, disjoint hosted cohort. The candidate combines two development-supported changes: increase the finite F generator attempt cap from 500 to 1,000 while preserving the population-CMI floor at 0.005, and use the deterministic support-aware inner split while retaining the existing target-support guard. The effects are separate mechanisms, but this single-candidate validation does not estimate their individual causal contributions.

The endpoint is a named, prospective amendment to the F completion protocol. It does not amend or replace D-106, its 400-row full-panel result, the Task 11 validation, or any earlier F follow-up outcome. It makes no claim about E nonlinear gain, other panel cases, AP or edge-recovery success, rare failure rates, tail risk, FDR, stability, or broad CIN recovery. AP and truth-based metrics may be reported descriptively only for fully complete rows.

## Development evidence and fixed candidate

Candidate selection used separate development evidence already recorded in the repository:

- The paired support-aware split study on identities 2000–2019 improved completion from 19/20 to 20/20 and unsupported pairs from 7/560 to 0/560, with no previously complete identity regressing.
- The generator-only cap study on 4000–4099 accepted 96/100 identities by 500 attempts and 100/100 by 1,000.
- The full-pipeline paired cap study on 5000–5099 completed 98/100 at cap 500 and 100/100 at cap 1,000. Both cap-500 generation errors first passed at attempt 536 under cap 1,000; all 98 shared datasets and non-timing fit metrics were identical.

All are development/diagnostic evidence, not held-out validation. The frozen candidate uses `f_max_tries=1000` and `support_aware_inner_splits=true`. Do not lower the CMI floor, alter the graph/data-generation rules, change fit settings, or select another candidate after validation starts.

## Cohorts and seed rules

Use master seed `20261006`, with development replicates 6400–6419 and validation replicates 6500–6596. A separate correctness-only smoke uses diagnostic identity 6300 and records all five seeds in the diagnostic inventory; it is not part of either campaign cohort. These ranges are disjoint from D-106, the consumed Task 11 F cohort 3000–3096, prior development identities 2000–2019, generator diagnostics 4000–4099, and cap-comparison identities 5000–5099. The gate preflight also compares every proposed five-stream bundle against the preserved raw seed rows and diagnostic inventory, rather than relying on replicate labels alone. Any collision blocks dispatch.

Development runs the single frozen candidate over all 20 development identities. Keep generation errors, fit errors, incomplete fits, missing rows, and unavailable metrics in the denominator. The development checkpoint is operational: preserve the 20 expected rows and their sidecars; if any identity is non-complete, stop for diagnosis without opening validation. Any code, config, environment, or candidate change requires a new versioned freeze and new, disjoint validation identities.

Validation uses 97 identities and runs once after the development checkpoint and preflight. The candidate is the sole validation arm. No baseline refit is needed for the primary claim; previous-cohort rows are not treated as a paired comparator. The fixed primary gate is **97/97 complete**, with complete defined as successful generation and all 28 CIN pair fits complete. Any generation error, fit error, incomplete pair set, missing or duplicate identity, or unavailable result is a non-complete outcome. Never replace a seed or retry an outcome row.

Report the completion numerator/denominator, two-sided 95% Wilson interval, all identity statuses and generator attempts, and sidecar integrity. AP remains null on every incomplete/error row. Do not convert unavailable values to zero or drop failures.

## Precision and compute

For `n=97`, the two-sided 95% Wilson interval has worst-case half-width `0.0975835` at 48 completions; at 97/97 its lower bound is approximately `0.961906`. This is a nominal completion-proportion precision target only and cannot support a rare-failure or tail-risk claim.

The combined development and validation estimate is **0.24 runner-hours**, with a strict **0.50 runner-hour ceiling**. The estimate is bounded against the previous hosted F campaign's 0.239 runner-hours across ten attempts (two arms, including failed infrastructure aggregates) and the local cap-1,000 full-pipeline runtime of 120.71 seconds for 100 identities. It includes one candidate development cohort, one candidate validation cohort, generation, fitting, pair sidecars, plan/shard/aggregate overhead, and one outcome-independent operational recovery allowance. Stability resampling is excluded. The retry allowance applies only when infrastructure prevents a valid artifact from being produced; a statistically non-complete identity is retained and is never rerun. Stop before dispatch if preflight shows the ceiling could be exceeded. The historical 12-hour envelope is not authorization or budget for this protocol.

The hosted environment is Python 3.11 with the exact dependency pins in `requirements-cin-followup-v1.txt`; use the matching lock file in every shard and aggregate job. Record the actual Python, package, OS, thread, source revision, config, charter, seed-inventory, sidecar, and raw-output hashes. Local development package-version differences are recorded in the development reports and limit timing comparability.

## Sharding and stop rules

Use `.github/workflows/sharded_benchmark.yml` with runner module `mintnet.experiments.cin_baseline`, config `configs/cin_followup_v2.yaml`, case `F`, and dimension 2 `--replicate-batches`. Run development as `dev0` and aggregate explicitly as `development`. After reviewing those development artifacts, run validation once with `val0,val1` in the same workflow and aggregate explicitly as `validation`. Omit dimension 3 so the frozen config's cap and split setting are used. Supply the committed `freeze_candidate_v2.json` and dispatch from its documented frozen source revision or a docs-only descendant that passes the code fingerprint check.

The workflow preflight must reject a missing/draft manifest, changed charter/config/source fingerprint, changed identity or seed inventory, altered cap/split mode, unsupported runner, or budget mismatch before any shard starts. Aggregation and the F gate reject missing, duplicate, foreign, mixed-phase, or malformed rows; missing, orphaned, or tampered sidecars; invalid seed bundles; fabricated AP on incomplete rows; and any validation identity count other than 97. Retain failed infrastructure attempts and logs. Do not use partial statistical outcomes to trigger retries or stopping.

This package ends at the dispatch review gate. No hosted development or validation run may start until the owner separately approves the exact workflow inputs, identity ranges, freeze hashes, estimate, and ceiling.
