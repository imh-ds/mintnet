# CIN Follow-up Campaign and Failure Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct and diagnose D-106 without altering it, repair any proven infrastructure or implementation defects, and run a new preregistered campaign only if an evidence-backed decision memo warrants one.

**Architecture:** Keep forensic scripts and copied evidence in a new versioned audit area. Reuse the existing CIN runner, phase-aware shard aggregator, sidecar validator, reporting module, and gate checker; add focused diagnostic code only where manual inspection cannot be reproduced. Separate the audit, infrastructure corrections, protocol freeze, development, and one held-out validation with explicit stop gates.

**Tech Stack:** Python 3.11, NumPy, pandas, SciPy, scikit-learn, PyYAML, pytest, Ruff, PowerShell, GitHub Actions, CSV/JSON/Markdown.

**Spec:** `docs/design/cin/build-plan/13_followup_campaign_and_failure_audit.md`; also read `docs/cin_baseline_charter.md`, `docs/design/cin/build-plan/11_statistical_panel.md`, `docs/cin_cost_charter.md`, D-106/D-107 in `docs/decision_log.md`, and `docs/cin_user_guide.md` before implementation.

## Global Constraints

- D-106 development run `36216599775`, validation run `36217428583`, revision `6f2f86c`, charter SHA-256 `0e846c6445ff4eac87c49db336ba714c86faa12facf8794080155c784c970d7c`, selection `delta=0.005`, and D-106/D-107 decisions are immutable historical evidence.
- D-106 validation expected exactly 400 method-dataset rows: 20 replicates for each case, three methods for A–E and CIN alone for F–I and `regression`. The recorded outcomes are 396 complete, two incomplete, and two generation errors; independently verify before interpreting them.
- Preserve original gate definitions, especially completion `1.0` and E nonlinear AP gain `0.10`. The observed E value `0.049111` is a failed D-106 gate, never a tuning target.
- Never rerun D-106 validation seeds as a new validation campaign; deterministic replay of individual failures is diagnostic only and must be labeled as such.
- Keep failed and unavailable identities in denominators. Do not replace failed draws or convert unavailable AP to zero. Distinguish method rows from unique generated datasets.
- Follow-up validation identities must be fresh and disjoint from Task 11 development, validation, and all diagnostic identities used for decisions. Freeze the charter, config, code revision, environment, sample size, gates, retry rule, and compute ceiling first.
- The Task 11 12 runner-hour envelope is historical, not authorization for new dispatch. No new hosted run is authorized by the source audit plan; leave dispatch as a separately reviewed execution step.
- Existing unsupported boundaries remain unsupported until their own prespecified evidence passes: broad continuous recovery, high-p categorical recovery, low-N recovery, and panel-wide stability.
- Preserve the user's unrelated working-tree changes. This checkout already contains uncommitted files; stage only files belonging to each completed task.

## Review Focus

- Missing or duplicate `(case, phase, replicate, method)` keys must fail before metrics are summarized; cover this in Task 2.
- A valid 400-row validation-only aggregate must succeed while a mixed-phase or foreign-seed input fails; cover this in Task 5.
- Missing, tampered, or orphaned pair/stability sidecars must fail provenance checks; cover this in Task 2 and Task 5.
- A complete row with nonfinite pair scores or an incomplete row with fabricated AP must be rejected or explicitly marked unavailable; cover this in Task 3 and Task 5.
- A follow-up protocol that overlaps any prior or diagnostic seed, exceeds budget, or changes after freeze must block dispatch; cover this in Task 7.

## Files and ownership

