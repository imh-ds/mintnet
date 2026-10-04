# CIN Follow-up F v2 Validation Audit

**Disposition:** The frozen F-only completion gate passed. This is a bounded result for the exact candidate and simulation setting below; it does not establish broader recovery or inferential claims.

## Run and frozen protocol

- GitHub Actions run: [37177262946](https://github.com/imh-ds/mintnet/actions/runs/37177262946), dispatched once from `main` at `2178ade78ea8b04f048e75677d4a4336aa7a6cab`.
- Protocol: `cin-followup-f-v2`; case F, method CIN, `n=150`, cap 1,000, support-aware inner splits enabled, no stability scope.
- Cohort: exactly validation identities 6500–6596, sharded as `val0` and `val1`; aggregate phase `validation`.
- Workflow: plan passed in 8 seconds; `val0` shard passed in 59 seconds; `val1` shard passed in 58 seconds; aggregate passed in 24 seconds. Four job durations sum to 149 seconds (0.0413889 runner-hours); the longest job was 59 seconds (0.0163889 hours). Run wall time was about 96 seconds from plan start through aggregate completion.
- Frozen hashes: source config `8fa7cac1e2b678fb7744cc4e2909a959c8fae8a0db610f01b39aba6a526225ef`; resolved config `71f7bc1081a870d1660d8263a0d5e82595176f2cc8f96a7f9e934c0f1c4df52a`; charter `9490b8e36912760a030bf3a3dcf3e37fe81fda0bd284bebbde239e7473fd9b68`; seed inventory `ff9c69cad54c1d7a7bc4b27dae4c41a99b1af4aec24324ebe7c582e09d34f411`.
- Hosted environment: Python 3.11.16, Linux. Aggregate metadata records two shards and `provenance_validated=true`.

## Prespecified gate and artifact audit

The gate checker was run after download using the frozen config, metadata, and manifest. Reproduce it from the repository root with:

```powershell
$env:PYTHONPATH = 'src;.'
python scripts/cin_followup_f_gate_check.py `
  --config configs/cin_followup_v2.yaml `
  --raw docs/cin_followup_audit/followup_f_v2/validation/run-37177262946/cin-followup-f-v2-aggregate/raw_metrics.csv `
  --metadata docs/cin_followup_audit/followup_f_v2/validation/run-37177262946/cin-followup-f-v2-aggregate/metadata.json `
  --freeze-manifest docs/cin_followup_audit/followup_f_v2/freeze_candidate_v2.json `
  --output docs/cin_followup_audit/followup_f_v2/validation/run-37177262946/f_gate.json
```

It returned `status=pass`:

| Check | Result |
|---|---|
| Expected validation denominator | 97 identities, exactly 6500–6596 |
| Unique `(case, phase, replicate, method)` keys | 97; no duplicates, missing, or foreign keys |
| Status counts | 97 complete; 0 incomplete; 0 errors |
| Frozen completion gate | Pass: 97/97 = 1.0, threshold 1.0 |
| 95% Wilson interval | 0.961906–1.000000; half-width 0.019047 |
| Pair fits | 28/28 complete on every row; 2,716 aggregate pair rows |
| Generator-attempt accounting | Present on every row; range 1–975 |
| Source sidecar manifests | 97 entries across two shards; all files present, hashes match, each has 28 data rows |
| Aggregate raw metrics | SHA-256 matches metadata: `f615333c8c4b0cbc0151214cb1441993fe9ea64d665171217e87671aa5029c82` |
| Config and charter provenance | Both match the frozen manifest; aggregate provenance validation passed |

All validation rows have finite AP because all rows completed. Mean AP is 0.619521 (MCSE 0.014449, n=97); this is descriptive and was not a gate. Mean strong-edge recall is also descriptive and has only 93 contributors because the truth-based metric is unavailable for four identities without a qualifying strong-edge set. No AP threshold or edge-recovery claim is inferred from these summaries.

The separate D-106 failure diagnosis and E paired analysis remain in `docs/cin_followup_audit/d106/f_failures.md` and `docs/cin_followup_audit/d106/e_nonlinear_gain.md`; the forensic closeout and prior no-go decision are in `docs/cin_followup_audit/d106/audit_closeout.md` and `docs/cin_followup_audit/d106/decision_memo.md`. This v2 validation is kept as a separate protocol and cohort.

The raw and aggregate outputs, both shard artifacts, resolved configs, metadata, reports, all source pair sidecars, and aggregate sidecar manifest are retained in `validation/run-37177262946/`. The frozen checker output is `validation/run-37177262946/f_gate.json`.

## Compute and interpretation

The v2 development run used 0.0216667 runner-hours; this validation used 0.0413889, for 0.0630556 total against the 0.50-hour ceiling and below the combined 0.24-hour estimate. No validation identity was replaced, retried, or selectively stopped. The preregistered endpoint passes for this F-only candidate and setting.

This result does not revise D-106, estimate the separate causal contribution of the cap and support-aware split, establish AP or edge-recovery performance, validate ordinal modeling, or support high-p categorical recovery, panel-wide stability, FDR, rare-failure/tail-risk, or broad CIN recovery claims. Keep the categorical branch experimental and preserve D-106's failures unchanged.

GitHub Actions emitted non-blocking notices that actions/checkout@v4, setup-python@v5, and upload-artifact@v4 are being forced onto Node.js 24, and that `ubuntu-latest` will migrate to Ubuntu 26 beginning 2026-10-19. These are workflow maintenance items, not validation failures.

## Repository verification

On the unchanged source revision, the focused regression command
`python -m pytest tests/unit/test_cin_followup_f_gate_check.py tests/unit/test_cin_followup_dispatch_guard.py tests/unit/test_aggregate_shards.py tests/integration/test_cin_runners.py -q --basetemp=.pytest-tmp-followup-val-final`
completed with **110 passed, 6 existing pandas FutureWarnings, 303.53 seconds**.
No production source code changed for this campaign close-out; Ruff was not
run on the documentation and archived result files.
