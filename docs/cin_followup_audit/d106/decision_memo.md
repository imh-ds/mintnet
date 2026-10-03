# D-106 Follow-Up Decision Memo

## Current disposition — amended 2026-10-03

**F-only: go to Task 7 protocol freeze. E: no-go. Hosted dispatch: not authorized.** This amendment incorporates the fresh development-only cap comparison completed after the original 2026-09-27 decision. It supersedes that decision only for whether a narrowly scoped F completion follow-up merits protocol-freeze work. It does not alter D-106, its failed validation result, or any frozen gate.

The claim at stake is whether the F generator's finite 500-attempt limit caused avoidable generation failures and whether a separately frozen cap-1,000 candidate can satisfy the existing strict completion criterion on fresh hosted identities. The cap-1,000 full-pipeline development comparison found 98/100 complete at cap 500 and 100/100 at cap 1,000; the two cap-500 generation errors first passed at attempt 536 under cap 1,000. The 98 shared accepted datasets had identical hashes, attempt counts, planted edges, population-CMI summaries, and non-timing fit metrics. No fit-incomplete rows occurred. Together with the earlier generator-only audit (96/100 accepted by 500 versus 100/100 by 1,000), this identifies finite-cap censoring as the supported operational mechanism in development data. It does not prove future 100% completion, and the comparison was local under older numerical-package versions than the hosted validation environment.

The F-only follow-up should test a **candidate with the cap set to 1,000 and the development-selected support-aware inner split**, preserving the 0.005 population-CMI acceptance floor, generator construction, metrics, sidecar contract, target-support guard, and strict completion gate. The primary estimand is the proportion of distinct, independently generated F datasets that yield a complete CIN result under the frozen candidate. Keep every expected identity in the denominator; do not replace failures. The pass gate remains **97/97 complete**, matching the established strict completion rule's all-complete requirement at its prior 97-identity cohort size. The proposed disjoint cohorts are 20 development identities (6400–6419) followed by 97 validation identities (6500–6596), using a new master seed and a preflight check against prior raw seed records. The separate correctness-only smoke identity 6300 is excluded from both cohorts and included in the diagnostic seed inventory. This campaign would assess only F generation and pipeline completion; it would not validate broad recovery, rare-failure rates, tail risk, FDR, fit quality beyond completion, or panel-wide stability.

For planning precision, use the two-sided 95% Wilson score interval and target a worst-case half-width no greater than 0.10. At the binomial worst case `p=0.5`, the minimum is 93 identities (Wilson half-width 0.09958). Retain **97 fresh validation identities** for the proposed protocol: this gives a worst-case Wilson half-width of 0.09759 and preserves the established cohort size and strict 97/97 gate. Even 97/97 successes has a two-sided 95% Wilson lower bound of about 0.9619, so this design cannot support a rare-failure claim. These calculations size a future frozen study; they do not treat the 100/100 development observation as validation evidence.

The proposed combined development-plus-validation estimate is **about 0.24 runner-hours**, with a **0.50 runner-hour hard ceiling** for one 20-identity development cohort and one 97-identity cap-1,000 validation arm, including generation, fitting, sidecars, aggregation, ordinary hosted overhead, and one outcome-independent technical recovery allowance. The local cap-1,000 run used 120.71 seconds for 100 identities (about 0.0325 hours when scaled to 97) before hosted orchestration overhead. As an empirical hosted upper reference, the earlier two-arm 97-identity F campaign consumed 0.239 runner-hours across ten attempts, including failed infrastructure aggregates and successful replays. The proposed single-candidate campaign is expected to use less compute, but the estimate is uncertain; the 0.50 ceiling is a conservative roughly 2.1× allowance over that two-arm observed total. Stability is excluded. Task 7 must specify retry eligibility and include generation, all methods, sidecars, shard and aggregation overhead, and ceiling enforcement in the frozen protocol. The historical 12-hour envelope is not authorization or available budget for this dispatch.

**Decision:** proceed to Task 7 to draft and test a separate F-only charter/config, reserve disjoint identities, and present the frozen package for review. Stop at Task 7's dispatch gate. Do not launch GitHub Actions until the frozen protocol, hashes, exact workflow inputs, and compute ceiling have been reviewed and separately authorized. The E shortfall remains unexplained; no independently testable E mechanism was established, so no E follow-up or broad campaign is recommended. This memo does not change or reinterpret the prior hosted validation result (candidate 90/97, baseline 88/97; strict completion gate failed).

### Evidence added for this amendment

- [Generator acceptance diagnosis](../followup_f/development/generator_acceptance_diagnosis.md): seven exact-seed validation replays plus the fresh 100-identity generator-only cap audit.
- [Full-pipeline cap comparison report](../followup_f/development/full_pipeline_cap_comparison_20261004/report.md) and [run manifest](../followup_f/development/full_pipeline_cap_comparison_20261004/run_manifest.json): paired 100-identity cap-500/cap-1,000 development results, environment, hashes, and runtimes. Protocol and result commits: `46c9b4b`, `08ff689`, and `872c5cf`.
- [Hosted F run log](../followup_f/hosted_run_log.md): prior two-arm 97-identity campaign and its 0.239 runner-hour total across ten workflow attempts.

## Historical decision — 2026-09-27