| File | Responsibility |
| --- | --- |
| `docs/cin_followup_audit/d106/` | New immutable copies, hashes, inventory, reconstructed tables, diagnostic outputs, and audit memo. Create only after retrieving artifacts; never put generated output into the frozen D-106 source directory. |
| `scripts/cin_followup_audit.py` | If needed, reusable read-only artifact/identity and paired-E audit CLI; no fitting or dispatch. |
| `tests/unit/test_cin_followup_audit.py` | Synthetic fixtures for identity, denominator, and E pairing rules if the audit CLI is added. |
| `src/mintnet/simulation/cin_networks.py` and `tests/unit/cin/test_simulation.py` | Conditional F generator/CMI correction and deterministic regression tests. |
| `src/mintnet/cin/fit.py`, `src/mintnet/cin/scores.py`, and corresponding `tests/unit/cin/` tests | Conditional fit or score correction only after a root cause is established. |
| `src/mintnet/experiments/cin_baseline.py`, `src/mintnet/experiments/cin_baseline_reporting.py`, and `tests/integration/test_cin_runners.py` | Row status, complete-pair metric, runner provenance, and report contracts. |
| `scripts/aggregate_shards.py`, `scripts/aggregate_cin_sidecars.py`, `.github/workflows/sharded_benchmark.yml`, `tests/unit/test_aggregate_shards.py`, and `tests/integration/test_cin_runners.py` | Phase-aware aggregation and shard/sidecar integrity. The current checkout already has `--phase`; verify its behavior before editing. |
| `scripts/cin_gate_check.py` and `tests/unit/test_cin_gate_check.py` | Frozen gate arithmetic and provenance; add audit checks only if reconstruction reveals a defect. A new endpoint belongs in a separately versioned checker. |
| `docs/cin_followup_charter_v1.md`, `configs/cin_followup_v1.yaml`, `docs/cin_compute_ledger.csv` | Conditional follow-up protocol and compute accounting. Never rewrite the original charter/config. |
| `docs/decision_log.md` and `docs/cin_user_guide.md` | Append a new decision and adjust claim boundaries only after new evidence reaches a decision. |

## Task 1: Establish custody and freeze the audit inputs

**Deliverable:** `docs/cin_followup_audit/d106/provenance.md` plus a machine-readable file inventory; no benchmark execution.

- [ ] **Step 1: Inventory available artifacts.** From D-106's two Actions runs, record the run URL, artifact ID/name, download timestamp, local relative path, byte size, and SHA-256 for every shard, aggregate, sidecar, manifest, selection file, gate output, resolved config, metadata file, and report. Use `gh run view 36216599775 --json artifacts,url,headSha` and the analogous validation command if `gh` supports those fields; otherwise use `gh api repos/imh-ds/mintnet/actions/runs/<id>/artifacts`. Download into a new audit directory without overwriting existing files. If access is unavailable, list the exact missing artifact and continue with available evidence.
- [ ] **Step 2: Verify custody.** Hash each downloaded file using `Get-FileHash -Algorithm SHA256`; compare `metadata.json` fields `git_commit`, `source_config_sha256`, `config_sha256`, `charter_sha256`, and `aggregated_raw_metrics_sha256` with the recorded file bytes. Confirm the normalized charter hash equals the D-106 value above. Record any mismatch as a provenance defect.
- [ ] **Step 3: Lock the original evidence.** Write a `files.csv` with `run_id,artifact_id,relative_path,size_bytes,sha256` and a provenance note showing which archive is source versus reconstructed copy. Do not edit the downloaded source files.
- [ ] **Step 4: Check the inventory.** Rehash every `files.csv` entry with a short read-only verifier or PowerShell loop; pass when every digest and byte count matches. Commit only the inventory/note and any small reproducible verifier, not large generated archives unless repository policy already tracks them.

## Task 2: Reconstruct the D-106 table and gate inputs

**Interfaces:** Consume `load_config(Path)`, `expected_identities(config, phase="validation")`, `aggregate(..., phase="validation")`, `aggregate_sidecars(..., phase="validation")`, and `evaluate_validation_gates(...)` from existing modules. If a helper is needed, create `audit_validation(raw: pd.DataFrame, config: PanelConfig) -> dict[str, object]` in `scripts/cin_followup_audit.py`; it returns missing/duplicate/foreign keys, status counts, and paired E rows without fitting.

