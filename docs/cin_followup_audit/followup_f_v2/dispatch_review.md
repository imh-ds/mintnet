# CIN F Follow-Up v2 Dispatch Review

**Decision state:** protocol frozen locally; no GitHub Actions run has been launched. Dispatch requires separate owner authorization. The current checkout is the local branch `codex/fix-bug-01`; it must be made available on GitHub before a workflow can run. No push has been made.

## Frozen package

- Charter: `docs/cin_followup_charter_v2.md`
- Config: `configs/cin_followup_v2.yaml`
- Freeze manifest: `docs/cin_followup_audit/followup_f_v2/freeze_candidate_v2.json`
- Frozen source revision: `4d29ce0121f55ff1518061796ce40bd767fe0ccf`
- Candidate: F generator cap 1,000 plus support-aware inner splits; 0.005 population-CMI floor unchanged.
- Development: 20 identities, 6400–6419. Validation: 97 identities, 6500–6596. Local correctness smoke identity 6300 is reserved in the seed inventory and is in neither cohort.
- Primary gate: all 97 validation identities complete, with failures retained in the denominator.
- Precision target: two-sided 95% Wilson interval, worst-case half-width 0.0975835.
- Expected runner usage: 0.24 hours. Hard ceiling: 0.50 runner-hours for both phases including one outcome-independent operational recovery. Stability is excluded.
- Environment: GitHub-hosted Ubuntu, Python 3.11, pinned `requirements-cin-followup-v1.txt`.

## Workflow inputs

Both runs use workflow `sharded_benchmark.yml`, runner module `mintnet.experiments.cin_baseline`, config `configs/cin_followup_v2.yaml`, dimension 1 flag/value `--cases` / `F`, dimension 2 flag `--replicate-batches`, no dimension 3, and freeze manifest `docs/cin_followup_audit/followup_f_v2/freeze_candidate_v2.json`. The aggregation phase must match the batch values.

Development is `dev0`, aggregation phase `development`:

```powershell
gh workflow run sharded_benchmark.yml --ref codex/fix-bug-01 `
  --field runner_module=mintnet.experiments.cin_baseline `
  --field config=configs/cin_followup_v2.yaml `
  --field dim1_flag=--cases --field dim1_values=F `
  --field dim2_flag=--replicate-batches --field dim2_values=dev0 `
  --field freeze_manifest=docs/cin_followup_audit/followup_f_v2/freeze_candidate_v2.json `
  --field aggregation_phase=development
```

Validation is `val0,val1` in the same workflow so the aggregator receives all 97 identities, aggregation phase `validation`:

```powershell
gh workflow run sharded_benchmark.yml --ref codex/fix-bug-01 `
  --field runner_module=mintnet.experiments.cin_baseline `
  --field config=configs/cin_followup_v2.yaml `
  --field dim1_flag=--cases --field dim1_values=F `
  --field dim2_flag=--replicate-batches --field dim2_values=val0,val1 `
  --field freeze_manifest=docs/cin_followup_audit/followup_f_v2/freeze_candidate_v2.json `
  --field aggregation_phase=validation
```

The validation command is contingent on the development artifacts passing their frozen identity/provenance checks and the owner separately approving the held-out run. The plan job parses config YAML and rejects altered dimensions before creating the shard matrix. The shard preflight resolves the frozen and dispatch revisions, requires dispatch from the checked-out commit and a source-identical descendant of the frozen commit, and verifies the frozen source fingerprint. The workflow also blocks full-grid aggregation, partial validation batches, cap/split overrides, third dimensions, unsupported dimensions, and missing or changed freeze values before fitting starts. Results upload as `cin-followup-f-v2-aggregate` and aggregate locally under `results/generated/cin_followup_f_v2` in the Actions artifact.

An independent final review found and prompted fixes for a dimension-1 override bypass, syntax-only Git revision checks, and exact-text protocol detection. Regression tests now cover those cases, including quoted/commented YAML protocol values. These repairs change dispatch validation only; they do not change the candidate or the frozen statistical gate.

## Dispatch attempt log

- 2026-10-03, run [37157100618](https://github.com/imh-ds/mintnet/actions/runs/37157100618): stopped in the plan job before shard-matrix creation. The guard's dimension flags began with `--` and were passed as separate argparse values, so argparse treated them as options. No shard or benchmark identity ran; no campaign seed was consumed. The workflow now passes those inputs in `--option=value` form. The fix is covered by a direct CLI regression test and is frozen in the source revision above.

## What the gate can establish

A pass would support only that this fixed F-only candidate completed all 97 new identities under this frozen protocol. It would not repair the earlier failed Task 11 gate, demonstrate rare-failure control, establish recovery accuracy, or change the unsupported E and panel-wide claims. A failure remains in the denominator and leaves the candidate gate failed.