At that date this memo recommended **no-go for a new hosted benchmark**. That was the evidence-based decision before the full-pipeline cap comparison existed. The following historical analysis is retained as originally recorded; the dated amendment above updates the current F-only disposition without rewriting D-106 or the historical gate outcome.

## Claim at stake and evidence

The claim at stake is whether the CIN Task 11 panel met its frozen completion and nonlinear-gain criteria, and whether the audited F failures reflect a software defect that needs correction before those results can be interpreted.

| Scope | Evidence | Classification | Audit conclusion |
| --- | --- | --- | --- |
| D-106 source and accounting | 30 archived shard ZIPs and their 816 members are inventoried and hash-verified. The original local aggregate, development selection, gate file, and report bytes are unavailable. | Provenance limitation | Archived source rows are sufficient to reconstruct identities and reported arithmetic, but not to authenticate the missing original output bytes. |
| Completion | Reconstructed validation has 396 complete, two incomplete, and two generation-error method rows out of 400. All four are F. | Confirmed frozen-gate failure; no general implementation defect demonstrated | The exact-seed F replay reproduces the two generator rejections and two unsupported partial fits. Failures stay in the denominator; unavailable AP stays unavailable. |
| E nonlinear gain | Twenty matched validation pairs reproduce mean CIN AP 0.7416081, mean CIN-linear AP 0.6924976, and paired mean difference 0.0491106 against the unchanged 0.10 threshold. | Confirmed frozen-gate failure; cause unresolved | Pairing and gate arithmetic are correct. The data do not identify an independently testable mechanism for the shortfall. E remains unsupported under the frozen claim. |
| Stability | Archived sidecars contain 98 validation stability manifests, rather than the three datasets described in the build plan; the charter/config do not identify exact rows or methods. | Confirmed protocol inconsistency; descriptive data only | Do not treat the emitted stability runs as a prespecified pass/fail gate or broaden a stability claim from them. |
| Phase-only aggregation | The old revision rejected the valid 400-row validation phase as short of the 600-row full grid. Current phase-aware aggregation checks phase identities; new exact 200/400/600 fixtures pass. | Historical infrastructure defect, already corrected | No method or gate change is needed. Current validation-only dispatch must explicitly select `validation` because the workflow default is `full`. |

The four F rows have two distinct mechanisms. Replicates 1004 and 1012 exhaust the frozen 500-candidate rejection limit because no sampled candidate meets the strict 0.005 population-CMI floor. Replicates 1003 and 1011 produce datasets but have one inner training split missing a rare category, so seven target-incident pairs remain unsupported and AP is correctly blank. Replay used the exact historical seeds only as diagnosis; it did not resample or replace validation identities. No production defect was reproduced and no estimator, generator, retry policy, score, or gate was changed.

## Go/no-go rationale

Do not run a broad follow-up campaign now. A repeat of the unchanged frozen method would spend compute without testing a new corrective hypothesis: the F behavior is reproduced as rejection and support limitations, while the E arithmetic is sound and its mechanism remains unresolved. A campaign to tune those mechanisms against validation would violate the evidence boundary. A future study would need development-only work to propose and justify a generator or support-handling change, followed by a newly frozen protocol and fresh, disjoint identities. The existing evidence does **not** establish broad recovery, reliable F completion, a general nonlinear advantage, or panel-wide stability.

The prospective sample-size calculation is therefore an explicitly conservative planning illustration, not a recommendation to dispatch. For a future F-only completion-rate endpoint, target a 95% interval half-width of at most 0.10 for the proportion of independently generated F datasets yielding complete CIN rows. Development has only 10/10 complete F rows, which is too little evidence to estimate the failure rate. Using the binomial worst case `p=0.5`, a normal-approximation planning formula gives `n = ceil(1.96^2 * 0.25 / 0.10^2) = 97` distinct F datasets. The final count and interval would need exact Wilson/binomial recalculation in the frozen protocol, and this size would not justify a rare-failure or tail-risk claim. Do not count method rows as independent datasets, and do not use D-106 validation outcomes as development data. The E scope has no prospective sample size here because no independently testable E mechanism was identified.

## Compute and dispatch boundary

The historical Task 11 ledger records 0.4175 runner-hours for development and 1.319722 runner-hours for validation. Those runs cover different phases and a broad panel, including stability work; they are not a reliable linear cost model for an F-only design. Since this memo recommends no campaign and no protocol is frozen, it assigns **no new runner-hour ceiling**. Any future proposal must estimate generation, fit, stability (if prespecified), sidecars, shard overhead, retries, aggregation, and hosted-run variance from a development pilot, then set a new explicit ceiling. The historical 12-hour envelope is not new dispatch authorization.

Task 7 protocol freezing is not triggered by this no-go recommendation. Task 8 remains separately unauthorized. No hosted job was run.

## Evidence references

- [Source custody and provenance](provenance.md)
- [Reconstructed identities, sidecars, and frozen gates](reconstruction.md)
- [F failure diagnosis](f_failures.md)
- [E nonlinear-gain audit](e_nonlinear_gain.md)
- [Stability and phase-aggregation audit](protocol_infrastructure.md)
- [20-row E paired table](e_pairs.csv)
- [Reconstructed gate results](reconstructed_gate_results.json)