- [ ] **Step 1: Write failing fixture tests for the audit helper if added.** In `tests/unit/test_cin_followup_audit.py`, assert that the 400-key fixture has no key errors, that one duplicate plus one missing key is reported separately even when row count stays 400, that F error/incomplete rows stay in the denominator, and that E pairing uses only identical replicate IDs with one `cin` and one `cin_linear` AP each. Assert a missing E AP is recorded as unavailable, not zero.
- [ ] **Step 2: Run focused tests.** Set `$env:PYTHONPATH = 'src;.'`; run `python -m pytest tests/unit/test_cin_followup_audit.py -q`. Expected before implementation: failure only for the missing helper, if introduced.
- [ ] **Step 3: Reconstruct from archived bytes.** Use the archived revision/config/charter and invoke `python scripts/aggregate_shards.py --module mintnet.experiments.cin_baseline --config <frozen-config> --shards-dir <validation-shards> --output <new-audit-output> --phase validation`. Then invoke `python scripts/cin_gate_check.py --raw <new-audit-output>/raw_metrics.csv --config <frozen-config> --selection <frozen-development-selection> --provenance <new-audit-output>/metadata.json --output <new-audit-output>/gates.json`. Keep the current revision's result separate from an archived-revision reproduction and record both revisions.
- [ ] **Step 4: Independently calculate identity and metric checks.** Compare observed keys to `expected_identities`; tabulate counts by `case,method,status,error_type`, sidecar promises and manifest counts, and the four F identities. Pivot E on replicate and compute `mean(AP_cin) - mean(AP_cin_linear)` and mean of paired differences, verifying both methods contribute the same 20 identities. Confirm `396/400`, the two F errors at 1004/1012, the two F incomplete rows at 1003/1011, and E `0.049111` to the gate output's displayed precision; report deviations rather than forcing agreement.
- [ ] **Step 5: Verify sidecar chain.** For each non-complete F row, trace shard row, generated dataset or exception, pair sidecar if promised, manifest entry, aggregate row, and gate input. Confirm a generation error has no fabricated sidecar and that incomplete fits retain their seven failed pairs. Run `python -m pytest tests/unit/test_cin_gate_check.py tests/unit/test_cin_baseline_reporting.py tests/integration/test_cin_runners.py -k 'sidecar or gate or phase_aggregator' -q`; expected PASS on current code.
- [ ] **Step 6: Save `reconstruction.md`, `validation_identity.csv`, `status_counts.csv`, `e_pairs.csv`, and reconstructed gate JSON.** State precisely which checks were possible if any archive is missing. Commit audit code/tests separately from copied evidence.

## Task 3: Diagnose F generation and fit failures one identity at a time

**Deliverable:** `docs/cin_followup_audit/d106/f_failures.md` with one row each for F/1003, 1004, 1011, 1012; code changes are conditional.

- [ ] **Step 1: Trace deterministic inputs.** Read `derive_seed_bundle` use in `src/mintnet/experiments/cin_baseline.py`, `_sample_finite_case` and `exact_cmi_from_joint` in `src/mintnet/simulation/cin_networks.py`, and the archived raw `structure_seed`/`sample_seed`. For each F error, replay `generate_case("F", structure_seed=<archived>, sample_seed=<archived>)` in an isolated diagnostic process at the archived revision and environment. Mark this as replay of exposed validation identities, not new validation evidence.
- [ ] **Step 2: Audit the floor.** Save the final attempted graph/fields/interactions if safely obtainable without changing the baseline generator; independently calculate exact CMI from the normalized joint tensor using a second implementation or high precision reference. Compare every true edge with the `0.005` floor at full precision, including dtype, level order, rare/zero cells, normalization, and the 500-attempt stopping rule. Determine whether the exception is a legitimate rejected draw, numerical boundary, or implementation defect. Do not resample the same identity.
- [ ] **Step 3: Audit the two incomplete fits.** Load each pair sidecar and list the seven non-complete unordered pairs, pair status, node/category levels, retained counts, folds, fit diagnostics, clipping/floor/fallback flags, and elapsed budget. Compare overlap between 1003 and 1011. Check `src/mintnet/cin/fit.py`, `scores.py`, `_run_method`, and `_metrics` to verify that incomplete AP is unavailable and no zero substitutes for a missing score.
- [ ] **Step 4: Add a regression test only for a proven root cause.** If generator arithmetic is wrong, add a deterministic F fixture in `tests/unit/cin/test_simulation.py` asserting the corrected population joint and edge CMI; then make the minimal generator correction. If fit status or score arithmetic is wrong, add the exact failed pattern in `tests/unit/cin/test_fit.py` or `test_scores.py` and correct only that path. If the draw is a valid hard case, change no method code and document the limitation.
- [ ] **Step 5: Verify any correction.** Run the new focused test before and after the edit, then `python -m pytest tests/unit/cin/test_simulation.py tests/unit/cin/test_fit.py tests/unit/cin/test_scores.py tests/integration/test_cin_runners.py -q`. Expected final PASS; separately show that D-106 raw rows and gate output are unchanged. Commit each proven correction with its regression test.
- [ ] **Step 6: Write the four-row diagnosis table.** Columns: identity, stage, frozen status/error, affected pairs/nodes, reproduction result, causal evidence, severity, proposed action, and effect on future work. State whether F generation and fit failures share a cause; do not infer one from their shared case label.

