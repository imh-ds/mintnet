# F Follow-Up GitHub Actions Run Log

**Repository branch:** `codex/fix-bug-01`
**Final hosted campaign result:** completed; strict candidate validation gate failed (see [`validation_report.md`](validation_report.md))
**Frozen benchmark source:** `d006f7f46a9011125f923de540dce6ac90d3ab11`

## Run ledger

| Run | Purpose | Outcome | Notes |
| --- | --- | --- | --- |
| [36536987174](https://github.com/imh-ds/mintnet/actions/runs/36536987174) | Candidate development, initial dispatch | Aggregate failed | Shard passed; aggregate could not import `scripts.aggregate_cin_sidecars` because the workflow exposed `src` but not the repository root on `PYTHONPATH`. |
| [36537008680](https://github.com/imh-ds/mintnet/actions/runs/36537008680) | Baseline development, initial dispatch | Aggregate failed | Same aggregate import-path defect. |
| [36538544662](https://github.com/imh-ds/mintnet/actions/runs/36538544662) | Candidate development, retry | Passed | Full 20-identity aggregate and provenance passed. |
| [36538562967](https://github.com/imh-ds/mintnet/actions/runs/36538562967) | Baseline development, retry | Passed | Full 20-identity aggregate and provenance passed. |
| [36538830085](https://github.com/imh-ds/mintnet/actions/runs/36538830085) | Candidate validation `val0` alone | Aggregate failed | Shard produced 48 rows; phase aggregator requires all 97 validation identities. No metrics were used from this partial aggregate. |
| [36538831378](https://github.com/imh-ds/mintnet/actions/runs/36538831378) | Candidate validation `val1` alone | Aggregate failed | Shard produced the complementary 49 rows; phase aggregator requires all 97 in one workflow aggregate. |
| [36538831850](https://github.com/imh-ds/mintnet/actions/runs/36538831850) | Baseline validation `val0` alone | Aggregate failed | Partial-phase aggregation shape mismatch. |
| [36538832064](https://github.com/imh-ds/mintnet/actions/runs/36538832064) | Baseline validation `val1` alone | Aggregate failed | Partial-phase aggregation shape mismatch. |
| [36539181736](https://github.com/imh-ds/mintnet/actions/runs/36539181736) | Candidate validation, both batches | Passed | `val0` and `val1` were combined into the required 97-row validation aggregate. |
| [36539184400](https://github.com/imh-ds/mintnet/actions/runs/36539184400) | Baseline validation, both batches | Passed | `val0` and `val1` were combined into the required 97-row validation aggregate. |

The successful development comparison used the same 20 identities, seeds, and generator attempts in both arms: baseline completed 19/20 identities and candidate completed 20/20. The validation aggregates likewise contain the same 97 identities and five-seed bundles in both arms.

## Operational corrections

1. Commit `d006f7f` amended the aggregate job's `PYTHONPATH` to include the repository root and added a regression test. A fresh local shard aggregated successfully, and the relevant local suite passed 319 tests at that stage.
2. The first validation dispatches split `val0` and `val1` across separate workflows. Each partial shard succeeded, but the aggregator correctly rejected 48-row or 49-row partial validation phases because the frozen gate requires exactly 97 rows. The authorized replay combined both batches within one workflow per arm; no partial metrics were used.
3. The strict gate initially rejected the valid baseline manifest because a present Boolean `false` was treated as missing. Commit `e190169` fixed the truthiness check and added regression coverage.
4. Commit `7b3f3a9` made validation provenance compare source fingerprints at the frozen code revision and aggregate revision. The dispatch revision is a docs-only commit after the frozen source; both revisions resolve to the same frozen-source fingerprint. This lets the corrected checker evaluate the preserved runs without changing or rerunning held-out identities.

## Runtime and warnings

Summing GitHub job durations across all ten attempts, including failed aggregates and the authorized replay, used approximately **0.239 runner-hours**. This is below the frozen one-pass estimate of 0.585 runner-hours and the 1.25 runner-hour ceiling. The workflow also emitted non-fatal GitHub notices about future `ubuntu-latest` image migration and actions' Node 20 runtime deprecation.

The cap sweep was already run locally on the 20 development identities. The frozen workflow rejects post-freeze generator-cap overrides, so no hosted cap override was attempted.
