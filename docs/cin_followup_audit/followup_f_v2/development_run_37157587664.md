# CIN Follow-up F v2 Development Run Audit

**Disposition:** Development operational checkpoint passed. This is not validation evidence and does not establish a statistical or generalization claim.

## Run and protocol

- GitHub Actions run: [37157587664](https://github.com/imh-ds/mintnet/actions/runs/37157587664), dispatched from `main` at `001a50a9e9a559db8c5a48ea2caaad3a5a508339`.
- Frozen protocol: `cin-followup-f-v2`; its source revision is `4d29ce0121f55ff1518061796ce40bd767fe0ccf`. The dispatched revision is a descendant containing only the dispatch-review and freeze-manifest documentation updates; the frozen source-code fingerprint was unchanged and workflow preflight passed.
- Inputs: `configs/cin_followup_v2.yaml`, case F, development batch `dev0`, aggregate phase `development`, cap 1,000, support-aware inner splits enabled.
- Freeze checks: source config SHA-256 `8fa7cac1e2b678fb7744cc4e2909a959c8fae8a0db610f01b39aba6a526225ef`; resolved config SHA-256 `71f7bc1081a870d1660d8263a0d5e82595176f2cc8f96a7f9e934c0f1c4df52a`; charter SHA-256 `9490b8e36912760a030bf3a3dcf3e37fe81fda0bd284bebbde239e7473fd9b68`; seed-inventory SHA-256 `ff9c69cad54c1d7a7bc4b27dae4c41a99b1af4aec24324ebe7c582e09d34f411`.
- The hosted environment reported Python 3.11.16 on Linux. The one shard and aggregate each reported 9.1436 seconds of benchmark runtime; the three Actions jobs (plan, shard, aggregate) had 78 seconds summed job duration and 39 seconds maximum job duration. The compute ledger records these as 0.0216667 runner-hours summed and 0.0108333 hours maximum wall time.

## Integrity and outcomes

| Check | Result |
|---|---|
| Expected development identities | Exactly F/development/6400–6419 (20 rows) |
| Duplicate or missing identity keys | None; 20 unique `(case, phase, replicate, method)` keys |
| Completion statuses | 20/20 `complete` |
| Pair fits | 28/28 complete for every identity; 560 aggregate pair rows |
| Generator attempt accounting | Present on all rows; range 6–534, mean 130.95 |
| Shard sidecar manifest | 20 entries; every file exists, SHA-256 matches, and row count is 28 |
| Aggregate raw metrics | SHA-256 matches metadata: `67088959d4840ab351adb9c56de7b451032cffc56dced3f8a5e819bd8b742bfa` |
| Aggregate provenance | `provenance_validated=true`, one shard, commit/config/charter metadata align with the frozen protocol |

The descriptive CIN AP mean was 0.6605169 (MCSE 0.0279005, n=20). The charter does not use AP as a validation gate; this development summary therefore does not select a new threshold or support an AP/recovery claim. No identity had to be replaced or retried.

The preserved files under `development/run-37157587664/` include aggregate and shard raw metrics, panel outputs, resolved config, metadata, all pair sidecars, and manifests. The aggregate sidecar contains 560 data rows. A prior dispatch attempt, [37157100618](https://github.com/imh-ds/mintnet/actions/runs/37157100618), failed in the plan job because dashed dimension arguments were parsed as options. It created no shard and consumed no cohort identity. The argument-passing fix was committed as `4d29ce0`; corrected run 37157587664 passed its plan guard.

## Decision and next gate

The frozen development rule is satisfied: all 20 expected identities are complete. No code, config, fit setting, generator floor, or candidate change is warranted by this operational checkpoint. The validation identities remain 6500–6596 and are disjoint under the already-passed seed preflight. Actual compute used to date is 0.0216667 runner-hours against the protocol ceiling of 0.50; 0.4783333 hours remain by that ceiling arithmetic. The combined protocol estimate remains 0.24 runner-hours.

The protocol's next stage is the post-development validation preflight, followed by a single validation dispatch. This report and the development result do not themselves authorize that dispatch. No validation identities were run or consumed. Keep the strict 97/97 completion gate and report failures in the denominator if validation is later authorized.

## Verification limits

This local shell could not launch its configured Python interpreter (`python.exe` access denied; `py -3.11` reported no installed Python). The hosted plan/shard/aggregate jobs succeeded, and this audit independently checked identities, CSV counts, gzip row counts, all 20 source-sidecar hashes, the aggregate raw hash, and current config/charter hashes with PowerShell/.NET. The package test suite was not rerun in this shell during this evidence-recording step.