## Task 4: Explain E nonlinear gain without retuning validation

**Deliverable:** `docs/cin_followup_audit/d106/e_nonlinear_gain.md` and a 20-row paired table.

- [ ] **Step 1: Use Task 2's `e_pairs.csv`.** Include replicate, AP for each method, paired difference, status, truth edge count, pair universe, complete-pair count, prevalence, and diagnostic flags. Calculate mean, sample standard deviation, median, range, Monte Carlo standard error `s/sqrt(20)`, and a labeled descriptive interval. Keep the original gate statistic and threshold unchanged.
- [ ] **Step 2: Verify common data and comparator contract.** Compare structure/sample seeds, truth edges, and generated draw hash for `cin` and `cin_linear` on each replicate. Check `_nonlinear_tree_result` in `src/mintnet/simulation/cin_networks.py` for the declared nonlinear map and oracle truth. Inspect `_fit_method` to confirm `cin_linear` differs only by intended curvature restriction; compare fold seeds, penalty grid, standardization, `max_curvature_rank`, selected penalties, dimensions, scores, floor hits, and runtimes.
- [ ] **Step 3: Classify the result.** Attribute the shortfall only where evidence supports a pipeline difference, generator/comparator mismatch, Monte Carlo variation, or implementation defect. If these cannot be separated, record unresolved. Any candidate model change must be mechanism-based and evaluated on development or newly designated diagnostic seeds, never selected using D-106 validation AP.
- [ ] **Step 4: Verify the arithmetic.** Add a focused regression test to `tests/unit/test_cin_gate_check.py` only if the current E gate calculation is wrong; the test must assert a pivot by replicate, equal contributor count, and `0.10` threshold. Run `python -m pytest tests/unit/test_cin_gate_check.py tests/unit/test_cin_baseline_reporting.py -q`; expected PASS. Do not modify D-106's decision.

## Task 5: Reconcile stability and phase-only aggregation

**Deliverable:** `docs/cin_followup_audit/d106/protocol_infrastructure.md` plus conditional infrastructure fixes.

- [ ] **Step 1: Build the stability matrix.** Compare Task 11 plan, frozen charter, `configs/cin_baseline.yaml`, hosted workflow inputs, shard raw fields, and stability manifests for cases A/B/F, `B=10`, fraction `0.8`, and 600-second estimate limit. Record requested and completed repeat IDs, statuses, and rows; if final outputs are absent, mark stability unavailable.
- [ ] **Step 2: Reproduce the historical 600-versus-400 failure at revision `6f2f86c` with a fixture or archived shard set.** Identify whether the old workflow omitted `aggregation_phase`, the aggregator ignored `--phase`, or the runner exposed only full-grid counts. The current checkout already implements `expected_row_count_for_phase`, `expected_identities(..., phase=...)`, and workflow `aggregation_phase`; verify their exact revision and behavior rather than reimplementing them blindly.
- [ ] **Step 3: Add or strengthen tests in `tests/unit/test_aggregate_shards.py` and `tests/integration/test_cin_runners.py`.** Assert development-only 200 and validation-only 400 rows aggregate, full-grid 600 rows aggregate, and duplicate/foreign/mixed-phase keys fail. Assert missing/tampered/orphaned sidecars, false pair promises, and missing stability repeat IDs fail before the output directory is published. Test empty view and failed-method report contributor counts in `tests/unit/test_cin_baseline_reporting.py` as needed.
- [ ] **Step 4: Run tests before any conditional edit, then correct the specific failing boundary.** Keep generic aggregation behavior for non-CIN runners intact. Run `python -m pytest tests/unit/test_aggregate_shards.py tests/unit/test_cin_baseline_reporting.py tests/unit/test_cin_gate_check.py tests/integration/test_cin_runners.py -q`; expected PASS. Run `python -m ruff check scripts/aggregate_shards.py scripts/aggregate_cin_sidecars.py src/mintnet/experiments/cin_baseline.py src/mintnet/experiments/cin_baseline_reporting.py` on changed paths.
- [ ] **Step 5: Record infrastructure revision and scope.** Include old/new commands, exact fixture counts, passed tests, and a sentence that operational repair does not alter E or completion statistical verdicts. Commit only changed code/tests/workflow, if any.

## Task 6: Make a go/no-go decision and size any new campaign

**Deliverable:** `docs/cin_followup_audit/d106/decision_memo.md`. This task may end the project with no new campaign.

- [ ] **Step 1: Classify each F identity and the E shortfall** as confirmed defect, supported limitation, Monte Carlo uncertainty, or unresolved. Decide separately whether F completion, E nonlinear gain, both as independent co-primary questions, or neither warrants fresh evidence.
- [ ] **Step 2: Calculate the prospective design from development/diagnostic data only.** Choose a target half-width for E AP-gain estimation or F completion probability, calculate required `n` using observed variability and an explicitly named interval method, and show the precision achievable at the proposed count. Do not claim precise rare-failure, FDR, or tail-error rates from 20 validation replicates.
- [ ] **Step 3: Reconcile compute.** Start from `docs/cin_compute_ledger.csv` (Task 10 `0.22`, Task 11 development `0.4175`, validation `1.319722` runner-hours); estimate generation, all methods, sidecars, optional stability, aggregation, retries, and hosted-run variance for the proposed design. Set a new explicit ceiling. The historical 12-hour cap is not new dispatch authorization.
- [ ] **Step 4: Write a decision memo.** Name the user-facing claim at stake, evidence for the hypothesis, scope, estimand/gate, precision target, sample count, runner-hour ceiling, and go/no-go rationale. If no independently testable E mechanism exists, record E unsupported and stop. If only accounting/documentation changed, stop without broad validation.

## Task 7: If go, freeze a separate protocol and prove dispatch guards

**Deliverable:** A reviewable `docs/cin_followup_charter_v1.md`, `configs/cin_followup_v1.yaml`, frozen hashes, and green local tests. Do this task only if Task 6 says go.

- [ ] **Step 1: Write the charter and config together.** Declare whether each scope is a named amendment or new endpoint; primary hypothesis, estimand, gate, cases/parameters, methods, failure denominator, sample count, development/validation identities, seed derivation, sharding, environment, stopping and retry rules, stability inclusion/exclusion, and compute ceiling. Keep original `0.10` E and `1.0` completion gates unless a scientifically justified amendment is explicitly labeled and frozen before new outcomes.
- [ ] **Step 2: Implement only needed config/runner extensions.** Add a separate config loader or narrowly parameterize `PanelConfig` in `src/mintnet/experiments/cin_baseline.py`; retain old config behavior and D-106-reproducible seed derivation. New seed ranges must be disjoint from `0..9`, `1000..1019`, and all Task 3/4 diagnostic seeds. If a new endpoint differs from Task 11, create `scripts/cin_followup_gate_check.py` instead of silently changing `scripts/cin_gate_check.py`.
- [ ] **Step 3: Write guard tests before implementation.** In `tests/integration/test_cin_runners.py` and the relevant gate test, assert fresh seed disjointness, exact expected keys, no duplicate/foreign rows, mandatory charter/config/provenance hashes, preserved failure rows, rejection of missing sidecars, and rejection of a changed frozen charter or code revision. Include fabricated pass, fail, incomplete, and unavailable rows. Run focused tests before and after the code edit.
- [ ] **Step 4: Run a correctness-only smoke with fresh diagnostic identities.** Aggregate by phase and evaluate fabricated gates; never use these identities as held-out validation. Run the focused tests, `python -m ruff check` on changed files, and `python -m pytest tests/unit/cin tests/unit/test_cin_gate_check.py tests/unit/test_aggregate_shards.py tests/integration/test_cin_runners.py -q`. Record commands/results, code revision, environment lock, charter/config SHA-256, and expected runner-hours in a freeze manifest.
- [ ] **Step 5: Stop at the dispatch gate.** Present the frozen protocol, exact workflow inputs, estimated runner-hours, and computed ceiling for review. Do not launch a hosted campaign merely because this plan exists.

## Task 8: If authorized, run development, refreeze, and validate once

**Deliverable:** New versioned follow-up evidence under `results/generated/cin_followup_v1/` or an equivalent archived Actions artifact; never overwrite D-106.

- [x] **Step 1: Dispatch only the charter's development identities.** Preserve raw method rows, pair/stability sidecars, manifests, resolved config, metadata, runtime, and failure taxonomy; append actual runner-hours to `docs/cin_compute_ledger.csv`.
- [x] **Step 2: Evaluate permitted corrections on development data.** Explain each mechanistically. If code/config changes, rerun the entire affected development scope, issue a new freeze manifest and revision, and do not carry validation outcomes between revisions.
- [x] **Step 3: Verify preflight.** Compare candidate validation identities against Task 11 and diagnostic sets, expected row count, config/charter/code/environment hashes, sidecar contract, and remaining compute headroom. Abort if any check fails.
- [x] **Step 4: Dispatch validation once.** Monitor operational health without using interim outcomes to tune or selectively stop. Apply only the frozen outcome-independent retry rule; retain all attempts and identities.
- [x] **Step 5: Aggregate and gate using the frozen revision.** Publish every expected identity, status, failure, unavailable metric, manifest, and gate contributor count. Recompute E paired AP difference and completion independently; note deviations. Append actual compute to the ledger.

## Task 9: Report and close out each scope

**Deliverable:** A reproducible report, new decision-log entry, and narrowly updated researcher guide if Task 8 was run; otherwise a closed audit memo with no new statistical claim.

- [x] **Step 1: Write the report.** Include provenance/hashes, exact commands, per-replicate E table, F failure table, uncertainty, missingness and denominators, stability outcome or explicit unavailability, cost, and verdict per independent scope. Compare to D-106 descriptively while keeping protocols and seeds separate; pool only if prespecified.
- [x] **Step 2: Append a new `docs/decision_log.md` entry.** Record charter/config hashes, code revision, Actions run/artifact IDs, sample counts, original versus amended endpoints, gates and observed values, failures, compute total, limitations, and exact user-facing claim boundary. Do not rewrite D-106 or D-107.
- [x] **Step 3: Update `docs/cin_user_guide.md` only where evidence changes a claim.** Preserve unsupported labels for scopes whose gates did not pass. Archive raw artifacts, manifests, frozen charter/config, selection, gate JSON, report, and audit memo together.
- [x] **Step 4: Final verification.** Rehash archived evidence, rerun read-only reconstruction commands, run the relevant focused tests and Ruff on changed code, and inspect `git diff --check` and `git status --short`. Commit only task-owned files.

## Completion criteria

- Every D-106 identity and gate input traces to hashed evidence, or each missing source is explicitly named.
- F's four non-complete rows have individual evidence-backed diagnoses or are explicitly unresolved; E's paired arithmetic is reproduced without gate changes.
- Historical stability ambiguity and the phase-only aggregation failure are explained with code revision and test evidence.
- A new campaign exists only after a documented go decision, frozen protocol, new budget, disjoint seeds, and one held-out validation. If the go decision is negative, the completed audit and bounded claim are the correct end state.
